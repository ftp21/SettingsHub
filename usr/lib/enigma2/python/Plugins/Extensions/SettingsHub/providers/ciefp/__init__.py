# -*- coding: utf-8 -*-
"""Info provider: metadati del setting man Ciefp (ciefpsettings-enigma2-zipped)."""
ID = "ciefp"
NAME = "Ciefp"
DESCRIPTION = "Setting satellitari da github.com/ciefp/ciefpsettings-enigma2-zipped"
ENABLED = True


def getProvider():
	from .provider import CiefpProvider
	return CiefpProvider()
