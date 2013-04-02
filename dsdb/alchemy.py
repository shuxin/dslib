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

# standard library imports
import json
import base64
import thread

# third party imports
import sqlalchemy as sal
import sqlalchemy.orm as salorm
from sqlalchemy.sql import between
from sqlalchemy.engine import reflection

# dslib imports
from dslib.client import Client
from dslib.models import Message, dmFile, dmHash, dmEvent
from dslib.pkcs7_models import PKCS7_data
from dslib.certs.cert_manager import CertificateManager

# local imports
from abstract import AbstractDSDatabase

MESSAGE_TYPE_RECEIVED = 1
MESSAGE_TYPE_SENT = 2

class Binding(object):

  model = None
  table_name = None
  columns = []
  indexes = []

  def __init__(self):
    self.table = None

  def create_table(self, engine, metadata):
    self.table = sal.Table(self.table_name, metadata, *self.get_columns())
    self.create_indexes(engine)
    metadata.create_all(engine)

  def bind_model(self, map_props=None):
    if self.model:
      if map_props is None:
        map_props = {}
      salorm.mapper(self.model, self.table, properties=map_props)

  def create_indexes(self, engine):
      for idx_name, idx_cols in self.indexes:
          i = sal.Index(idx_name,
                        *[getattr(self.table.c, col) for col in idx_cols])
          insp = reflection.Inspector.from_engine(engine)
          indexes = insp.get_indexes(self.table_name)
          print indexes
          for index in indexes:
              if index.get('name') == idx_name:
                  break
          else:
              i.create(engine)


class MessageBinding(Binding):

  _type_map = {"dmPersonalDelivery": sal.Boolean,
               "dmAllowSubstDelivery": sal.Boolean,
               "dmAttachmentSize": sal.Integer,
               "dmMessageStatus": sal.Integer,
               "dmSenderType": sal.Integer,
               "dmDeliveryTime": sal.DateTime,
               "dmAcceptanceTime": sal.DateTime}

  model = Message
  table_name = 'messages'
  indexes = [("idx_messages_deltime", ("dmDeliveryTime",))]

  @classmethod
  def get_columns(cls):
    return [sal.Column('dmID', sal.Integer, primary_key=True),
            sal.Column('is_verified', sal.Boolean),
            sal.Column('_origin', sal.Text)
            ] + \
            [sal.Column(name, cls._type_map.get(name, sal.Text), nullable=True)
             for name in Message.KNOWN_ATTRS
             if name != 'dmID' and name not in Message.ATTR_TO_TYPE and name != 'dmHash']


class dmFileBinding(Binding):

  model = dmFile
  table_name = 'files'
  indexes = [("idx_files_msgid", ("message_id",))]

  @classmethod
  def get_columns(cls):
    return [sal.Column('id', sal.Integer, primary_key=True),
            sal.Column('message_id', sal.Integer, sal.ForeignKey("messages.dmID"))] + \
            [sal.Column(name, sal.Text, nullable=True)
             for name in cls.model.KNOWN_ATTRS]


class dmHashBinding(Binding):

  model = dmHash
  table_name = 'hashes'
  indexes = [("idx_hashes_msgid", ("message_id",))]

  @classmethod
  def get_columns(cls):
    return [sal.Column('id', sal.Integer, primary_key=True),
            sal.Column('message_id', sal.Integer, sal.ForeignKey("messages.dmID"))] + \
            [sal.Column(name, sal.Text, nullable=True)
             for name in cls.model.KNOWN_ATTRS]

class dmEventBinding(Binding):

  model = dmEvent
  table_name = 'events'
  indexes = [("idx_events_msgid", ("message_id",))]
  
  @classmethod
  def get_columns(cls):
    return [sal.Column('id', sal.Integer, primary_key=True),
            sal.Column('message_id', sal.Integer, sal.ForeignKey("messages.dmID"))] + \
            [sal.Column(name, sal.Text, nullable=True)
             for name in cls.model.KNOWN_ATTRS]

# ---- Additional models and bindings not inherited from dslib ----

class RawMessageData(object):

  def __init__(self, dmID, message_type, data):
    self.message_id = dmID
    self.message_type = message_type
    self.data = data

class RawMessageDataBinding(Binding):

  model = RawMessageData
  table_name = 'raw_message_data'
  @classmethod
  def get_columns(cls):
    return [sal.Column('message_id', sal.Integer,
                       sal.ForeignKey("messages.dmID"), primary_key=True),
            sal.Column('message_type', sal.Integer),
            sal.Column('data', sal.Text)]

# delivery info data

class RawDeliveryInfoData(object):

  def __init__(self, dmID, data):
    self.message_id = dmID
    self.data = data

class RawDeliveryInfoDataBinding(Binding):

  model = RawDeliveryInfoData
  table_name = 'raw_delivery_info_data'
  @classmethod
  def get_columns(cls):
    return [sal.Column('message_id', sal.Integer,
                       sal.ForeignKey("messages.dmID"), primary_key=True),
            sal.Column('data', sal.Text)]


class SupplementaryMessageData(object):

  def __init__(self, dmID, type=MESSAGE_TYPE_RECEIVED,
               read_locally=False, data=None, download_date=None):
    self.message_id = dmID
    self.message_type = type
    self.read_locally = read_locally
    self.download_date = download_date
    self.custom_data = data

  def set_custom_data(self, data):
    self.custom_data = json.dumps(data)

  def get_custom_data(self):
    if self.custom_data:
      return json.loads(self.custom_data)
    return {}

class SupplementaryMessageDataBinding(Binding):

  model = SupplementaryMessageData
  table_name = 'supplementary_message_data'
  indexes = [("idx_supplementary_message_data_msgtype", ("message_type",))]

  @classmethod
  def get_columns(cls):
    return [sal.Column('message_id', sal.Integer,
                       sal.ForeignKey("messages.dmID"), primary_key=True),
            sal.Column('message_type', sal.Integer),
            sal.Column("read_locally", sal.Boolean),
            sal.Column("download_date", sal.DateTime),
            sal.Column('custom_data', sal.Text), # in JSON format
            ]

class CertificateData(object):

  def __init__(self, der_data, id=None):
    self.id = id
    self.der_data = base64.b64encode(der_data)

  def get_der_data(self):
    return base64.b64decode(self.der_data)

class CertificateDataBinding(Binding):

  model = CertificateData
  table_name = 'certificate_data'
  @classmethod
  def get_columns(cls):
    return [sal.Column('id', sal.Integer, primary_key=True),
            sal.Column('der_data', sal.Text, unique=True)]

class MessageToCertificateData(Binding):

  table_name = 'message_certificate_data'
  indexes = [("idx_message_certificate_data_msgid", ("message_id",))]
  
  @classmethod
  def get_columns(cls):
    return [sal.Column('message_id', sal.Integer, sal.ForeignKey('messages.dmID')),
            sal.Column('certificate_id', sal.Integer,
                       sal.ForeignKey('certificate_data.id'))]

# ----- The database itself -----

def thread_safe_session(f):
  def new(obj, *args, **kw):
    if thread.get_ident() != obj._session_thread:
      # session is not thread safe, especially with sqlite
      # we switch sessions when different thread is detected
      obj._close_session()
      obj._new_session()
    ret = f(obj, *args, **kw)
    return ret
  return new

class DSDatabase(AbstractDSDatabase):

  DEBUG = False

  binding_cls = [MessageBinding, dmFileBinding, dmHashBinding,
                 dmEventBinding, RawMessageDataBinding,
                 RawDeliveryInfoDataBinding,
                 SupplementaryMessageDataBinding, CertificateDataBinding,
                 ]

  def __init__(self):
    super(DSDatabase, self).__init__()
    self.engine = None
    self.session = None
    self.metadata = None
    self.bindings = [bcls() for bcls in self.binding_cls]
    self.mess_to_cert = MessageToCertificateData()
    self._supp_data_cache = {}


  def open_database(self, filename=None):
    """should open the database. Filename is the name of the sqlite db"""
    self.metadata = sal.MetaData()
    if filename:
      self.engine = sal.create_engine('sqlite:///%s' % filename, echo=self.DEBUG)
    else:
      self.engine = sal.create_engine('sqlite:///:memory:', echo=self.DEBUG)
    for binding in self.bindings:
      binding.create_table(self.engine, self.metadata)
    self.mess_to_cert.create_table(self.engine, self.metadata)
    for binding in self.bindings:
      if isinstance(binding, MessageBinding):
        props = {'certificate_data': salorm.relation(CertificateData,
                                          secondary=self.mess_to_cert.table,
                                          backref="messages")}
      else:
        props = None
      binding.bind_model(map_props=props)
    self._new_session()

  def _new_session(self):
    self.session = salorm.sessionmaker(bind=self.engine)()
    self._session_thread = thread.get_ident()

  def _close_session(self):
    self.session.close()
    self.session = None

  def close_database(self):
    sal.orm.clear_mappers()
    self.engine.dispose()

  @thread_safe_session
  def list_message_ids(self):
    for id in self.session.query(Message.dmID).all():
      yield id[0]

  @thread_safe_session
  def all_messages(self):
    for m in self.messages_between_dates(None, None):
      yield m


  @thread_safe_session
  def store_message(self, message, raw_data=None,
                    typ=None, read_locally=None, custom_data=None):
    # translate type from string if needed
    self.session.expunge_all()
    if typ != None:
      if typ == "received":
        typ = MESSAGE_TYPE_RECEIVED
      elif typ == "sent":
        typ = MESSAGE_TYPE_SENT
    # check if message already exists
    if self.has_message(message.dmID):
      self.remove_message(message.dmID)
    # store certificate data
    if hasattr(message, 'pkcs7_data') and message.pkcs7_data:
      message.certificate_data = []
      for certificate in message.pkcs7_data.certificates:
        if hasattr(certificate, "raw_der_data") and certificate.raw_der_data:
          data = base64.b64encode(certificate.raw_der_data)
          cd = self.session.query(CertificateData).filter_by(der_data=data).first()
          if not cd:
            cd = CertificateData(certificate.raw_der_data)
          message.certificate_data.append(cd)
    # store message
    self.session.merge(message)
    # store additional models associated with the message
    for o in message.dmFiles + message.dmEvents + [message.dmHash]:
      if o:
        o.message_id = message.dmID
        self.session.add(o)
    # store raw data
    if raw_data:
      rd = RawMessageData(message.dmID, typ, raw_data)
      self.session.add(rd)
    # store supplementary data
    if typ != None or read_locally != None or custom_data != None:
      sd = self.session.query(SupplementaryMessageData).\
            filter_by(message_id=id).first()
      if not sd:
        sd = SupplementaryMessageData(message_id.dmID)
      if typ != None:
        sd.message_type = typ
      if read_locally != None:
        sd.read_locally = read_locally
      if custom_data != None:
        sd.set_custom_data(custom_data)
      self.session.add(sd)
    # commit the data
    self.session.commit()

  @thread_safe_session
  def get_message(self, id, omit_relations=False):
    """return message by its id"""
    m, sup = self.session.query(Message, SupplementaryMessageData).\
                filter(Message.dmID == SupplementaryMessageData.message_id).\
                filter(Message.dmID == int(id)).first()
    if sup:
      m.message_type = sup.message_type
      m.read_locally = sup.read_locally
    if m and not omit_relations:
      m.dmFiles = [f for f in self.session.query(dmFile).filter_by(message_id=id)]
      m.dmHash = self.session.query(dmHash).filter_by(message_id=id).first()
      m.dmEvents = [e for e in self.session.query(dmEvent).filter_by(message_id=id)]
    if m:
      self.add_pkcs7_data(m)
    return m

  @thread_safe_session
  def messages_between_dates(self, from_date, to_date,
                             message_type=None, add_pkcs7_data=False):
    """generator yielding messages with dmDeliveryTime between certain dates"""
    query = self.session.query(Message, SupplementaryMessageData).\
                filter(Message.dmID == SupplementaryMessageData.message_id)
    if message_type:
        query = query.filter(SupplementaryMessageData.message_type == message_type)
    if to_date and not from_date:
      ms = query.filter(Message.dmDeliveryTime < to_date)
    elif from_date and not to_date:
      ms = query.filter(Message.dmDeliveryTime > from_date)
    elif from_date and to_date:
      ms = query.filter(between(Message.dmDeliveryTime, from_date, to_date))
    else:
      ms = query
    for m, supp in ms:
      m.read_locally = supp.read_locally
      m.message_type = supp.message_type
      if add_pkcs7_data:
        self.add_pkcs7_data(m)
      yield m

  @thread_safe_session
  def get_messages_between_dates(self, from_date, to_date,
                                 message_type=None, add_pkcs7_data=False):
    """return messages with dmDeliveryTime between certain dates"""
    ret = list(self.messages_between_dates(from_date, to_date, message_type,
                                           add_pkcs7_data))
    return ret

  @thread_safe_session
  def get_messages_without_date(self, message_type=None, add_pkcs7_data=False):
    """return messages with empty dmDeliveryTime"""
    query = self.session.query(Message, SupplementaryMessageData).\
              filter(Message.dmID == SupplementaryMessageData.message_id).\
              filter(Message.dmDeliveryTime == None)
    if message_type:
      query = query.filter(SupplementaryMessageData.message_type == message_type)
    ret = []
    for m, supp in query:
      m.read_locally = supp.read_locally
      m.message_type = supp.message_type
      if add_pkcs7_data:
        self.add_pkcs7_data(m)
      ret.append(m)
    return ret

  @thread_safe_session
  def add_pkcs7_data(self, message):
    p = PKCS7_data()
    p.certificates = [CertificateManager.get_certificate_from_der(c.get_der_data())\
                      for c in message.certificate_data]
    message.pkcs7_data = p

  @thread_safe_session
  def add_delivery_info_data(self, mid, delivery_info, raw_data=None):
    """merges additional data from delivery info into the message
    and stores raw data into the database if given"""
    if raw_data:
      rd = RawDeliveryInfoData(mid, data=raw_data)
      self.session.add(rd)
      self.session.commit()
    for old_event in self.session.query(dmEvent).filter_by(message_id=mid):
      self.session.delete(old_event)
    for event in delivery_info.dmEvents:
      event.message_id = mid
      self.session.add(event)
    self.session.commit()

  @thread_safe_session
  def has_message(self, id):
    assert self.session
    return bool(self.session.query(Message).get(int(id)))

  @thread_safe_session
  def has_raw_data(self, id):
    assert self.session
    return bool(self.session.query(RawMessageData).get(int(id)))

  @thread_safe_session
  def has_raw_delivery_info_data(self, id):
    assert self.session
    return bool(self.session.query(RawDeliveryInfoData).get(int(id)))

  @thread_safe_session
  def remove_message(self, id):
    for m in self.session.query(Message).filter_by(dmID=int(id)):
      self.session.delete(m)
    for cls in dmFile, dmHash, dmEvent, RawMessageData, RawDeliveryInfoData:
      for m in self.session.query(cls).filter_by(message_id=int(id)):
        self.session.delete(m)
    self.session.commit()

  @thread_safe_session
  def store_raw_data(self, rd):
    self.session.add(rd)
    self.session.commit()

  @thread_safe_session
  def get_message_from_raw_data(self, id, client):
    rd = self.get_raw_data(id)
    if rd.message_type == MESSAGE_TYPE_RECEIVED:
      method = "SignedMessageDownload"
    else:
      method = "SignedSentMessageDownload"
    message = client.signature_to_message(rd.data, method)
    return message

  @thread_safe_session
  def get_delivery_info_from_raw_data(self, id, client):
    rd = self.get_raw_delivery_info_data(id)
    method = "GetSignedDeliveryInfo"
    di = client.signature_to_delivery_info(rd.data, method)
    return di

  @thread_safe_session
  def get_raw_data(self, id):
    rd = self.session.query(RawMessageData).get(id)
    if not rd:
      raise ValueError("RawMessageData with id '%d' does not exist." % id)
    return rd

  @thread_safe_session
  def get_raw_delivery_info_data(self, id):
    rd = self.session.query(RawDeliveryInfoData).get(id)
    if not rd:
      raise ValueError("RawDeliveryInfoData with id '%d' does not exist." % id)
    return rd

  @thread_safe_session
  def store_supplementary_data(self, sd):
    self.session.add(sd)
    self.session.commit()

  @thread_safe_session
  def has_supplementary_data(self, id):
    assert self.session
    return bool(self.session.query(SupplementaryMessageData).get(int(id)))

  @thread_safe_session
  def get_supplementary_data(self, id):
    return self.session.query(SupplementaryMessageData).get(int(id))

  @thread_safe_session
  def get_unique_senders(self):
    ret = list(self.session.query(Message.dbIDSender, Message.dmSender,
                                  Message.dmSenderAddress)\
               .join(SupplementaryMessageData)\
               .filter_by(message_type=MESSAGE_TYPE_RECEIVED)\
               .distinct())
    return ret

  @thread_safe_session
  def get_unique_recipients(self):
    ret = list(self.session.query(Message.dbIDRecipient, Message.dmRecipient,
                                  Message.dmRecipientAddress)\
               .join(SupplementaryMessageData)\
               .filter_by(message_type=MESSAGE_TYPE_SENT)\
               .distinct())
    return ret

  @thread_safe_session
  def mark_messages_as_read_locally(self, mids):
    """mids is a list of message ids that should be marked as read_locally"""
    #ex = sal.update(SupplementaryMessageData)\
    #        .where(SupplementaryMessageData.message_id.in_(mids))\
    #        .values(read_locally=True)
    self.session.query(SupplementaryMessageData)\
      .filter(SupplementaryMessageData.message_id.in_(mids))\
      .update({"read_locally": True}, synchronize_session=False)
    self.session.commit()
