# encoding: utf-8

#*    dslib - Python library for Datove schranky
#*    Copyright (C) 2009-2012  CZ.NIC, z.s.p.o. (http://www.nic.cz)
#*
#*    This library is free software; you can redistribute it and/or
#*    modify it under the terms of the GNU Library General Public
#*    License as published by the Free Software Foundation; either
#*    version 2 of the License, or (at your option) any later version.
#*
#*    This library is distributed in the hope that it will be useful,
#*    but WITHOUT ANY WARRANTY; without even the implied warranty of
#*    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#*    Library General Public License for more details.
#*
#*    You should have received a copy of the GNU Library General Public
#*    License along with this library; if not, write to the Free
#*    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#*

"""
This is the main part of the dslib library - a client object resides here
which is responsible for all communication with the DS server..
"""

# standard library imports
# suds does not work properly without this
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import base64
import logging
import re
import urllib2
import cookielib

# third party imports
import OpenSSL

# local imports
import pkcs7.pkcs7_decoder
import pkcs7.verifier
import pkcs7.tstamp_helper
from sudsds.client import Client as SudsClient
from sudsds.transport.http import HttpAuthenticated, HttpTransport
import exceptions
from ds_exceptions import \
  DSOTPException, DSNotAuthorizedException, DSSOAPException,\
  DSServerCertificateException
import models
from properties.properties import Properties as props
import certs.cert_loader
import local
import release
from network import NoPostRedirectionHTTPRedirectHandler, ProxyManager


class Dispatcher(object):
  """
  DS splits its functionality between several parts. These have different URLs
  as well as different WSDL files.
  Dispatcher is a simple client that handles one of these parts
  """

  # this is a map between a signed version of a method and its
  # normal counterpart which should be used to decode the content after it's
  # unpacked from pkcs7 
  SIGNED_TO_DECODING_METHOD = {"SignedMessageDownload":"MessageDownload",
                               "SignedSentMessageDownload":"MessageDownload",
                               "GetSignedDeliveryInfo":"GetDeliveryInfo",}

  def __init__(self, ds_client, wsdl_url, soap_url=None, server_certs=None):
    self.ds_client = ds_client # this is a Client instance;
                               # username, password, etc. will be take from it
    self.wsdl_url = wsdl_url
    self.soap_url = soap_url # if None, default from WSDL will be used
    if type(server_certs) == unicode:
      server_certs = server_certs.encode(sys.getfilesystemencoding())
    # test server_certs availability
    if server_certs:
      if not os.path.isfile(server_certs):
        raise DSServerCertificateException(
                    "No server certificate file found - %s" % server_certs,
                    DSServerCertificateException.SERVER_CERT_FILE_MISSING)
      else:
        if os.path.getsize(server_certs) > 100000:
          raise DSServerCertificateException(
                  "Server certificate file not valid (too big) - %s (%d KB)" %\
                  (server_certs, os.path.getsize(server_certs)//1000),
                  DSServerCertificateException.SERVER_CERT_FILE_INVALID)
        try:
          logging.debug("Loading trusted server certificates from %s",
                        server_certs)
          cert_f = open(server_certs, 'r')
          cert_content = cert_f.read()
          cert_f.close()
          logging.debug("Read %d bytes of certificate data", len(cert_content))
        except Exception as e:
          raise DSServerCertificateException(
                    "Server certificate is not readable - %s (%s)" % \
                    (server_certs, e),
                    DSServerCertificateException.SERVER_CERT_FILE_INACCESSIBLE)
        try:
          cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
                                                 cert_content)
        except Exception as e:
          raise DSServerCertificateException(
                    "Server certificate file not valid - %s" % server_certs,
                    DSServerCertificateException.SERVER_CERT_FILE_INVALID)
    # go on with creating the connection parameters
    transport_args = dict(ca_certs=server_certs,
                          cert_verifier=Client.CERT_VERIFIER,
                          username=self.ds_client.login,
                          password=self.ds_client.password,
                          user_agent_string=self.ds_client.isds_user_agent_string
                          )
    transport_class = HttpAuthenticated # for Basic HTTP authentication
    if self.ds_client.login_method in ("certificate","user_certificate"):
      transport_args.update(client_certfile = self.ds_client.client_certfile,
                            client_keyfile = self.ds_client.client_keyfile,
                            client_certobj = self.ds_client.client_certobj,
                            client_keyobj = self.ds_client.client_keyobj
                            )
      if self.ds_client.login_method == "certificate":
        transport_class = HttpTransport # we do not need Basic authentication
                                        # - we use only certs
    if self.ds_client.login_method in ("hotp", "totp"):
      transport_class = HttpTransport
      transport_args.update(cookie_callback=self.ds_client.get_cookie_jar)
    transport = transport_class(**transport_args)
    if not self.soap_url:
      self.soap_client = SudsClient(self.wsdl_url, transport=transport)
    else:
      self.soap_client = SudsClient(self.wsdl_url, transport=transport,
                                    location=self.soap_url)
    
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
      code_attr = "dmStatusCode"
      message_attr = "dmStatusMessage"
    elif hasattr(reply, "dbStatus"):
      status = models.dbStatus(reply.dbStatus)
      code_attr = "dbStatusCode"
      message_attr = "dbStatusMessage"
    else:
      raise ValueError("Neither dmStatus, nor dbStatus found in reply:\n%s" %
                       reply)
    status_code = getattr(status, code_attr)
    if status_code != "0000":
      status_message = getattr(status, message_attr)
      raise DSSOAPException(status_code, status_message)
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
    status = self._extract_status(reply)
    if hasattr(reply, 'dmReturnedMessageEnvelope'):
      message = models.Message(reply.dmReturnedMessageEnvelope)
    else:
      message = None
    return Reply(status, message)

  def MessageDownload(self, msgid):
    reply = self.soap_client.service.MessageDownload(msgid)
    status = self._extract_status(reply)
    if hasattr(reply, 'dmReturnedMessage'):
      message = models.Message(reply.dmReturnedMessage)
    else:
      message = None
    return Reply(status, message)

  def DummyOperation(self):
    reply = self.soap_client.service.DummyOperation()
    assert reply == None
    return Reply(None, None)

  def FindDataBox(self, info):
    """info = dbOwnerInfo instance"""
    soap_info = self.soap_client.factory.create("dbOwnerInfo")
    info.copy_to_soap_object(soap_info)
    reply = self.soap_client.service.FindDataBox(soap_info)
    if reply.dbStatus and reply.dbStatus.dbStatusCode == "0003":
      # this is a special case where non-zero status code is not an error
      status = reply.dbStatus
    else:
      status = self._extract_status(reply)
    if hasattr(reply, 'dbResults') and reply.dbResults:
      ret_infos = reply.dbResults.dbOwnerInfo
      if type(ret_infos) != list:
        ret_infos = [ret_infos]
      result = [models.dbOwnerInfo(ret_info) for ret_info in ret_infos]
    else:
      result = []
    return Reply(status, result)

  def CreateMessage(self, envelope, files):
    """returns message id as reply.data"""
    soap_envelope = self.soap_client.factory.create("tMessageEnvelopeSub")
    envelope.copy_to_soap_object(soap_envelope)
    soap_files = self.soap_client.factory.create("dmFiles")
    for f in files:
      soap_file = self.soap_client.factory.create("dmFile")
      f.copy_to_soap_object(soap_file)
      soap_files.dmFile.append(soap_file)
    reply = self.soap_client.service.CreateMessage(soap_envelope, soap_files)
    status = self._extract_status(reply)
    if hasattr(reply,"dmID"):
      dmID = reply.dmID
    else:
      dmID = None
    return Reply(status, dmID)
    
  def GetOwnerInfoFromLogin(self):
    reply = self.soap_client.service.GetOwnerInfoFromLogin()
    status = self._extract_status(reply)
    if hasattr(reply, 'dbOwnerInfo'):
      message = models.dbOwnerInfo(reply.dbOwnerInfo)
    else:
      message = None
    return Reply(status, message)

  def GetUserInfoFromLogin(self):
    reply = self.soap_client.service.GetUserInfoFromLogin()
    status = self._extract_status(reply)
    if hasattr(reply, 'dbUserInfo'):
      message = models.dbUserInfo(reply.dbUserInfo)
    else:
      message = None
    return Reply(status, message)
 
  def _verify_der_msg(self, der_message):
    '''
    Verifies message in DER format (decoded b64 content of dmSIgnature)
    '''    
    verification_result = pkcs7.verifier.verify_msg(der_message)
    if verification_result:        
        logging.debug("Message verified")
    else:
        logging.debug("Verification of pkcs7 message failed")
    return verification_result
    
  def _xml_parse_msg(self, string_msg, method):
    '''
    Parses content of pkcs7 message. Outputs xml document.
    '''
    import sudsds.sax.parser as p
    parser = p.Parser()
    soapbody = parser.parse(string = string_msg)
    meth_name = method.name
    decoding_method = Dispatcher.SIGNED_TO_DECODING_METHOD.get(meth_name, None)
    if not decoding_method:
      raise Exception("Decoding of XML result of '%s' is not supported." % meth_name)
    internal_method = getattr(self.soap_client.service, decoding_method).method  
    document = internal_method.binding.input
    soapbody = document.multiref.process(soapbody)
    nodes = document.replycontent(internal_method, soapbody)
    rtypes = document.returned_types(internal_method)
    if len(rtypes) > 1:
        result = document.replycomposite(rtypes, nodes)
        return result
    if len(rtypes) == 1:
        if rtypes[0].unbounded():
            result = document.replylist(rtypes[0], nodes)
            return result
        if len(nodes):
            unmarshaller = document.unmarshaller()
            resolved = rtypes[0].resolve(nobuiltin=True)
            result = unmarshaller.process(nodes[0], resolved)
            return result
    return None
    

  def _prepare_PKCS7_data(self, decoded_msg): 
    '''
    Creates objects representing pkcs7 message.
    '''   
    pkcs_data = models.PKCS7_data(decoded_msg)
    return pkcs_data
  
  def _generic_get_signed(self, der_encoded, method):
    '''
    "Base" of methods downloading signed versions of messages and
    delivery information.
    Returns tuple xml_document, pkcs7_data, verified flag 
    method is either a SOAP method or its name as string   
    '''
    if type(method) in (str, unicode):
      method = getattr(self.soap_client.service, method)
    # decode DER encoding
    decoded_msg = pkcs7.pkcs7_decoder.decode_msg(der_encoded)    
    if props.VERIFY_MESSAGE:
      # verify the message
      verified = self._verify_der_msg(decoded_msg)
    else:
      verified = None            
    # prepare PKCS7 to supply to the Message
    pkcs_data = self._prepare_PKCS7_data(decoded_msg)
    # extract sent message from pkcs7 document
    str_msg = pkcs_data.message

    # parse string xml to create xml document
    xml_document = self._xml_parse_msg(str_msg, method.method)
    return xml_document, pkcs_data, verified
  

  
  def _mark_invalid_certificates(self, message, bad_certs_ids):
    '''
    In messages's pkcs7 data mark invalid certificates       
    (sets their 'is_cerified' attribute to False)
    bad_certs_ids is array of tuples with issuer name and cert sn
    '''
    import certs.cert_finder as finder
    msg_certs = message.pkcs7_data.certificates
    for cert in bad_certs_ids:
      found = finder.find_cert_by_iss_sn(msg_certs, cert[0], cert[1])
      if found:
        found.is_verified = False
          
      
  def _signed_msg_download(self, ws_name, msg_id):
    '''
    Common method for downloading signed message (sent or received)
    '''
    method = getattr(self.soap_client.service, ws_name)
    if (method is None):
        raise Exception("Unknown method: %s" % ws_name)
    reply = method.__call__(msg_id)
    status = self._extract_status(reply)
    if not reply.dmSignature:
      return Reply(status, None)
    message = self.signature_to_message(reply.dmSignature, method)
    return Reply(status, message, raw_data=reply.dmSignature)
  
  def signature_to_message(self, signature, method):
    """
    method is either a SOAP method or its name as string
    """
    if type(method) in (str, unicode):
      method = getattr(self.soap_client.service, method)
    der_encoded = base64.b64decode(signature) 
    xml_document, pkcs_data, verified  = self._generic_get_signed(der_encoded, method)
    if method.method.name in ("SignedSentMessageDownload","SignedMessageDownload"):
      message = models.Message(xml_document.dmReturnedMessage)
    else:
      raise Exception("Unsupported signed method '%s'" % method.method.name) 
    message.pkcs7_data = pkcs_data
    if (verified):
        message.is_verified = True
    return message

  def _check_timestamp(self, message):
    '''
    Checks message timestamp - parses and verifies it. TimeStampToken
    is attached to the message.
    Method returns flag that says, if the content of messages's dmHash element
    is the same as the message imprint
    '''
    # if message had dmQtimestamp, parse and verify it
    if message.dmQTimestamp is not None:
        tstamp_verified, tstamp = pkcs7.tstamp_helper\
                                        .parse_qts(message.dmQTimestamp,\
                                                   verify=props.VERIFY_TIMESTAMP)
        
        # certificate verification (if properties say so)
        if props.VERIFY_CERTIFICATE:
          for cert in tstamp.asn1_certificates:
            c = CertificateManager.get_certificate(cert)
            if not tstamp.certificates_contain(c.tbsCertificate.serial_number):
              tstamp.certificates.append(c)            
        
        message.tstamp_verified = tstamp_verified
        message.tstamp_token = tstamp
        
        imprint = tstamp.msgImprint.imprint
        imprint = base64.b64encode(imprint)
    
        hashFromMsg = message.dmHash.value
    
        if hashFromMsg == imprint:
            logging.info("Message imprint in timestamp and dmHash value are the same")
            return True
        else:
            logging.error("Message imprint in timestamp and dmHash value differ!")
            return False

        
  def SignedMessageDownload(self, msgId):
    return self._signed_msg_download("SignedMessageDownload", msgId)
    
  def SignedSentMessageDownload(self, msgId):
    return self._signed_msg_download("SignedSentMessageDownload", msgId)
    
  def GetSignedDeliveryInfo(self, msgId):
    method = self.soap_client.service.GetSignedDeliveryInfo
    reply = method(msgId)
    status = self._extract_status(reply)
    message = self.signature_to_delivery_info(reply.dmSignature, method)
    return Reply(status, message, raw_data=reply.dmSignature)
    
  def signature_to_delivery_info(self, signature, method):
    if type(method) in (str, unicode):
      method = getattr(self.soap_client.service, method)
    der_encoded = base64.b64decode(signature)  
    xml_document, pkcs_data, verified  = self._generic_get_signed(der_encoded, method)
    # create Message instance to return 
    message = models.Message(xml_document.dmDelivery)        
    message.pkcs7_data = pkcs_data
    if (verified):
        message.is_verified = True
    
    '''
    if props.VERIFY_CERTIFICATE:
      # set verified value of message certificates    
      for c in message.pkcs7_data.certificates:
        c.is_verified = True
      if len(bad_certs) > 0:
        self._mark_invalid_certificates(message, bad_certs) 
    '''
    return message


  def GetDeliveryInfo(self, msgId):
    reply = self.soap_client.service.GetDeliveryInfo(msgId)
    status = self._extract_status(reply)
    if hasattr(reply, 'dmDelivery'):
      message = models.Message(reply.dmDelivery)
    else:
      message = None
    return Reply(status, message)
  
  def GetPasswordInfo(self):
    reply = self.soap_client.service.GetPasswordInfo()    
    status = self._extract_status(reply)
    # minOccur = 0, maxOccur = 1
    expiry_date = None
    if hasattr(reply, 'pswExpDate'):
      expiry_date = reply.pswExpDate    
    return Reply(status, expiry_date)
  
  def ChangeISDSPassword(self, old_pass, new_pass):
    reply = self.soap_client.service.ChangeISDSPassword(old_pass, new_pass) 
    status = models.dbStatus(reply)   
    return Reply(status, None)

  def AuthenticateMessage(self, message_data):
    reply = self.soap_client.service.AuthenticateMessage(message_data) 
    status = models.dmStatus(reply.dmStatus)
    if hasattr(reply, "dmAuthResult"):
      result = reply.dmAuthResult
    else:
      result = None
    return Reply(status, result)
  
  def MarkMessageAsDownloaded(self, msgid):
    reply = self.soap_client.service.MarkMessageAsDownloaded(msgid)
    status = models.dmStatus(reply)
    if status.dmStatusCode == "0000":
      ok = True
    else:
      ok = False 
    return Reply(status, ok)
  
  def ConfirmDelivery(self, msgid):
    reply = self.soap_client.service.ConfirmDelivery(msgid)
    status = models.dmStatus(reply)
    if status.dmStatusCode == "0000":
      ok = True
    else:
      ok = False 
    return Reply(status, ok)
  
  def GetMessageAuthor(self, msgid):
    reply = self.soap_client.service.GetMessageAuthor(msgid)    
    status = self._extract_status(reply)
    result = dict(userType=reply.userType, authorName=reply.authorName) 
    return Reply(status, result)

    
class Client(object):

  try:
    import sudsds.transport.pyopenssl_wrapper
  except ImportError:
    CERT_LOGIN_AVAILABLE = False
  else:
    CERT_LOGIN_AVAILABLE = True

  wsdl_path = local.find_data_directory("wsdl")
  # urllib does not handle unicode strings properly 
  wsdl_path = os.path.abspath(wsdl_path)
  if os.sep == "\\":
    wsdl_path = wsdl_path.replace("\\","/")
  if not wsdl_path.startswith("/"):
    # on windows abspath does start with drive letter, not /
    wsdl_path = "/" + wsdl_path
  WSDL_URL_BASE = 'file://%s/' % wsdl_path
    
  attr2dispatcher_name = {"GetListOfSentMessages": "info",
                          "GetListOfReceivedMessages": "info",
                          "MessageDownload": "operations",
                          "MessageEnvelopeDownload": "info",
                          "DummyOperation": "operations",
                          "GetDeliveryInfo": "info",
                          "FindDataBox": "search",
                          "CreateMessage": "operations",
                          "SignedMessageDownload" : "operations",
                          "SignedSentMessageDownload" : "operations",
                          "GetSignedDeliveryInfo" : "info",
                          "GetPasswordInfo" : "access",
                          "GetOwnerInfoFromLogin": "access",
                          "GetUserInfoFromLogin": "access",
                          "ChangeISDSPassword" : "access",
                          "signature_to_message": "operations",
                          "signature_to_delivery_info": "info",
                          "AuthenticateMessage": "operations",
                          "MarkMessageAsDownloaded": "info",
                          "ConfirmDelivery": "info",
                          "GetMessageAuthor": "info",
                          }

  dispatcher_name2config = {"info": {"wsdl_name": "dm_info.wsdl",
                                     "soap_url_end": "dx"},
                            "operations": {"wsdl_name": "dm_operations.wsdl",
                                           "soap_url_end": "dz"},
                            "search": {"wsdl_name": "db_search.wsdl",
                                       "soap_url_end": "df"},
                            "access": {"wsdl_name": "db_access.wsdl",
                                       "soap_url_end": "DsManage"},
                            }
  test2soap_url = {True: {"username": "https://ws1.czebox.cz/",
                          "certificate": "https://ws1c.czebox.cz/",
                          "user_certificate": "https://ws1c.czebox.cz/",
                          "hotp": "https://www.czebox.cz/",
                          "totp": "https://www.czebox.cz/"},
                   False: {"username":"https://ws1.mojedatovaschranka.cz/",
                           "certificate": "https://ws1c.mojedatovaschranka.cz/",
                           "user_certificate":
                                    "https://ws1c.mojedatovaschranka.cz/",
                           "hotp": "https://www.mojedatovaschranka.cz/",
                           "totp": "https://www.mojedatovaschranka.cz/"}
                   }

  login_method2url_part = {"username": "DS",
                           "certificate": "cert/DS",
                           "user_certificate": "certds/DS",
                           "hotp": "apps/DS",
                           "totp": "apps/DS"
                           }
  
  otp_method2addr = {"hotp": "as/processLogin?type=hotp",
                     "totp": "as/processLogin?type=totp"}
  
  logout_url_part = "as/processLogout"



  def __init__(self, login=None, password=None, soap_url=None, test_environment=None,
               login_method="username", server_certs=None,
               client_certfile=None, client_keyfile=None,
               client_keyobj=None, client_certobj=None,
               otp_callback=None, isds_user_agent_string=None):
    """
    if soap_url is not given and test_environment is given, soap_url will be
    inferred from the value of test_environment based on what is set in test2soap_url;
    if neither soap_url not test_environment is provided, it will be empty and
    the dispatcher will use the value from WSDL;
    if soap_url id used, it will be used without regard to test_environment value
    server_certs - path to a certificate chain used for verification of server
    certificate, if None, no check on server certificate is performed
    
    client_keyfile, client_certfile - are used with login_method 'certificate'
    or 'user_certificate'
    client_keyobj, client_certobj - internal OpenSSL objects for key and certificate
    - an alternative way of providing data for login_methods 'certificate' and
    'user_certificate' 
    """
    self._cookie_jar = cookielib.CookieJar()
    self.login = login
    self.password = password
    self.client_keyfile = client_keyfile
    self.client_certfile = client_certfile
    self.client_keyobj = client_keyobj
    self.client_certobj = client_certobj
    self.login_method = login_method 
    self.otp_callback = otp_callback
    if not isds_user_agent_string:
      self.isds_user_agent_string = "dslib %s" % release.DSLIB_VERSION
    else:
      self.isds_user_agent_string = isds_user_agent_string
    # check authentication data
    if self.login_method in ("certificate","user_certificate"):
      if not self.CERT_LOGIN_AVAILABLE:
        raise ValueError("The %s login_method is not available\
 - it was not possible to import the pyopenssl_wrapper module." % login_method)
      if not (self.client_certobj or self.client_certfile):
        raise ValueError("You must supply client_certfile or client_certobj\
 when using '%s' login method" % login_method)
      if not (self.client_keyobj or self.client_keyfile):
        raise ValueError("You must supply client_keyfile or client_keyobj\
 when using '%s' login method" % login_method)
    if self.login_method in ("username","user_certificate"):
      if not self.login:
        raise ValueError("You must supply a username when using\
 '%s' login method" % login_method)
      if not self.password:
        raise ValueError("You must supply a password when using\
 '%s' login method" % login_method)
    if self.login_method in ("hotp","totp"):
      if not self.otp_callback:
        raise ValueError("You must supply otp_callback when using\
 '%s' login method" % login_method)
    # all ok - continue creating the instance attrs
    if soap_url:
      self.soap_url = soap_url
    elif test_environment != None:
      self.soap_url = Client.test2soap_url[test_environment][self.login_method]
    else:
      self.soap_url = None
    self.test_environment = test_environment
    self._dispatchers = {}
    self.server_certs = server_certs

  def login_to_server(self, repeat_otp=True):
    """Performs all steps necessary for later successful access to the server.
    It is needed by authentication method that require a cookie to be present
    when accessing the SOAP interface.
    'user_callback' is a function that would be called if the login requires some user
    input."""
    base_url = self.test2soap_url[self.test_environment][self.login_method]
    url = base_url + \
          self.otp_method2addr[self.login_method] + \
          "&uri=" + base_url + \
          self.login_method2url_part[self.login_method] + "/" + \
          self.dispatcher_name2config['operations']['soap_url_end']
    proxy_handler = ProxyManager.HTTPS_PROXY.create_proxy_handler()
    redir_handler = NoPostRedirectionHTTPRedirectHandler()
    urlopener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookie_jar),
                                     redir_handler)
    urlopener.addheaders = [('User-agent', self.isds_user_agent_string)]
    if proxy_handler:
      urlopener.add_handler(proxy_handler)
    try:
      if self.login_method == "totp":
        _url = url+"&sendSms=true"
      else:
        _url = url
      result = urlopener.open(_url, "")
    except urllib2.HTTPError as e:
      last_problem = ""
      auth_meth_req = e.headers.get("WWW-Authenticate")
      # HOTP
      if auth_meth_req == "hotp":
        req = urllib2.Request(url, "")
        while True:
          hotp = self.otp_callback(last_problem=last_problem)
          if hotp is not None:
            basic_auth = base64.b64encode(
                                 "%s:%s%s" % (self.login, self.password, hotp))
            req.add_header("Authorization", "Basic %s" % basic_auth)
            try:
              result = urlopener.open(req)
            except urllib2.HTTPError as e2:
              if e2.code == 302:
                # this is ok - we expected it
                break
              elif e2.code == 401:
                if repeat_otp:
                  last_problem = str(e2)
                else:
                  raise DSNotAuthorizedException(e2)
              else:
                raise e2
          else:
            raise DSOTPException(DSOTPException.OTP_CANCELED_BY_USER,
                                 "User did not supply an OTP")
      # TOTP
      if auth_meth_req == "totpsendsms":
        req = urllib2.Request(_url, "")
        # request an SMS to be sent using password for authentication
        basic_auth = base64.b64encode(
                             "%s:%s" % (self.login, self.password))
        req.add_header("Authorization", "Basic %s" % basic_auth)
        try:
          result = urlopener.open(req)
        except urllib2.HTTPError as e2:
          if e2.code == 302:
            # this is ok - we expected it
            pass
          elif e2.code == 401:
            raise DSNotAuthorizedException(e2)
          else:
            raise e2
        # ask for the code received via SMS
        while True:
          totp = self.otp_callback(last_problem=last_problem)
          if totp is not None:
            req = urllib2.Request(url, "")
            # make the final request obtaining the cookie
            basic_auth = base64.b64encode(
                                 "%s:%s%s" % (self.login, self.password, totp))
            req.add_header("Authorization", "Basic %s" % basic_auth)
            try:
              result = urlopener.open(req)
            except urllib2.HTTPError as e2:
              if e2.code == 302:
                # this is ok - we expected it
                break
              elif e2.code == 401:
                if repeat_otp:
                  last_problem = str(e2)
                else:
                  raise DSNotAuthorizedException(e2)
              else:
                raise e2
          else:
            raise DSOTPException(DSOTPException.OTP_CANCELED_BY_USER,
                                 "User did not supply an OTP")


  def logout_from_server(self):
    """When authentication requiring a cookie is used, we have to log out
    of the server - on app exit or whatever"""
    if self.requires_login() and len(self._cookie_jar) != 0:
      base_url = self.test2soap_url[self.test_environment][self.login_method]
      url = base_url + \
            self.logout_url_part + \
            "?uri=" + base_url + \
            self.login_method2url_part[self.login_method] + "/" + \
            self.dispatcher_name2config['operations']['soap_url_end']
      proxy_handler = ProxyManager.HTTPS_PROXY.create_proxy_handler()
      jar_copy = cookielib.CookieJar()
      for cookie in self._cookie_jar:
        jar_copy.set_cookie(cookie)
      urlopener = urllib2.build_opener(
                              urllib2.HTTPCookieProcessor(jar_copy))
      urlopener.addheaders = [('User-agent', self.isds_user_agent_string)]
      if proxy_handler:
        urlopener.add_handler(proxy_handler)
      try:
        result = urlopener.open(url, timeout=3)
      except urllib2.HTTPError as e:
        raise DSOTPException(DSOTPException.LOGOUT_NOT_POSSIBLE,
                             "Could not logout: %s" % e)
      else:
        result.close()
      

  def get_cookie_jar(self, do_login=True, force_refresh=False):
    if force_refresh:
      self._cookie_jar.clear_session_cookies()
    if do_login and self.requires_login() and len(self._cookie_jar) == 0:
      self.login_to_server()
    return self._cookie_jar
  
  def set_auth_cookie(self, cookie):
    self._cookie_jar.set_cookie(cookie)
  
  def requires_login(self):
    if self.login_method in ("hotp","totp"):
      return True
    return False

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
      this_soap_url += Client.login_method2url_part[self.login_method] + \
                       "/" + config['soap_url_end']
    dis = Dispatcher(self, Client.WSDL_URL_BASE+config['wsdl_name'],
                     soap_url=this_soap_url,
                     server_certs=self.server_certs)
    self._dispatchers[name] = dis
    return dis

   
  @classmethod
  def verify_server_certificate(cls, cert):
    """
    this is given to suds HTTPTransport augmented to checking certificates
    it should return True when certificate passes and False when not
    - we check mainly the name for which the certificate was issued
    """
    ok = False
    for parts in cert['subject']:
      # somehow 1-member tuples are used so we cycle again...
      for name, value in parts:
        if name == "organizationName" and \
           re.search(u"Ministerstv[oa] vnitra ČR", value, re.IGNORECASE):
          ok = True
          break
    return ok 

  # set this to None to omit checks or to custom function to allow custom checks
  CERT_VERIFIER = verify_server_certificate
   

class Reply(object):
  """represent a reply from the SOAP server"""

  def __init__(self, status, data, **kw):
    self.status = status
    self.data = data
    self.additional_data = {}
    self.additional_data.update(kw)

  def __unicode__(self):
    return "Reply: StatusCode: %s; DataType: %s" % (self.status.dmStatusCode, data.__class__.__name__)

  def add_addtional_data(self, **kw):
    self.add_addtional_data.update(kw)
