#! /usr/bin/python
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


import sys
import glob
import os
from setuptools import setup
import release

# dslib subpackages
dslib_dir = "./"
pkgdirs = ["dsdb","converters","pkcs7","properties","certs"]
dslib_subpackages = []
for pkgdir in pkgdirs:
  for name,dirs,files in os.walk(pkgdir): #, followlinks=True):
    if os.path.exists(os.path.join(name,"__init__.py")):
      dslib_subpackages.append("dslib."+name.replace("/","."))
#print >> sys.stderr, dslib_subpackages

data = dict(
  name = 'dslib',
  version = release.DSLIB_VERSION,
  description = "dslib is a free Python library for accessing Datove schranky",
  author = "CZ.NIC Labs",
  author_email = "datove-schranky@labs.nic.cz",
  url = "http://labs.nic.cz/datove-schranky/",
  license = "GNU LGPL",
  platforms = ["Unix", "Windows","MacOS X"],
  long_description = "dslib is a Python library for accessing a 'Databox' - \
an electronic communication interface endorsed by the Czech government.",
  
  packages=["dslib"]+dslib_subpackages,
  package_dir = {'dslib': './'},
  data_files = [('share/dslib', ['README.txt', 'LICENSE.txt']),
                ('share/dslib/wsdl', glob.glob('wsdl/*')),
                ('share/dslib/trusted_certificates',
                 glob.glob('trusted_certificates/*.pem')),
                ],
  install_requires = ['pyOpenSSL>=0.9', 'sudsds>=1.0', 'pyasn1>=0.0.13', 'SQLAlchemy>=0.7'],
  provides=["dslib"],
  )

set = setup(**data)

