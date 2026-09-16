# -*- coding: utf-8 -*-
"""Info provider: metadati del setting man ManuTEK (NemoxyzRLS)."""
ID = "manutek"
NAME = "ManuTEK"
DESCRIPTION = "Setting SAT+DTT per zona/citta' da manutek.it (realizzati NemoxyzRLS)"
ENABLED = True


def getProvider():
	from .provider import ManutekProvider
	return ManutekProvider()
