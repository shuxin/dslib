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

import sys
sys.path.insert(0, "../")
from dslib.client import Client
from dslib.certs.cert_manager import CertificateManager
from dslib import models


def active(f):
  """decorator to activate a test"""
  f.active = True
  return f

# ============================== Tests start here ==============================

@active
def GetListOfSentMessages():
  template = "%(dmID)-8s %(dmSender)-20s %(dmRecipient)-20s %(dmAnnotation)-20s %(dmDeliveryTime)-20s"
  heading = {"dmID":"ID",
             "dmSender":"Sender",
             "dmRecipient":"Recipient",
             "dmDeliveryTime":"DeliveryTime",
             "dmAnnotation":"Annotation",
             }
             
  print (template % heading).encode("utf-8")
  print "------------------------------------------------------------------------------------"
  reply = ds_client.GetListOfSentMessages()
  print reply
  for message in ds_client.GetListOfSentMessages().data:
    print (template % (message.__dict__)).encode("utf-8")


@active
def GetListOfReceivedMessages():
  template = "%(dmID)-8s %(dmSender)-20s %(dmRecipient)-20s %(dmAnnotation)-20s %(dmDeliveryTime)-20s"
  heading = {"dmSender":"Sender",
             "dmRecipient":"Recipient",
             "dmDeliveryTime":"DeliveryTime",
             "dmAnnotation":"Annotation",
             "dmID":"ID",
             }
             
  print (template % heading).encode("utf-8")
  print "------------------------------------------------------------------------------------"
  for message in ds_client.GetListOfReceivedMessages().data:
    print (template % (message.__dict__)).encode("utf-8")


@active
def MessageDownload():
  for envelope in ds_client.GetListOfReceivedMessages().data:
    message = ds_client.MessageDownload(envelope.dmID).data
    print "dmID:", message.dmID
    print "dmSender:", message.dmSender.encode('utf-8')
    print "dmAnnotation:", message.dmAnnotation.encode('utf-8')
    print "dmDeliveryTime:", type(message.dmDeliveryTime), message.dmDeliveryTime
    print "Attachments:"
    for f in message.dmFiles:
      print "  '%s' saved" % f.save_file("./")
    break # just the first one


@active
def MessageEnvelopeDownload():
  for envelope in ds_client.GetListOfReceivedMessages().data:
    message = ds_client.MessageEnvelopeDownload(envelope.dmID).data
    print "dmID:", message.dmID
    print "dmSender:", message.dmSender.encode('utf-8')
    print "dmAnnotation:", message.dmAnnotation.encode('utf-8')


@active
def GetDeliveryInfo():
  for envelope in ds_client.GetListOfSentMessages().data:
    message = ds_client.GetDeliveryInfo(envelope.dmID).data
    print "dmID:", message.dmID
    print "dmSender:", message.dmSender.encode('utf-8')
    print "dmAnnotation:", message.dmAnnotation.encode('utf-8')
    print "dmHash:", message.dmHash
    for event in message.dmEvents:
      print event
    print "----------------------------------------"

@active
def DummyOperation():
  print "Should be None None"
  reply = ds_client.DummyOperation()
  print "Actually is", reply.status, reply.data

@active
def FindDataBox():
  # part 1
  info = models.dbOwnerInfo()
  info.dbType = "OVM"
  info.firmName = u"Město Kladno"
  info.adZipCode = "27201"
  reply = ds_client.FindDataBox(info)
  print " * Should find one hit for Kladno"
  print (u"%-10s %-20s %-20s %-20s" % ("ID","Name","Street","City")).encode("utf-8")
  for owner in reply.data:
    print (u"%-10s %-20s %-20s %-20s" % (owner.dbID, owner.firmName, owner.adStreet, owner.adCity)).encode('utf-8')
  # part 2
  info = models.dbOwnerInfo()
  info.dbType = "OVM"
  info.firmName = u"Město"
  reply = ds_client.FindDataBox(info)
  print
  print " * Now much more hits starting with 'Město'"
  print (u"%-10s %-30s %-20s %-20s" % ("ID","Name","Street","City")).encode("utf-8")
  for owner in reply.data:
    print (u"%-10s %-30s %-20s %-20s" % (owner.dbID, owner.firmName, owner.adStreet, owner.adCity)).encode('utf-8')
  # part 3
  info = models.dbOwnerInfo()
  info.dbType = "OVM"
  info.firmName = u"Prase"
  reply = ds_client.FindDataBox(info)
  print
  print " * Should not find anything for 'Prase'"
  print "Result:", reply.data
  # part 4
  info = models.dbOwnerInfo()
  info.dbType = "OVM"
  info.dbID = u"hjyaavk"
  reply = ds_client.FindDataBox(info)
  print
  print " * Searching using dbID - should find Milotice only"
  print (u"%-10s %-30s %-20s %-20s" % ("ID","Name","Street","City")).encode("utf-8")
  for owner in reply.data:
    print (u"%-10s %-30s %-20s %-20s" % (owner.dbID, owner.firmName, owner.adStreet, owner.adCity)).encode('utf-8')
  # part 5
  info = models.dbOwnerInfo()
  info.dbType = "OVM"
  info.ic = u"00282651"
  reply = ds_client.FindDataBox(info)
  print
  print " * Searching using IC - should find Slapanice"
  print (u"%-10s %-30s %-20s %-20s" % ("ID","Name","Street","City")).encode("utf-8")
  for owner in reply.data:
    print (u"%-10s %-30s %-20s %-20s" % (owner.dbID, owner.firmName, owner.adStreet, owner.adCity)).encode('utf-8')
  
    
    
@active
def CreateMessage():
  envelope = models.dmEnvelope()
  envelope.dbIDRecipient = "4nwahuq"
  envelope.dmAnnotation = "tohle je dalsi pokus posilany z pythonu"
  dmfile = models.dmFile()
  dmfile._dmMimeType = "text/plain"
  dmfile._dmFileMetaType = "main"
  dmfile._dmFileDescr = "prilozeny_soubor_s/lomitkem/v/nazvu.txt"
  import base64
  dmfile.dmEncodedContent = base64.standard_b64encode("tohle je pokusny text v"
                                                      " pokusne priloze")
  dmfiles = [dmfile]
  reply = ds_client.CreateMessage(envelope, dmfiles)
  print reply.status
  print "Message ID is:", reply.data

@active
def GetOwnerInfoFromLogin():
  reply = ds_client.GetOwnerInfoFromLogin()
  print reply.status
  print reply.data

@active
def GetUserInfoFromLogin():
  reply = ds_client.GetUserInfoFromLogin()
  print reply.status
  print reply.data

@active
def SignedMessageDownload():
  for envelope in ds_client.GetListOfReceivedMessages().data:
    print "ID:", envelope.dmID
    reply = ds_client.SignedMessageDownload(envelope.dmID)    
    print reply.status
    print "ID matches:", reply.data.dmID, reply.data.dmID == envelope.dmID
    print "Verified message: %s" % reply.data.is_message_verified()
    print "Verified certificate: %s" % reply.data.pkcs7_data.certificates[0].is_verified()
    print reply.data.check_timestamp()
    break

@active
def SignedSentMessageDownload():
  for envelope in ds_client.GetListOfSentMessages().data:
    print "ID:", envelope.dmID
    reply = ds_client.SignedSentMessageDownload(envelope.dmID)    
    print reply.status
    print "ID matches:", reply.data.dmID, reply.data.dmID == envelope.dmID
    print "Verified message: %s" % reply.data.is_message_verified()
    print "Verified certificate: %s" % reply.data.pkcs7_data.certificates[0].is_verified()
    print "Attachments:"
    for f in reply.data.dmFiles:
      print "  Attachment '%s'" % f._dmFileDescr
    break # just the first one
  
@active
def GetSignedDeliveryInfo():  
  for envelope in ds_client.GetListOfSentMessages().data:
    print type(envelope)
    print "ID:", envelope.dmID
    reply = ds_client.GetSignedDeliveryInfo(envelope.dmID)    
    print reply.status
    print reply.data
    print "ID matches:", reply.data.dmID, reply.data.dmID == envelope.dmID
    print "Verified message: %s" % reply.data.is_verified
    print "Verified certificate: %s" % reply.data.pkcs7_data.certificates[0].is_verified()
    print "Timestamp verified: %s" % reply.data.check_timestamp()
    for event in reply.data.dmEvents:
      print "  Event", event
    f = file("dodejka.zfo","w")
    import base64
    f.write(base64.b64decode(reply.additional_data['raw_data']))
    f.close()
    break

@active
def GetPasswordInfo():
  reply = ds_client.GetPasswordInfo()
  print "Password expires: %s" %reply.data
  
@active
def ChangeISDSPassword():  
  import getpass
  old_pass = getpass.getpass("Current password:")
  new_pass = getpass.getpass("New password:")
  reply = ds_client.ChangeISDSPassword(old_pass, new_pass)
  print "%s : %s"% (reply.status.dbStatusCode, reply.status.dbStatusMessage)
  
@active
def AuthenticateMessage():
  import base64
  print "This should return None"
  reply = ds_client.AuthenticateMessage(base64.b64encode("Hello DS"))
  print "Actually is", reply.data
  print "-----------------------------------------------"
  print "This should complete successfully"
  import local
  test_dir = local.find_data_directory("test_msgs")
  f = file(os.path.join(test_dir,"AuthenticateMessage-test.txt"),"r")
  text = f.read()
  f.close()
  reply = ds_client.AuthenticateMessage(text)
  print "Actually is", reply.status
  print "Message verified successfully:", reply.data
  
@active
def MarkMessageAsDownloaded():  
  i = 0
  for envelope in ds_client.GetListOfReceivedMessages().data:
    print "ID:", envelope.dmID
    reply = ds_client.MarkMessageAsDownloaded(envelope.dmID)    
    print reply.status
    print reply.data
    i += 1
    if i > 2:
      break

@active
def ConfirmDelivery():  
  for envelope in ds_client.GetListOfReceivedMessages().data:
    print "*ID:", envelope.dmID, envelope._dmType, envelope.dmMessageStatus
    if envelope._dmType == "K" and envelope.dmMessageStatus == 4: 
      reply = ds_client.ConfirmDelivery(envelope.dmID)    
      print reply.status
      print reply.data
      break
    
@active
def GetMessageAuthor():  
  for envelope in ds_client.GetListOfReceivedMessages().data:
    print "*ID:", envelope.dmID
    reply = ds_client.GetMessageAuthor(envelope.dmID)    
    #print reply.status
    print " userType", reply.data.get('userType')
    auth_name = reply.data.get('authorName')
    if auth_name:
      print " authorName", auth_name.encode('utf-8')
    
    #break


if __name__ == "__main__":
  import logging
  #logging.basicConfig(level=logging.DEBUG)
  #logging.getLogger('suds').setLevel(logging.DEBUG)
  def otp_callback(last_problem=None):
    if last_problem:
      print last_problem
    x = raw_input("Generated code: ")
    return x
  
  def list_tests(tests):
    print "Available tests:"
    for i,test in enumerate(tests):
      print "  %2d. %s" % (i, test.__name__)
    print
    
  # get list of tests
  import sys, inspect
  tests = []
  for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
    if hasattr(f, "active") and f.active:
      tests.append(f)

  # parse options
  from optparse import OptionParser
  import os
  op = OptionParser(usage="""python %prog [options] [username] test+\n
username - the login name do DS - not given when certificate login is used
test - either a number or name of a test or 'ALL'""")
  op.add_option( "-t", action="store_true",
                 dest="test_account", default=False,
                 help="the account is a test account, not a standard one.")
  op.add_option( "-k", action="store",
                 dest="keyfile", default=None,
                 help="Client private key file to use for 'certificate' or \
'user_certificate' login methods.")
  op.add_option( "-c", action="store",
                 dest="certfile", default=None,
                 help="Client certificate file to use for 'certificate' or \
'user_certificate' login methods.")
  op.add_option( "-P", action="store",
                 dest="p12file", default=None,
                 help="Client certificate and key in a PKCS12 file\
 to use for 'certificate' or 'user_certificate' login methods.")
  op.add_option( "-p", action="store",
                 dest="proxy", default="",
                 help="address of HTTP proxy to be used\
 (use 'SYSTEM' for default system setting).")
  op.add_option( "-m", action="store",
                 dest="login_method", default="",
                 help="login method to use - defaults to 'username' or to \
'user_certificate' (when -P or -k and -c is given). \
Possible values are 'username', 'certificate' and 'user_certificate'.")
  
  
  (options, args) = op.parse_args()
  # select the login_method
  if options.p12file or (options.keyfile and options.certfile):
    login_method = options.login_method or 'user_certificate'
  else:
    login_method = options.login_method or 'username'
  if login_method == "certificate":
    username = None
    args = args[:]
  else:
    if len(args) < 1:
      list_tests(tests)
      op.error("Too few arguments - when certificates are not given,\
 username must be present.")
    else:
      username = args[0]
      args = args[1:]
  # setup proxy
  proxy = options.proxy
  if proxy == "SYSTEM":
    proxy = -1
  from dslib.network import ProxyManager
  ProxyManager.HTTPS_PROXY.set_uri(proxy)
  # read the tests
  to_run = []
  if 'ALL' in args:
    to_run = tests
  else:
    for test_name in args:
      if test_name.isdigit():
        test_id = int(test_name)
        if test_id < len(tests):
          to_run.append(tests[test_id])
        else:
          sys.stderr.write("Test %d does not exist!\n" % test_id)
      else:
        for test in tests:
          if test.__name__ == test_name:
            to_run.append(test)
            break
        else:
          sys.stderr.write("Test '%s' does not exist!\n" % test_name)
  # run the tests
  if to_run:
    # setup the client argument and attributes
    import local
    cert_dir = local.find_data_directory("trusted_certificates")
    args = dict(test_environment=options.test_account,
                server_certs=os.path.join(cert_dir, "all_trusted.pem"),
                login_method=login_method
                )
    # process specific things
    if login_method in ("certificate", "user_certificate"):
      if options.p12file:
        # PKCS12 file certificate and key storage
        import OpenSSL
        f = file(options.p12file, 'rb')
        p12text = f.read()
        f.close()
        import getpass
        password = getpass.getpass("Enter PKSC12 file password:")
        try:
          p12obj = OpenSSL.crypto.load_pkcs12(p12text, password)
        except OpenSSL.crypto.Error, e:
          a = e.args
          if type(a) in (list,tuple) and type(a[0]) in (list,tuple) and \
            type(a[0][0]) in (list,tuple) and e.args[0][0][2] == 'mac verify failure':
            print "Wrong password! Exiting."
            sys.exit()
        except Exception, e:
          print "Error:", e
          sys.exit()
        login_method = options.login_method or 'user_certificate'
        args.update(client_certobj=p12obj.get_certificate(),
                    client_keyobj=p12obj.get_privatekey())
      elif options.keyfile and options.certfile:
        # PEM file certificate and key storage
        args.update(client_certfile=options.certfile,
                    client_keyfile=options.keyfile)
      else:
        # no certificates were given
        sys.stderr.write("For login method '%s' certificate (either -P or -k \
and -c) is needed!\n" % login_method)
        sys.exit(101)
    if login_method in ("username", "user_certificate", "hotp", "totp"):
      # username and password login
      # try to find a stored password
      passfile = "./.isds_password"
      if os.path.exists(passfile):
        print "Using password from '%s'" % passfile
        password = file(passfile,'r').read().strip()
      else:
        import getpass
        password = getpass.getpass("Enter login password:")
      args.update(login=username, password=password)
      if login_method in ("hotp", "totp"):
        args.update(otp_callback=otp_callback)
    CertificateManager.read_trusted_certificates_from_dir("trusted_certificates")
    # create the client      
    ds_client = Client(**args)
    # run the tests
    for test in to_run:
      print "==================== %s ====================" % test.__name__
      # if testing password change, pass current password      
      test()
      print "==================== end of %s ====================" % test.__name__  
      print
      print
    ds_client.logout_from_server()
  else:
    list_tests(tests)
    print op.get_usage()

