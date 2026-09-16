# -*- coding: utf-8 -*-
"""
Info provider: ogni cartella dentro providers/ dichiara qui i propri
metadati, cosi' sono leggibili senza dover importare/istanziare la classe.
"""
ID = "demo"
NAME = "Demo Provider"
DESCRIPTION = "Provider di esempio incluso nello scheletro di SettingsHub, nessuna rete reale."
# Resta nel codice come riferimento/collaudo ma non compare nella lista che
# vede l'utente finale: per riabilitarlo basta mettere True.
ENABLED = False


def getProvider():
	from .provider import DemoProvider
	return DemoProvider()
