
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
'''
Some usefull tools for working with ASN1 components.
'''

# dslib imports
from pyasn1.codec.der import decoder
from pyasn1 import error

# local imports
from RSA import *


def tuple_to_OID(tuple):
    """
    Converts OID tuple to OID string
    """
    l = len(tuple)
    buf = ''
    for idx in xrange(l):
        if (idx < l-1):
            buf += str(tuple[idx]) + '.'
        else:
            buf += str(tuple[idx])
    return buf

def get_RSA_pub_key_material(subjectPublicKeyAsn1):
    '''
    Extracts modulus and public exponent from 
    ASN1 bitstring component subjectPublicKey
    '''
    # create template for decoder
    rsa_key = RsaPubKey()
    # convert ASN1 subjectPublicKey component from BITSTRING to octets
    pubkey = subjectPublicKeyAsn1.toOctets()
    
    key = decoder.decode(pubkey, asn1Spec=rsa_key)[0]
    
    mod = key.getComponentByName("modulus")._value
    exp = key.getComponentByName("exp")._value
    
    return {'mod': mod, 'exp': exp}