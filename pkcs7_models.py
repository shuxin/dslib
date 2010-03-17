
#*    dslib - Python library for Datove schranky
#*    Copyright (C) 2009-2010  CZ.NIC, z.s.p.o. (http://www.nic.cz)
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

'''
Created on Dec 11, 2009

'''

from pkcs7.asn1_models.tools import *
from pkcs7.asn1_models.oid import *
from pkcs7.asn1_models.tools import *
from pkcs7.asn1_models.X509_certificate import *
from pkcs7.asn1_models.certificate_extensions import *
from pkcs7.debug import *
from certs.cert_manager import CertificateManager
import datetime, time


#class SignedData():    
'''
Represents SignedData object.
Attributes:
- version
- digest_algorithms
- message
'''
'''
def __init__(self, signed_data):
    self.version = signed_data.getComponentByName("version")        
    self.digest_algorithms = self._extract_used_digest_algs(signed_data)
    self.message = signed_data.getComponentByName("content").getComponentByName("signed_content").getContentValue()                 

def _extract_used_digest_algs(self, signed_data):
    used_digests = signed_data.getComponentByName("digestAlgs")
    result = []
    for used_digest in used_digests:           
        algorithm_key = tuple_to_OID(used_digest.getComponentByName("algorithm")._value)
        result.append(algorithm_key)  
    return result
'''
    
class Name():
    '''
    Represents Name (structured, tagged).
    This is a dictionary. Keys are types of names (their OIDs), value is the value.
    String representation: "1.2.3.5=>CZ, 2.3.6.5=>Ceska posta..."
    Oids are in oid_map, in module oid
    '''
    def __init__(self, name):
        self.__attributes = {}
        for name_part in name:
            for attr in name_part:
                type = str(attr.getComponentByPosition(0).getComponentByName('type'))                
                value = str(attr.getComponentByPosition(0).getComponentByName('value'))
                self.__attributes[type] = value 
        self.__attributes.keys().sort()       
    
    def __str__(self):        
        result = ''
        self.__attributes.keys().sort()
        for key in self.__attributes.keys():
            result += key
            result += ' => '
            result += self.__attributes[key]
            result += ','
        return result[:len(result)-1]
        
    def get_attributes(self):
        self.__attributes.keys().sort()
        return self.__attributes.copy()

class ValidityInterval():
    '''
    Validity interval of a certificate. Values are UTC times.
    Attributes:
    -valid_from
    -valid_to
    '''
    def __init__(self, validity):
        self.valid_from = validity.getComponentByName("notBefore").getComponent()._value
        self.valid_to = validity.getComponentByName("notAfter").getComponent()._value
        
    def get_valid_from_as_datetime(self):
      return self.parse_date(self.valid_from)
    
    def get_valid_to_as_datetime(self):
      return self.parse_date(self.valid_to)
       
    @classmethod
    def parse_date(cls, date):
      """
      parses date string and returns a datetime object;
      it also adjusts the time according to local timezone, so that it is
      compatible with other parts of the library
      """
      year = 2000 + int(date[:2])
      month = int(date[2:4])
      day = int(date[4:6])
      hour = int(date[6:8])
      minute = int(date[8:10])
      second = int(date[10:12])
      tz_delta = datetime.timedelta(seconds=time.timezone)
      return datetime.datetime(year, month, day, hour, minute, second) - tz_delta

class PublicKeyInfo():
    '''
    Represents information about public key.
    Expected RSA.
    TODO: other types of algorithms (DSA)! are supported in pkcs7?
    NOTE: PostSignum does not use DSA
    Attributes:
    - alg (identifier of algorithm)
    - key (tuple of modulus and exponent)
    '''
    def __init__(self, public_key_info):
        self.alg = str(public_key_info.getComponentByName("algorithm"))
        bitstr_key = public_key_info.getComponentByName("subjectPublicKey")
        self.key = get_RSA_pub_key_material(bitstr_key)

class SubjectAltNameExt():
    '''
    Subject alternative name extension.
    '''
    def __init__(self, asn1_subjectAltName):
        self.names = []
        #gen_names = asn1_subjectAltName.getComponentByName("subjectAltName")
        for gname in asn1_subjectAltName:
            #self.names.append(gname.getComponent()._value)
            self.names.append(str(gname.getComponent()))

class BasicConstraintsExt():
    '''
    Basic constraints of this certificate - is it CA and maximal chain depth.
    '''
    def __init__(self, asn1_bConstraints):
        self.ca = asn1_bConstraints.getComponentByName("ca")._value
        self.max_path_len = 0
        if asn1_bConstraints.getComponentByName("pathLen") is not None:
            self.max_path_len = asn1_bConstraints.getComponentByName("pathLen")._value
        

class KeyUsageExt():
    '''
    Key usage extension. 
    '''    
    def __init__(self, asn1_keyUsage):
        self.digitalSignature = False    # (0),
        self.nonRepudiation = False     # (1),
        self.keyEncipherment = False    # (2),
        self.dataEncipherment = False   # (3),
        self.keyAgreement = False       # (4),
        self.keyCertSign = False        # (5),
        self.cRLSign = False            # (6),
        self.encipherOnly = False       # (7),
        self.decipherOnly = False       # (8) 
        
        bits = asn1_keyUsage._value
        try:
            if (bits[0]): self.digitalSignature = True
            if (bits[1]): self.nonRepudiation = True
            if (bits[2]): self.keyEncipherment = True
            if (bits[3]): self.dataEncipherment = True
            if (bits[4]): self.keyAgreement = True
            if (bits[5]): self.keyCertSign = True
            if (bits[6]): self.cRLSign = True    
            if (bits[7]): self.encipherOnly = True
            if (bits[8]): self.decipherOnly = True
        except IndexError:
            return

class AuthorityKeyIdExt():
    '''
    Authority Key identifier extension.
    Identifies key of the authority which was used to sign this certificate.
    '''
    def __init__(self, asn1_authKeyId):
        if (asn1_authKeyId.getComponentByName("keyIdentifier")) is not None:
            self.key_id = asn1_authKeyId.getComponentByName("keyIdentifier")._value
        if (asn1_authKeyId.getComponentByName("authorityCertSerialNum")) is not None:
            self.auth_cert_sn = asn1_authKeyId.getComponentByName("authorityCertSerialNum")._value
        if (asn1_authKeyId.getComponentByName("authorityCertIssuer")) is not None:
            issuer = asn1_authKeyId.getComponentByName("authorityCertIssuer")
            iss = str(issuer.getComponentByName("name"))
            self.auth_cert_issuer = iss
    
class SubjectKeyIdExt():
    '''
    Subject Key Identifier extension. Just the octet string.
    '''
    def __init__(self, asn1_subKey):
        self.subject_key_id = asn1_subKey._value
      
class PolicyQualifier():
    '''
    Certificate policy qualifier. Consist of id and
    own qualifier (id-qt-cps | id-qt-unotice).
    '''
    def __init__(self, asn1_pQual):
        self.id = str(asn1_pQual.getComponentByName("policyQualifierId"))
        if asn1_pQual.getComponentByName("qualifier") is not None:
            qual = asn1_pQual.getComponentByName("qualifier")
            # this is a choice - onky one of following types will be non-null
            qaulifier = None
            comp = qual.getComponentByName("t1")
            if comp is not None:
                qaulifier = comp[0]
            comp = qual.getComponentByName("t2")
            if comp is not None:
                qaulifier = comp[0]  
            comp = qual.getComponentByName("t3")
            if comp is not None:
                qaulifier = comp
            self.qualifier = str(qaulifier)
            
class CertificatePolicyExt():
    '''
    Certificate policy extension.
    COnsist of id and qualifiers.
    '''
    def __init__(self, asn1_certPol):
        self.id = str(asn1_certPol.getComponentByName("policyIdentifier"))
        if (asn1_certPol.getComponentByName("policyQualifiers")):
            qualifiers = asn1_certPol.getComponentByName("policyQualifiers")
            self.qualifiers = [PolicyQualifier(pq) for pq in qualifiers]

class Reasons():
    '''
    CRL distribution point reason flags
    '''
    def __init__(self, asn1_rflags):
        self.unused  = False   #(0),
        self.keyCompromise = False   #(1),
        self.cACompromise = False   #(2),
        self.affiliationChanged = False    #(3),
        self.superseded = False   #(4),
        self.cessationOfOperation = False   #(5),
        self.certificateHold = False   #(6),
        self.privilegeWithdrawn = False   #(7),
        self.aACompromise = False   #(8) 
        
        bits = asn1_rflags._value
        try:
            if (bits[0]): self.unused = True
            if (bits[1]): self.keyCompromise = True
            if (bits[2]): self.cACompromise = True
            if (bits[3]): self.affiliationChanged = True
            if (bits[4]): self.superseded = True
            if (bits[5]): self.cessationOfOperation = True
            if (bits[6]): self.certificateHold = True    
            if (bits[7]): self.privilegeWithdrawn = True
            if (bits[8]): self.aACompromise = True
        except IndexError:
            return


class CRLdistPointExt():
    '''
    CRL distribution point extension
    '''
    def __init__(self, asn1_crl_dp):
        dp = asn1_crl_dp.getComponentByName("distPoint")
        if dp is not None:
            self.dist_point = str(dp.getComponent())
        else:
            self.dist_point = None
        reasons = asn1_crl_dp.getComponentByName("reasons")
        if reasons is not None:
            self.reasons = Reasons(reasons)
        else:
            self.reasons = None
        issuer = asn1_crl_dp.getComponentByName("issuer")
        if issuer is not None:
            self.issuer = str(issuer)
        else:
            self.issuer = None

class QcStatementExt():
    '''
    id_pe_qCStatement
    '''
    def __init__(self, asn1_caStatement):
        self.oid = str(asn1_caStatement.getComponentByName("stmtId"))
        
class Extension():
    '''
    Represents one Extension in X509v3 certificate
    Attributes:
    - id  (identifier of extension)
    - is_critical
    - value (value of extension, needs more parsing - it is in DER encoding)
    '''
    def __init__(self, extension):
        self.id = tuple_to_OID(extension.getComponentByName("extnID"))
        critical = extension.getComponentByName("critical")
        if critical == 0:
            self.is_critical = False
        else:
            self.is_critical = True
        # set the bytes as the extension value
        self.value = extension.getComponentByName("extnValue")._value
        # if we know the type of value, parse it
        if (self.id == "2.5.29.17"):
            v = decoder.decode(self.value, asn1Spec=GeneralNames())[0]
            val = SubjectAltNameExt(v)
            self.value = val
        elif (self.id == "2.5.29.35"):            
            v = decoder.decode(self.value, asn1Spec=KeyId())[0]
            val = AuthorityKeyIdExt(v)
            self.value = val
        elif (self.id == "2.5.29.14"):            
            v = decoder.decode(self.value, asn1Spec=SubjectKeyId())[0]
            val = SubjectKeyIdExt(v)
            self.value = val
        elif (self.id == "2.5.29.19"):
            v = decoder.decode(self.value, asn1Spec=BasicConstraints())[0]
            val = BasicConstraintsExt(v)
            self.value = val
        elif (self.id == "2.5.29.15"):
            v = decoder.decode(self.value)[0]
            val = KeyUsageExt(v)
            self.value = val
        elif (self.id == "2.5.29.32"):            
            v = decoder.decode(self.value, asn1Spec=CertificatePolicies())[0]           
            val = [CertificatePolicyExt(p) for p in v]
            self.value = val
        elif (self.id == "2.5.29.31"):            
            v = decoder.decode(self.value, asn1Spec=CRLDistributionPoints())[0]         
            val = [CRLdistPointExt(p) for p in v]
            self.value = val
        elif (self.id == "1.3.6.1.5.5.7.1.3"):            
            v = decoder.decode(self.value, asn1Spec=Statements())[0]
            val = [QcStatementExt(s) for s in v]            
            self.value = val

class Certificate():
    '''
    Represents Certificate object.
    Attributes:
    - version
    - serial_number
    - signature_algorithm (data are signed with this algorithm)
    - issuer (who issued this certificate)
    - validity
    - subject (for who the certificate was issued)
    - pub_key_info 
    - issuer_uid (optional)
    - subject_uid (optional)
    - extensions (list of extensions)
    '''
    def __init__(self, tbsCertificate):
        self.version = tbsCertificate.getComponentByName("version")._value
        self.serial_number = tbsCertificate.getComponentByName("serialNumber")._value
        self.signature_algorithm = str(tbsCertificate.getComponentByName("signature"))
        self.issuer = Name(tbsCertificate.getComponentByName("issuer"))
        self.validity = ValidityInterval(tbsCertificate.getComponentByName("validity"))
        self.subject = Name(tbsCertificate.getComponentByName("subject"))
        self.pub_key_info = PublicKeyInfo(tbsCertificate.getComponentByName("subjectPublicKeyInfo"))
        
        issuer_uid = tbsCertificate.getComponentByName("issuerUniqueID")
        if issuer_uid:
            self.issuer_uid = issuer_uid.toOctets()
        else:
            self.issuer_uid = None
            
        subject_uid = tbsCertificate.getComponentByName("subjectUniqueID")
        if subject_uid:
            self.subject_uid = subject_uid.toOctets()
        else:
            self.subject_uid = None
            
        self.extensions = self._create_extensions_list(tbsCertificate.getComponentByName('extensions'))        
    
    def _create_extensions_list(self, extensions):
        from pyasn1.type import tag,namedtype,namedval,univ,constraint,char,useful
        from pyasn1.codec.der import decoder, encoder
        from pyasn1 import error
            
        if extensions is None:
            return []
        result = []
        for extension in extensions:
            ext = Extension(extension)
            result.append(ext)
          
        return result
    
class X509Certificate():
    '''
    Represents X509 certificate.
    Attributes:
    - signature_algorithm (used to sign this certificate)
    - signature
    - tbsCertificate (the certificate)
    '''
    def __init__(self, certificate):
        self.signature_algorithm = str(certificate.getComponentByName("signatureAlgorithm"))
        self.signature = certificate.getComponentByName("signatureValue").toOctets()     
        tbsCert = certificate.getComponentByName("tbsCertificate")
        self.tbsCertificate = Certificate(tbsCert)   
        self.verification_results = None
        self.raw_der_data = "" # raw der data for storage are kept here by cert_manager
    
    def is_verified(self):
      '''
      Checks if all values of verification_results dictionary are True,
      which means that the certificate is valid
      '''
      if self.verification_results is None:
        return False
      for key in self.verification_results.keys():
        if self.verification_results[key]:
          continue
        else:
          return False
      return True
    
    def valid_at_date(self, date):
      """check validity of all parts of the certificate with regard
      to a specific date"""
      verification_results = self.verification_results_at_date(date)
      if verification_results is None:
        return False
      for key, value in verification_results.iteritems():
        if not value:
          return False
      return True
    
    def verification_results_at_date(self, date):
      if self.verification_results is None:
        return None
      results = dict(self.verification_results) # make a copy
      results["CERT_TIME_VALIDITY_OK"] = self.time_validity_at_date(date)
      results["CERT_NOT_REVOKED"] = self.crl_validity_at_date(date)
      return results

    def time_validity_at_date(self, date):
      """check if the time interval of validity of the certificate contains
      'date' provided as argument"""
      from_date = self.tbsCertificate.validity.get_valid_from_as_datetime()
      to_date = self.tbsCertificate.validity.get_valid_to_as_datetime()
      time_ok = to_date >= date >= from_date
      return time_ok
    
    def crl_validity_at_date(self, date):
      """check if the certificate was not on the CRL list at a particular date"""
      rev_date = self.get_revocation_date()
      if not rev_date:
        return True
      if date >= rev_date:
        return False
      else:
        return True
      
    def get_revocation_date(self):
      from certs.crl_store import CRL_cache_manager
      cache = CRL_cache_manager.get_cache()
      issuer = str(self.tbsCertificate.issuer)
      rev_date = cache.certificate_rev_date(issuer, self.tbsCertificate.serial_number)
      if not rev_date:
        return None
      rev_date = ValidityInterval.parse_date(rev_date)
      return rev_date
    
        
class Attribute():
    """
    One attribute in SignerInfo attributes set
    """
    def __init__(self, attribute):
        self.type = str(attribute.getComponentByName("type"))
        self.value = str(attribute.getComponentByName("value").getComponentByPosition(0))
        #print base64.b64encode(self.value)

class AutheticatedAttributes():
    """
    Authenticated attributes of signer info
    """
    def __init__(self, auth_attributes):
        self.attributes = []
        for aa in auth_attributes:
            self.attributes.append(Attribute(aa))

class SignerInfo():
    """
    Represents information about a signer.
    Attributes:
    - version
    - issuer 
    - serial_number (of the certificate used to verify this signature)
    - digest_algorithm 
    - encryp_algorithm
    - signature
    - auth_atributes (optional field, contains authenticated attributes)
    """
    def __init__(self, signer_info):
        self.version = signer_info.getComponentByName("version")._value
        self.issuer = Name(signer_info.getComponentByName("issuerAndSerialNum").getComponentByName("issuer"))
        self.serial_number = signer_info.getComponentByName("issuerAndSerialNum").getComponentByName("serialNumber")._value
        self.digest_algorithm = str(signer_info.getComponentByName("digestAlg"))
        self.encrypt_algorithm = str(signer_info.getComponentByName("encryptAlg"))
        self.signature = signer_info.getComponentByName("signature")._value
        auth_attrib = signer_info.getComponentByName("authAttributes")
        if auth_attrib is None:
            self.auth_attributes = None
        else:
            self.auth_attributes = AutheticatedAttributes(auth_attrib)


class PKCS7_data():    
    '''
    Holder for PKCS7 data - version, digest algorithms, signed message, certificate, signer information.
    signed_data, certificate, signer_info = instances from pyasn1, will be 
    mapped into plain python objects
    '''
    def __init__(self, asn1_message=None):
        self.version = None
        self.digest_algorithms = None
        self.message = None
        self.certificates = None
        self.signer_infos = None
        if asn1_message:
          self.parse_asn1_message(asn1_message)
      
    def parse_asn1_message(self, asn1_message):
        msg_content = asn1_message.getComponentByName("content")
        
        self.version = msg_content.getComponentByName("version")
        self.digest_algorithms = self._extract_used_digest_algs(msg_content)
        self.message = msg_content.getComponentByName("content").getComponentByName("signed_content").getContentValue()                 
        self.certificates = [CertificateManager.get_certificate(cert) for cert in msg_content.getComponentByName("certificates")] 
        self.signer_infos = [SignerInfo(si) for si in msg_content.getComponentByName("signerInfos")]
    
    def _extract_used_digest_algs(self, signed_data):
        used_digests = signed_data.getComponentByName("digestAlgs")
        result = []
        for used_digest in used_digests:           
            algorithm_key = tuple_to_OID(used_digest.getComponentByName("algorithm")._value)
            result.append(algorithm_key)  
        return result

######
#TSTinfo
######
class MsgImprint():
    def __init__(self, asn1_msg_imprint):
        self.alg = str(asn1_msg_imprint.getComponentByName("algId"))
        self.imprint = str(asn1_msg_imprint.getComponentByName("imprint"))

class TsAccuracy():
    def __init__(self, asn1_acc):
        secs = asn1_acc.getComponentByName("seconds")
        if secs:
            self.seconds = secs._value
        milis = asn1_acc.getComponentByName("milis")
        if milis:
            self.milis = milis._value
        micros = asn1_acc.getComponentByName("micros")
        if micros:
            self.micros = micros._value

class TimeStampToken():
    '''
    Holder for Timestamp Token Info - attribute from the qtimestamp.    
    '''
    def __init__(self, asn1_tstInfo):
        self.version = asn1_tstInfo.getComponentByName("version")._value
        self.policy = str(asn1_tstInfo.getComponentByName("policy"))
        self.msgImprint = MsgImprint(asn1_tstInfo.getComponentByName("messageImprint"))
        self.serialNum = asn1_tstInfo.getComponentByName("serialNum")._value
        self.genTime = asn1_tstInfo.getComponentByName("genTime")._value
        self.accuracy = TsAccuracy(asn1_tstInfo.getComponentByName("accuracy"))
        self.tsa = Name(asn1_tstInfo.getComponentByName("tsa"))
        # place for parsed certificates in asn1 form
        self.asn1_certificates = []
        # place for certificates transformed to X509Certificate
        self.certificates = []
        #self.extensions = asn1_tstInfo.getComponentByName("extensions")
    
    def certificates_contain(self, cert_serial_num):
        """
        Checks if set of certificates of this timestamp contains
        certificate with specified serial number.
        Returns True if it does, False otherwise.
        """
        for cert in self.certificates:
          if cert.tbsCertificate.serial_number == cert_serial_num:
            return True
        return False
    
    def get_genTime_as_datetime(self):
      """
      parses the genTime string and returns a datetime object;
      it also adjusts the time according to local timezone, so that it is
      compatible with other parts of the library
      """
      year = int(self.genTime[:4])
      month = int(self.genTime[4:6])
      day = int(self.genTime[6:8])
      hour = int(self.genTime[8:10])
      minute = int(self.genTime[10:12])
      second = int(self.genTime[12:14])
      micro = int(float(self.genTime[14:].strip("Z"))*1e6)
      tz_delta = datetime.timedelta(seconds=time.timezone)
      return datetime.datetime(year, month, day, hour, minute, second, micro) - tz_delta
