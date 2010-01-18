'''
Model for pkcs#7 v1.5 signedData content
'''
import string
from pyasn1.type import tag,namedtype,univ,useful
from pyasn1 import error

from X509_certificate import Certificates
from att_certificate_v2 import CertificateSet
from general_types import *
from oid import oid_map as oid_map


class SignedContent(univ.SequenceOf):
    #tagSet = univ.OctetString.tagSet.tagExplicitly(
    #                    tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
    #                )
    componentType = univ.OctetString()
    tagSet = univ.SequenceOf.tagSet.tagImplicitly(
                        tag.Tag(tag.tagClassUniversal, tag.tagFormatConstructed, 0x04)
                    )
    def getContentValue(self):
        buffer = ''
        for idx in xrange(len(self)):
            comp = self.getComponentByPosition(idx)
            buffer += comp
        return buffer._value


class Content(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("content_type", univ.ObjectIdentifier()),
                        namedtype.NamedType("signed_content", SignedContent().\
                                            subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0)))                 
                    )

class AlgIdentifiers(univ.SetOf):
    componentType = AlgorithmIdentifier()
            

class SignedData(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("version", univ.Integer()),                        
                        namedtype.NamedType("digestAlgs", AlgIdentifiers()),
                        namedtype.NamedType("content", Content())    
                    )

class MsgType(univ.ObjectIdentifier): pass

class SignVersion(univ.Integer):pass

class IssuerAndSerial(univ.Sequence):
    componentType = namedtype.NamedTypes(
                                         namedtype.NamedType("issuer", Name()),
                                         namedtype.NamedType("serialNumber", univ.Integer())
                                         )

class AuthAttributeValue(univ.Set): 
    def __str__(self):
        '''
        Return string of first element in this set
        '''
        return str(self.getComponentByPosition(0))

class AuthAttribute(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('type', univ.ObjectIdentifier()),
        namedtype.NamedType('value', AuthAttributeValue())
        )


class Attributes(univ.SetOf):
    componentType = AuthAttribute()

class SignerInfo(univ.Sequence): 
    componentType = namedtype.NamedTypes(
                                        namedtype.NamedType("version", SignVersion()),
                                        namedtype.NamedType("issuerAndSerialNum", IssuerAndSerial()),
                                        namedtype.NamedType("digestAlg", AlgorithmIdentifier()),
                                        namedtype.OptionalNamedType("authAttributes", Attributes().\
                                                                                    subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0))),
                                        namedtype.NamedType("encryptAlg", AlgorithmIdentifier()),
                                        namedtype.NamedType("signature", univ.OctetString()),
                                        namedtype.OptionalNamedType("unauthAttributes", Attributes().\
                                                                                    subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x1)))
                                         )

class SignerInfos(univ.SetOf):
    componentType = SignerInfo()

class Crl(univ.Sequence):
    pass

class Crls(univ.Set):
    componentType = Crl()

class V1Content(univ.Sequence):   
    componentType = namedtype.NamedTypes(                        
                        namedtype.NamedType("version", univ.Integer()),                        
                        namedtype.NamedType("digestAlgs", AlgIdentifiers()),
                        namedtype.NamedType("content", Content()),
                        namedtype.OptionalNamedType("certificates", Certificates().\
                                                                subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0))),
                        namedtype.OptionalNamedType("crls", Crls().\
                                                                subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x1))),
                        namedtype.NamedType("signerInfos", SignerInfos())
                )
    
class Message(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("type", MsgType()),
                        namedtype.NamedType("content", V1Content().\
                                            subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0)))
                        )
####################################
####### TIMESTAMP MODEL ############
####################################
'''
version CMSVersion,
 digestAlgorithms DigestAlgorithmIdentifiers,
 encapContentInfo EncapsulatedContentInfo,
 certificates [0] IMPLICIT CertificateSet OPTIONAL,
 crls [1] IMPLICIT RevocationInfoChoices OPTIONAL,
 signerInfos SignerInfos
'''
class EncapsulatedContent(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("eContentType", univ.ObjectIdentifier()),
                        namedtype.OptionalNamedType("eContent", univ.OctetString().\
                                                    subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0))),
                        
                        )

class QtsContent(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("version", univ.Integer()),
                        namedtype.NamedType("digestAlgorithms", AlgIdentifiers()),
                        namedtype.NamedType("encapsulatedContentInfo", EncapsulatedContent()),
                        namedtype.OptionalNamedType("certificates", CertificateSet().\
                                                    subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0))),
                        namedtype.OptionalNamedType("crls", Crls().\
                                                    subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x1))),
                        namedtype.NamedType("signerInfos", SignerInfos()),
                        )

class Qts(univ.Sequence):
    componentType = namedtype.NamedTypes(
                        namedtype.NamedType("type", MsgType()),
                        namedtype.NamedType("content", QtsContent().\
                                            subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0x0)))
                        )
