# -*- coding: utf-8 -*-
"""
Riporta la lista canali a una situazione di base, cancellando tutto quello
che un setting man ha installato (lamedb, bouquet, satellites.xml) e
dimenticando quale entry risultava installata, cosi' il prossimo install
riparte da zero invece di pensare 'e' gia' aggiornato'. Non tocca la
configurazione dei preferiti (selezione/snapshot): sono preferenze
dell'utente, non 'dati del setting man', e servono proprio a sopravvivere a
un reset come questo."""
import os

ENIGMA2_DIR = "/etc/enigma2"

_EMPTY_LAMEDB = "eDVB services /4/\ntransponders\nend\nservices\nend\n"


def resetChannelData():
	"""Cancella lamedb/lamedb5, tutti gli userbouquet.*.tv/.radio e le liste
	bouquets.tv/bouquets.radio, sostituendoli con una base vuota valida.
	Ritorna il numero di file rimossi."""
	removed = 0
	if os.path.isdir(ENIGMA2_DIR):
		for name in os.listdir(ENIGMA2_DIR):
			isChannelFile = name in ("lamedb", "lamedb5", "bouquets.tv", "bouquets.radio") or (
				name.startswith("userbouquet.") and (name.endswith(".tv") or name.endswith(".radio"))
			)
			if isChannelFile:
				try:
					os.remove(os.path.join(ENIGMA2_DIR, name))
					removed += 1
				except OSError:
					pass

	with open(os.path.join(ENIGMA2_DIR, "lamedb"), "w", encoding="utf-8") as f:
		f.write(_EMPTY_LAMEDB)
	with open(os.path.join(ENIGMA2_DIR, "bouquets.tv"), "w", encoding="utf-8") as f:
		f.write("#NAME Bouquets (TV)\n")
	with open(os.path.join(ENIGMA2_DIR, "bouquets.radio"), "w", encoding="utf-8") as f:
		f.write("#NAME Bouquets (Radio)\n")

	from enigma import eDVBDB
	eDVBDB.getInstance().reloadServicelist()
	eDVBDB.getInstance().reloadBouquets()

	return removed


def resetProviderInstalledInfo(provider_id):
	"""Dimentica lo stato 'installato' corrente (vedi config.getInstalledInfo:
	e' un unico stato globale, non uno per provider). 'provider_id' non serve
	piu' per distinguere quale ramo di config azzerare, resta come parametro
	solo per compatibilita' con chi la chiama gia' passando il provider
	attivo (vedi screens/setup.py)."""
	from Plugins.Extensions.SettingsHub.config import resetInstalledInfo
	resetInstalledInfo()
