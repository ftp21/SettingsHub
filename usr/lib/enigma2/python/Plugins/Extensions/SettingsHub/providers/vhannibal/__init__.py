# -*- coding: utf-8 -*-
"""Info provider: metadati del setting man Vhannibal AutoSetting."""
ID = "vhannibal"
NAME = "Vhannibal"
DESCRIPTION = "Setting satellitari e digitale terrestre da vhannibal.net"
ENABLED = True


def getProvider():
	from .provider import VhannibalProvider
	return VhannibalProvider()
