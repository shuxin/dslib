"""
This is the main part of the dslib library - a client object resides here
which is responsible for all communication with the DS server..
"""
        
# this is a work-around for an incompatibility of openssl-1.0.0beta
# with the login.czebox.cz sites HTTPS interface
# more info here: https://bugzilla.redhat.com/show_bug.cgi?id=537822
# the workaround breaks things on FreeBSD
import sys, os
#if not sys.platform.startswith("freebsd") and not sys.platform.startswith("darwin"):
#  try:
#    import _ssl
#    _ssl.PROTOCOL_SSLv23 = _ssl.PROTOCOL_SSLv3
#  except:
#    pass
# / end of work-around

# suds does not work properly without this
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import base64
import pkcs7
import pkcs7.pkcs7_decoder
import pkcs7.verifier
import logging

from suds.client import Client as SudsClient
from suds.transport.http import HttpAuthenticated
import exceptions
from ds_exceptions import DSException
import models

import certs.pem_decoder

### temp

import urllib2
import httplib
from suds.transport.http import HttpAuthenticated, HttpTransport
AuthParent = HttpTransport 
#SUDS Client Auth solution
class HttpClientAuthTransport(AuthParent):
    def __init__(self, key, cert, **kwargs):
        AuthParent.__init__(self, **kwargs)
        to_remove = []
        for h in self.urlopener.handlers:
          if h.__class__.__name__ == "HTTPSHandler":
            to_remove.append(h)
        print to_remove
        for h in to_remove:
          self.urlopener.handlers.remove(h)
          self.urlopener.handle_open['https'].remove(h)
        self.urlopener.add_handler(HTTPSClientAuthHandler(key, cert))
#HTTPS Client Auth solution for urllib2, inspired by
# http://bugs.python.org/issue3466
# and improved by David Norton of Three Pillar Software. In this
# implementation, we use properties passed in rather than static module
# fields.
class HTTPSClientAuthHandler(urllib2.HTTPSHandler):
    def __init__(self, key, cert):
        urllib2.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert
        self.set_http_debuglevel(100)
    def https_open(self, req):
        #Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        print "AAA"
        return self.do_open(self.getConnection, req)
    def getConnection(self, host, **kwargs):
        print "BBBB"
        return httplib.HTTPSConnection(host, key_file=self.key, cert_file=self.cert, strict=False, **kwargs)

### // end of temp

class Dispatcher(object):
  """
  DS splits its functionality between several parts. These have different URLs
  as well as different WSDL files.
  Dispatcher is a simple client that handles one of these parts
  """

  def __init__(self, ds_client, wsdl_url, soap_url=None, proxy=None, trusted_certs_dir=None):
    """proxy can be a string 'hostname:port' or None"""
    self.ds_client = ds_client # this is a Client instance; username, password, etc. will be take from it
    self.wsdl_url = wsdl_url
    self.soap_url = soap_url # if None, default from WSDL will be used
    self.proxy = proxy
    if self.proxy:
      transport = HttpAuthenticated(username=self.ds_client.login, password=self.ds_client.password, proxy={'https':self.proxy})
    else:
      if self.ds_client.login_method == "username":
        transport = HttpAuthenticated(username=self.ds_client.login, password=self.ds_client.password)
      elif self.ds_client.login_method == "certificate":
        transport = HttpClientAuthTransport(self.ds_client.key_file, self.ds_client.cert_file, username=self.ds_client.login, password=self.ds_client.password)
    if not self.soap_url:
      self.soap_client = SudsClient(self.wsdl_url, transport=transport)
    else:
      self.soap_client = SudsClient(self.wsdl_url, transport=transport, location=self.soap_url)
    self.trusted_certs = []
    if trusted_certs_dir is not None:
        self.trusted_certs = certs.pem_decoder.load_certificates_from_dir(trusted_certs_dir)

    
  def __getattr__(self, name):
    def _simple_wrapper(method):
      def f(*args, **kw):
        reply = method(*args, **kw)
        status = self._extract_status(reply)
        data = getattr(reply, name)
        return Reply(status, data)
      return f
    return _simple_wrapper(getattr(self.soap_client.service, name))

  @classmethod
  def _extract_status(self, reply):
    if hasattr(reply, "dmStatus"):
      status = models.dmStatus(reply.dmStatus)
    elif hasattr(reply, "dbStatus"):
      status = models.dbStatus(reply.dbStatus)
    else:
      raise ValueError("Neither dmStatus, nor dbStatus found in reply:\n%s" % reply)
    return status


  def _handle_dmrecords_and_status_response(self, method):
    reply = method()
    status = self._extract_status(reply)
    # the following is a hack around a bug in the suds library that
    # does not properly create a list when only one object is present
    if reply.dmRecords == "":
      result = []
    else:
      messages = reply.dmRecords.dmRecord
      if type(messages) != list:
        result = [models.Message(messages)]
      else:
        result = [models.Message(message) for message in messages]
    return Reply(status, result)
    
  def GetListOfSentMessages(self):
    method = self.soap_client.service.GetListOfSentMessages
    return self._handle_dmrecords_and_status_response(method)

  def GetListOfReceivedMessages(self):
    method = self.soap_client.service.GetListOfReceivedMessages
    return self._handle_dmrecords_and_status_response(method)

  def MessageEnvelopeDownload(self, msgid):
    reply = self.soap_client.service.MessageEnvelopeDownload(msgid)
    if hasattr(reply, 'dmReturnedMessageEnvelope'):
      message = models.Message(reply.dmReturnedMessageEnvelope)
    else:
      message = None
    return Reply(self._extract_status(reply), message)

  def MessageDownload(self, msgid):
    reply = self.soap_client.service.MessageDownload(msgid)
    if hasattr(reply, 'dmReturnedMessage'):
      message = models.Message(reply.dmReturnedMessage)
    else:
      message = None
    return Reply(self._extract_status(reply), message)

  def DummyOperation(self):
    reply = self.soap_client.service.DummyOperation()
    assert reply == None
    return Reply(None, None)

  def FindDataBox(self, info):
    """info = dbOwnerInfo instance"""
    soap_info = self.soap_client.factory.create("dbOwnerInfo")
    info.copy_to_soap_object(soap_info)
    reply = self.soap_client.service.FindDataBox(soap_info)
    if reply.dbResults:
      ret_infos = reply.dbResults.dbOwnerInfo
      if type(ret_infos) != list:
        ret_infos = [ret_infos]
      result = [models.dbOwnerInfo(ret_info) for ret_info in ret_infos]
    else:
      result = []
    return Reply(self._extract_status(reply), result)

  def CreateMessage(self, envelope, files):
    """returns message id as reply.data"""
    soap_envelope = self.soap_client.factory.create("dmEnvelope")
    envelope.copy_to_soap_object(soap_envelope)
    soap_files = self.soap_client.factory.create("dmFiles")
    for f in files:
      soap_file = self.soap_client.factory.create("dmFile")
      f.copy_to_soap_object(soap_file)
      soap_files.dmFile.append(soap_file)
    reply = self.soap_client.service.CreateMessage(soap_envelope, soap_files)
    if hasattr(reply,"dmID"):
      dmID = reply.dmID
    else:
      dmID = None
    return Reply(self._extract_status(reply), dmID)
    
  def GetOwnerInfoFromLogin(self):
    reply = self.soap_client.service.GetOwnerInfoFromLogin()
    if hasattr(reply, 'dbOwnerInfo'):
      message = models.dbOwnerInfo(reply.dbOwnerInfo)
    else:
      message = None
    return Reply(self._extract_status(reply), message)
  
  def _verify_der_msg(self, der_message):    
    verification_result = pkcs7.verifier.verify_msg(der_message)
    if verification_result:        
        logging.debug("Message verified")
    else:
        logging.debug("Verification of pkcs7 message failed")
    return verification_result
    
  def _xml_parse_msg(self, string_msg):
    import suds.sax.parser as p
    parser = p.Parser()
    document = parser.parse(string = string_msg)
    return document

  def _create_message_instance(self, xml_document, message_type):
    m = None
    if (message_type == "Message"):
        m = models.Message(xml_document = xml_document, 
                   path_to_content=models.Message.SIG_MESSAGE_CONTENT_PATH)
    if (message_type == "DeliveryInfo"):
        m = models.Message(xml_document = xml_document, 
                   path_to_content=models.Message.SIG_DELIVERY_CONTENT_PATH)
    if ( m == None):
        print "Unknown type of message: %s" % message_type
        print "Expected: 'Message' or 'DeliveryInfo'"
    return m
  
  def _prepare_PKCS7_data(self, decoded_msg):    
    pkcs_data = models.PKCS7_data(decoded_msg)
    return pkcs_data
  
  def _generic_get_signed(self, der_encoded):
    '''
    "Base" of methods downloading signed versions of messages and
    delivery information.
    Returns tuple xml_document, pkcs7_data, verified, cert_verified
    '''
    # decode DER encoding
    decoded_msg = pkcs7.decoder.decode_msg(der_encoded)
    # verify the message
    verified = self._verify_der_msg(decoded_msg)            
    # prepare PKCS7 to supply to the Message
    pkcs_data = self._prepare_PKCS7_data(decoded_msg)
    # extract sent message from pkcs7 document
    str_msg = pkcs_data.signed_data.message
    # parse string xml to create xml document
    xml_document = self._xml_parse_msg(str_msg)
    
    # verify certificate
    certificates_ok = False
    certs = decoded_msg.getComponentByName("certificates")
    for cert in certs:
        if self._verify_certificate(cert):
            certificates_ok = True
        else:
            # if certificate is not trusted, set to false and exit cycle
            certificates_ok = False
            break
        
    return xml_document, pkcs_data, verified, certificates_ok
  
  def _signed_msg_download(self, ws_name, msg_id):
    '''
    Common method for downloading signed message (sent or received)
    '''
    method = getattr(self.soap_client.service, ws_name)
    if (method is None):
        raise Exception("Unknown method: %s" % ws_name)
    reply = method.__call__(msg_id)
    der_encoded = base64.b64decode(reply.dmSignature)  
   
    xml_document, pkcs_data, verified, cert_verified  = self._generic_get_signed(der_encoded)
    
    message = self._create_message_instance(xml_document, "Message")        
    message.pkcs7_data = pkcs_data
    if (verified):
        message.is_verified = True
    
    # TODO: distinguish among certificates (may be more signers, but highly improbable)
    if cert_verified:
        for c in message.pkcs7_data.certificates:
            c.is_verified = True
    
    return Reply(self._extract_status(reply), message)
  
  def _verify_certificate(self, certificate):
    import certs.cert_verifier
    res = certs.cert_verifier.verify_certificate(certificate, self.trusted_certs)
    return res
     
  def SignedMessageDownload(self, msgId):
    return self._signed_msg_download("SignedMessageDownload", msgId)
    
  def SignedSentMessageDownload(self, msgId):
    return self._signed_msg_download("SignedSentMessageDownload", msgId)
    
  def GetSignedDeliveryInfo(self, msgId):
    reply = self.soap_client.service.GetSignedDeliveryInfo(msgId)
    der_encoded = base64.b64decode(reply.dmSignature)  
    xml_document, pkcs_data, verified, cert_verified  = self._generic_get_signed(der_encoded)
    # create Message instance to return 
    message = self._create_message_instance(xml_document, "DeliveryInfo")        
    message.pkcs7_data = pkcs_data
    if (verified):
        message.is_verified = True
    
    # TODO: distinguish among certificates (may be more signers, but highly improbable)
    if cert_verified:
        for c in message.pkcs7_data.certificates:
            c.is_verified = True
            
    return Reply(self._extract_status(reply), message)


class Client(object):

  cur_path = os.path.dirname(os.path.abspath(__file__))
  if cur_path.startswith("/"):
    WSDL_URL_BASE = 'file://%s/wsdl/' % cur_path
  else:
    WSDL_URL_BASE = 'file:///%s/wsdl/' % cur_path

  attr2dispatcher_name = {"GetListOfSentMessages": "info",
                          "GetListOfReceivedMessages": "info",
                          "MessageDownload": "operations",
                          "MessageEnvelopeDownload": "info",
                          "DummyOperation": "operations",
                          "GetDeliveryInfo": "info",
                          "FindDataBox": "search",
                          "CreateMessage": "operations",
                          "GetOwnerInfoFromLogin": "supplementary",
                          "SignedMessageDownload" : "operations",
                          "SignedSentMessageDownload" : "operations",
                          "GetSignedDeliveryInfo" : "info"
                          }

  dispatcher_name2config = {"info": {"wsdl_name": "dm_info.wsdl",
                                     "soap_url_end": "dx"},
                            "operations": {"wsdl_name": "dm_operations.wsdl",
                                           "soap_url_end": "dz"},
                            "search": {"wsdl_name": "db_search.wsdl",
                                       "soap_url_end": "df"},
                            "supplementary": {"wsdl_name": "db_supplementary.wsdl",
                                              "soap_url_end": "DsManage"}
                            }
  test2soap_url = {True: "https://www.czebox.cz/",
                   False: "https://www.mojedatovaschranka.cz/"}

  login_method2url_part = {"username": "DS",
                           "certificate": "cert/DS",
                           }

  def __init__(self, login=None, password=None, soap_url=None, test_environment=None,
               login_method="username", key_file=None, cert_file=None,
               proxy=None, trusted_certs_dir=None):
    """
    if soap_url is not given and test_environment is given, soap_url will be
    infered from the value of test_environment based on what is set in test2soap_url;
    if neither soap_url not test_environment is provided, it will be empty and
    the dispatcher will use the value from WSDL;
    if soap_url id used, it will be used without regard to test_environment value
    proxy can be a string 'hostname:port' or None or -1 for automatic
    detection using the urllib2 library
    """
    self.login = login
    self.password = password
    if soap_url:
      self.soap_url = soap_url
    elif test_environment != None:
      self.soap_url = Client.test2soap_url[test_environment]
    else:
      self.soap_url = None
    self.test_environment = test_environment
    self.login_method = login_method
    self._dispatchers = {}
    self.proxy = proxy
    self.trusted_certs_dir = trusted_certs_dir
    self.key_file = key_file
    self.cert_file = cert_file


  def __getattr__(self, name):
    """called when the user tries to access attribute or method;
    it looks if some dispatcher supports it and then returns the
    corresponding dispatchers method."""
    if name not in Client.attr2dispatcher_name:
      raise AttributeError("Client object does not have an attribute named '%s'"%name)
    dispatcher_name = Client.attr2dispatcher_name[name]
    dispatcher = self.get_dispatcher(dispatcher_name)
    return getattr(dispatcher, name)


  def get_dispatcher(self, name):
    """returns a dispatcher object based on its name;
    creates the dispatcher if it does not exist yet"""
    if name not in self._dispatchers:
      if name in Client.dispatcher_name2config:
        return self._create_dispatcher(name)
      else:
        raise Exception("Wrong or unsupported dispatcher name '%s'" % name)
    else:
      return self._dispatchers[name]


  def _create_dispatcher(self, name):
    """creates a dispatcher based on it name;
    config for a name is present in Client.dispatcher_name2config
    """
    config = Client.dispatcher_name2config[name]
    this_soap_url = None
    if self.soap_url:
      if self.soap_url.endswith("/"):
        this_soap_url = self.soap_url
      else:
        this_soap_url = self.soap_url + "/"
      this_soap_url += Client.login_method2url_part[self.login_method] + "/" + config['soap_url_end']
    dis = Dispatcher(self, Client.WSDL_URL_BASE+config['wsdl_name'], soap_url=this_soap_url,\
                      proxy=self.get_real_proxy(), trusted_certs_dir=self.trusted_certs_dir)
    self._dispatchers[name] = dis
    return dis

  def get_real_proxy(self):
    return self.proxy_to_real_proxy(self.proxy)

  @classmethod
  def proxy_to_real_proxy(cls, proxy):
    """interpret the proxy setting to obtain a real name and port or None"""
    if proxy == None:
      return None
    elif proxy == -1:
      import urllib2
      return urllib2.getproxies().get('https',None) 
    else:
      return proxy    

class Reply(object):
  """represent a reply from the SOAP server"""

  def __init__(self, status, data):
    self.status = status
    self.data = data

  def __unicode__(self):
    return "Reply: StatusCode: %s; DataType: %s" % (self.status.dmStatusCode, data.__class__.__name__)


if __name__ == "__main__":
  import logging
  logging.basicConfig(level=logging.INFO)
  logging.getLogger('suds.transport.http').setLevel(logging.DEBUG)
  #logging.getLogger('suds.transport.http').setLevel(logging.DEBUG)
  #cl = Client(login_method="username",
  #            login="kvm6ra",
  #            password="Schr8ne4ka",
  #            test_environment=True)
  #print cl.GetOwnerInfoFromLogin()
  #aaa  
  cl = Client(login_method="certificate",
              login="kvm6ra",
              password="Schr8ne4ka",
              key_file=None, #os.path.abspath("beda-keyfile.pem"),
              cert_file=os.path.abspath("keys.pem"),
              test_environment=True)
  info = models.dbOwnerInfo()
  info.dbType = "FO"
  info.dbID = u"kvm6ra"
  rep = cl.FindDataBox(info) #.GetListOfReceivedMessages()
  print rep
