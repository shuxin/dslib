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
This module hosts classes that reflect objects used in the
DS SOAP interface.
The purpose of these classes is to provide further functionality,
such as serialization, etc.
"""

import logging
import os
import constants
import pkcs7
import base64
import datetime
from properties.properties import Properties as props

from pkcs7_models import *

class Model(object):

  KNOWN_ATTRS = ()
  ATTR_TO_TYPE = {}

  def __init__(self, soap_message=None, xml_document=None):
    self._init_default()    
    if soap_message:
      self._load_from_soap(soap_message)
    if xml_document is not None:
      self._load_from_xml_document(xml_document)


  def __unicode__(self):
    ret = u"%s:" % self.__class__.__name__
    for a in self.__class__.KNOWN_ATTRS:
      ret += u"\n  %s: %s" % (a, unicode(getattr(self, a)))
    return ret

  def __str__(self):
    return unicode(self).encode('utf-8')

  # ---------- private methods ----------

  def _init_default(self):
    for attr in self.__class__.KNOWN_ATTRS:
      if attr in self.__class__.ATTR_TO_TYPE:
        value = self.__class__.ATTR_TO_TYPE[attr]()
      else:
        value = None
      setattr(self, attr, value)
  


  def _load_from_soap(self, soap):
    _origin = soap.__class__.__name__
    for a in self.__class__.KNOWN_ATTRS:
      parent = soap
      self._load_one_attr(parent, a)

  
  def _load_one_attr(self, parent, attr):
    if hasattr(parent, attr):
      value = getattr(parent, attr)
      # some hardcoded stuff
      typ = value.__class__.__name__
      if typ == "tEventsArray":
        if type(value.dmEvent) == list:
          todo = value.dmEvent
        else:
          todo = [value.dmEvent]
        values = [dmEvent(child) for child in todo]
        setattr(self, attr, values)
      elif typ == "tFilesArray":
        values = [dmFile(child) for child in value.dmFile]
        setattr(self, attr, values)
      elif typ == "dmHash":
        setattr(self, attr, dmHash(value))
      else:
        setattr(self, attr, self._decode_soap_value(value))
    else:
      logging.debug("Attribute %s not present in %s", attr, parent.__class__.__name__)
    

  def _decode_soap_value(self, soap):
    """take a value as returned by SOAP and return a more suitable one;
    for example suds uses a class for text, so we translate to normal
    unicode string here"""
    if soap.__class__.__name__ == "Text":
      return unicode(soap)
    return soap


  def copy_to_soap_object(self, soap):
    for attr in self.KNOWN_ATTRS:
      value = getattr(self, attr)
      if value != None:
        # we do not copy default empty values
        self._set_one_attr(soap, attr, value)


  def _set_one_attr(self, soap, attr, value):
##     if attr == "dmFiles":
##       for child in value:
##         soap_child = dmFile()
##         child.copy_to_soap_object(soap_child)
    setattr(soap, attr, value)
  
  '''
  Returns value of xml attribute
  '''
  def _get_attribute_value(self, xml_attribute):
      return xml_attribute.getValue()
  
  '''
  Returns text value of child node 
  '''
  def _get_child_text_value(self, xml_child):
      return xml_child.text
  
  
  def _load_one_xml_att(self, parent, attr):
      
      if attr[0] == '_':
          entity = parent.attrib(attr[1:])
      else:
          entity = parent.getChild(attr)
          
      if entity is not None:
          if attr[0] == '_':
              value = self._get_attribute_value(entity)
          else:
              value = self._get_child_text_value(entity)
          
          if (attr == "dmFiles"):
              files = entity.getChildren()
              values = [dmFile(xml_document=file) for file in files]
              for file in files:
                  s = dmFile(xml_document=file)
              setattr(self, attr, values)
          elif (attr == "dmEvents"):
              events = entity.getChildren()
              values = [dmEvent(xml_document=event) for event in events]
              setattr(self, attr, values)
          elif (attr == "dmHash"):
              x = dmHash(xml_document=entity)
              setattr(self, attr, dmHash(xml_document=entity))              
          else:
              setattr(self, attr, value)          
      else:
          logging.debug("Attribute %s not present in %s", attr, parent.text)
    
    
  def _load_from_xml_document(self, xml_doc, root_name=None):      
      for a in self.__class__.KNOWN_ATTRS:
          parent = xml_doc
          self._load_one_xml_att(parent, a)
          

class Message(Model):
  """reflection of the DS message, which could be a result from
  several SOAP calles, namely: MessageDownload, MessageEnvelopeDownload,
  GetListOfSentMessages and GetListOfReceivedMessages"""

  KNOWN_ATTRS = ("dmID", "dbIDSender", "dmSender", "dmSenderAddress",
                 "dmSenderType", "dmRecipient", "dmRecipientAddress",
                 "dmAmbiguousRecipient", "dmSenderOrgUnit", "dmSenderOrgUnitNum",
                 "dbIDRecipient", "dmRecipientOrgUnit", "dmRecipientOrgUnitNum",
                 "dmToHands", "dmAnnotation", "dmRecipientRefNumber",
                 "dmSenderRefNumber", "dmRecipientIdent", "dmSenderIdent",
                 "dmLegalTitleLaw", "dmLegalTitleYear", "dmLegalTitleSect",
                 "dmLegalTitlePar", "dmLegalTitlePoint", "dmPersonalDelivery",
                 "dmAllowSubstDelivery", "dmFiles",
                 "dmHash", "dmQTimestamp", "dmDeliveryTime", "dmAcceptanceTime",
                 "dmMessageStatus", "dmAttachmentSize", "dmEvents", "_dmType"
                 )

  ATTR_TO_TYPE = {"dmFiles":list, "dmEvents":list}

  # attributes of message returned outside in case of MessageEnvelopeDownload,
  # MessageDownload, GetDeliveryInfo
  OUTSIDE_ATTRS = ("dmDeliveryTime","dmAcceptanceTime","dmMessageStatus",
                   "dmAttachmentSize","dmHash","dmQTimestamp","dmEvents", "_dmType")

  # origins in which some info (described above in OUTSIDE_ATTRS) is placed outside
  SPLIT_ORIGINS = ("dmReturnedMessageEnvelope","dmReturnedMessage",
                   "tReturnedMessageEnvelope","tReturnedMessage",
                   "dmDelivery","tDelivery")
  
  # origins which provide a complete message
  COMPLETE_ORIGINS = ('dmReturnedMessage','tReturnedMessage')
  
  SIG_DELIVERY_CONTENT_PATH = "GetDeliveryInfoResponse/dmDelivery"
  
  SIG_MESSAGE_CONTENT_PATH =  "MessageDownloadResponse/dmReturnedMessage" 
  
  # has meaning only if msg contains pkcs7_data
  is_verified = None
  # all PKCS7 data are stored in pkcs7_data attribute
  pkcs7_data = None
  
  # is message qtimestamp verified?
  tstamp_verified = False
  # TSTInfo - response obtained by signer (MVCR) from TSA (postsignum)
  # at the time when data message was created
  tstamp_token = None
  
  # if the message has dmQTimestamp, messageImprint value from Timestamtoken
  # contained in Qtimestamp as content, must be the same as the dmHash value
  qts_imprint_matches_hash = False
    
  def __init__(self, soap_message=None, xml_document=None, path_to_content=None):
    if (xml_document is not None) and (path_to_content is None):
        raise Exception("Must specify path to the content of message!")
    self.content_path = path_to_content    
    Model.__init__(self, soap_message, xml_document)

    # ---------- public methods ----------

  def get_origin(self):
    """returns a string describing from which SOAP call this Message comes;
    this could be used to determine which parts are (or should be) present."""
    return self._origin

  def get_status_description(self):
    return constants.MESSAGE_STATUS.get(self.dmMessageStatus, u"neznámy")
  
  def has_PKCS7_data(self):
      if self.pkcs7_data:
          return True
      else:
          return False

  def message_verification_attempted(self):
    if self.is_verified == None:
      return False
    return True
        
  def is_message_verified(self):
    return self.is_verified
  
  def is_signature_verified(self, ignore_missing_crl_check=False):
    """was the certificate used for signing the message verified"""
    if hasattr(self, "pkcs7_data") and hasattr(self.pkcs7_data, "certificates"):
      if self.pkcs7_data.certificates:
        if hasattr(self.pkcs7_data.certificates[0], "is_verified"):
          if type(self.pkcs7_data.certificates[0].is_verified) == bool:
            return self.pkcs7_data.certificates[0].is_verified
          else:
            return self.pkcs7_data.certificates[0].\
                      is_verified(ignore_missing_crl_check=ignore_missing_crl_check)
    return False

  def was_signature_valid_at_date(self, date, ignore_missing_crl_check=False):
    if hasattr(self, "pkcs7_data") and hasattr(self.pkcs7_data, "certificates"):
      if self.pkcs7_data.certificates:
        if hasattr(self.pkcs7_data.certificates[0], "valid_at_date"):
          return self.pkcs7_data.certificates[0].\
                    valid_at_date(date,
                                  ignore_missing_crl_check=ignore_missing_crl_check)
    return False

  def check_timestamp(self):
    '''
    Checks message timestamp - parses and verifies it. TimeStampToken
    is attached to the message.    
    Method returns flag that says, if the content of messages's dmHash element
    is the same as the message imprint
    '''
    # if message had dmQtimestamp, parse and verify it
    if self.dmQTimestamp is not None:
      if not self.tstamp_token:
        self._add_tstamp_token()
      if self.tstamp_token:
        imprint = self.tstamp_token.msgImprint.imprint
        imprint = base64.b64encode(imprint)
        hashFromMsg = self.dmHash.value
        if hashFromMsg == imprint:
          logging.info("Message imprint in timestamp and dmHash value are the same")
          return True
        else:
          logging.error("Message imprint in timestamp and dmHash value differ!")
          return False
    return None

  def _add_tstamp_token(self):
    if self.dmQTimestamp is not None:
      tstamp_verified, tstamp = pkcs7.tstamp_helper\
                                      .parse_qts(self.dmQTimestamp,\
                                                 verify=props.VERIFY_TIMESTAMP)
      self.tstamp_token = tstamp

  def get_verification_date(self):
    """returns the timestamp date or current date, depending on the
    availability of the timestamp"""
    return datetime.datetime.now()
    # we do not use the timestamp yet - it is unclear if it can be used
    if not self.tstamp_token:
      # we approximate because the parsing of timestamp is expensive
      return datetime.datetime.now()
    else:
      return self.tstamp_token.get_genTime_as_datetime()

  def still_on_server(self):
    if not self.dmDeliveryTime:
      return None
    now = datetime.datetime.now()
    return (now - self.dmDeliveryTime).days < 90
  
  def is_complete(self):
    """returns True if the message origin is amongst origins considered
     complete, False otherwise"""
    return self.get_origin() in self.COMPLETE_ORIGINS
  
  def get_sender_type(self):
    if not self.dmSenderType:
      return ""
    return constants.ORG_TYPE_NUM_TO_TEXT.get(self.dmSenderType,
                                              str(self.dmSenderType))

  # ---------- private methods ----------

  # overrides the Model._load_from_soap
  def _load_from_soap(self, soap):
    _origin = soap.__class__.__name__
    for a in Message.KNOWN_ATTRS:
      if a in Message.OUTSIDE_ATTRS or _origin not in Message.SPLIT_ORIGINS:
        # get it directly
        parent = soap
      else:
        parent = soap.dmDm
      self._load_one_attr(parent, a)
    self._origin = _origin
    
  def _load_from_xml_document(self, xml_doc):
    # split path to content by /
    parts = self.content_path.split('/')
    root = xml_doc
    # go down the xml tree to reach the start of "message envelope"
    for part in parts:
        root = root.getChild(part)
        if root is None:
            raise Exception("Could not reach the message content node, check specified path to the content")

    for a in Message.KNOWN_ATTRS:
        if a in Message.OUTSIDE_ATTRS: 
            parent = root
        else:
            parent = root.getChild("dmDm")
        self._load_one_xml_att(parent, a)


class dmFile(Model):
  """this class corresponds to the SOAP dmFile class"""

  KNOWN_ATTRS = ("_dmFileDescr","_dmUpFileGuid","_dmFileGuid","_dmMimeType","_dmFormat",
                 "_dmFileMetaType","dmEncodedContent")

  import os
  import base64

  def get_decoded_content(self):
    import base64
    return base64.standard_b64decode(self.dmEncodedContent)

  def get_size(self):
    """just approximate it"""
    return int(6.0 * len(self.dmEncodedContent) / 8)

  def save_file(self, dir, fname=None):
    """if fname is null, the one in the file_obj will be used"""
    if not fname:
      fname = self._dmFileDescr
    fullname = os.path.join(dir, fname)
    outf = file(fullname, "wb")
    outf.write(self.get_decoded_content())
    outf.close()
    return fullname
    
class dmFiles(Model):

  KNOWN_ATTRS = ("dmFile",)
  ATTR_TO_TYPE = {"dmFile":list}
          

class dmEvent(Model):
  """corresponds to dmEvent SOAP class"""

  KNOWN_ATTRS = ("dmEventTime", "dmEventDescr")



class dmStatus(Model):
  """corresponds to dmStatus SOAP class"""

  KNOWN_ATTRS = ("dmStatusCode", "dmStatusMessage")


class dbStatus(Model):
  """corresponds to dmStatus SOAP class"""

  KNOWN_ATTRS = ("dbStatusCode", "dbStatusMessage")


class dmHash(Model):
  """corresponds to dmHash SOAP class"""

  KNOWN_ATTRS = ("value", "_algorithm")

  '''
  Override Model _load>from_xml_document
  '''
  def _load_from_xml_document(self, xml_doc):
      self.value = xml_doc.text
      self._load_one_xml_att(xml_doc, "_algorithm")

class dmEnvelope(Model):

  KNOWN_ATTRS = ("dmSenderOrgUnit", "dmSenderOrgUnitNum", "dbIDRecipient",
                 "dmRecipientOrgUnit", "dmRecipientOrgUnitNum", "dmToHands",
                 "dmAnnotation", "dmRecipientRefNumber",
                 "dmSenderRefNumber", "dmRecipientIdent", "dmSenderIdent",
                 "dmLegalTitleLaw", "dmLegalTitleYear", "dmLegalTitleSect",
                 "dmLegalTitlePar", "dmLegalTitlePoint",
                 "dmPersonalDelivery", "dmAllowSubstDelivery", "dmOVM",
                 "_dmType", "dmPublishOwnID")
  
  
class dbOwnerInfo(Model):

  KNOWN_ATTRS = ("dbID", "dbType", "ic", "pnFirstName", "pnMiddleName", "pnLastName",
                 "pnLastNameAtBirth", "firmName", "biDate", "biCity", "biCounty",
                 "biState", "adCity", "adStreet", "adNumberInStreet", "adNumberInMunicipality",
                 "adZipCode", "adState", "nationality", "identifier", "registryCode",
                 "dbState", "dbEffectiveOVM", "dbOpenAddressing")

class dbUserInfo(Model):
  KNOWN_ATTRS = ("pnFirstName", "pnMiddleName", "pnLastName","pnLastNameAtBirth",
                 "adCity", "adStreet", "adNumberInStreet", "adNumberInMunicipality",
                 "adZipCode", "adState", "biDate", "userID", "userType", "userPrivils",
                 "ic", "firmName", "caStreet", "caCity", "caZipCode")
