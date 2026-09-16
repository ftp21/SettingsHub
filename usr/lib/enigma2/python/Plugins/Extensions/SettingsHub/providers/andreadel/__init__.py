# -*- coding: utf-8 -*-
"""Info provider: metadati del setting man Liste Canali Enigma2 Italia (Andrea del 1984)."""
ID = "andreadel"
NAME = "Andrea del 1984"
DESCRIPTION = "Liste canali semplici Hotbird/Astra da github.com/Andreadel1984"
ENABLED = True


def getProvider():
	from .provider import AndreadelProvider
	return AndreadelProvider()
