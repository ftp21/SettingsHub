# -*- coding: utf-8 -*-
"""Info provider: metadati del setting man Morpheus883."""
ID = "morpheus883"
NAME = "Morpheus883"
DESCRIPTION = "Setting satellitari da morpheus883.altervista.org"
ENABLED = True


def getProvider():
	from .provider import MorpheusProvider
	return MorpheusProvider()
