# -*- coding: utf-8 -*-
"""
Download ed applicazione di un pacchetto di setting in zip o tar.gz
(lamedb/bouquets), condiviso tra i provider che distribuiscono in questo
formato. Bloccante di proposito: va chiamato solo dentro api.runInThread."""
import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

from Plugins.Extensions.SettingsHub import favorites
from Plugins.Extensions.SettingsHub import lcn_integration
from Plugins.Extensions.SettingsHub.config import config as hubConfig, getFavoritesSelection
from Plugins.Extensions.SettingsHub.language import _

ENIGMA2_DIR = "/etc/enigma2"
CHANNEL_LIST_NAMES = ("lamedb", "lamedb5", "bouquets.tv", "bouquets.radio")


def installArchivePackage(url, user_agent, temp_prefix="settingshub_"):
	"""Formato rilevato dai byte scaricati, non dall'estensione dell'url.
	Salva/ripristina i bouquet preferiti (vedi favorites.py). Ritorna
	(True, messaggio) oppure (False, errore)."""
	req = urllib.request.Request(url, headers={"User-Agent": user_agent})
	with urllib.request.urlopen(req, timeout=60) as response:
		data = response.read()

	workDir = tempfile.mkdtemp(prefix=temp_prefix)
	try:
		extractDir = os.path.join(workDir, "extracted")
		os.makedirs(extractDir, exist_ok=True)

		archivePath = os.path.join(workDir, "package.bin")
		with open(archivePath, "wb") as f:
			f.write(data)

		if data[:2] == b"PK":
			try:
				with zipfile.ZipFile(archivePath) as zf:
					zf.extractall(extractDir)
			except zipfile.BadZipFile:
				return False, _("The downloaded file is not a valid zip archive.")
		elif data[:2] == b"\x1f\x8b":
			try:
				with tarfile.open(archivePath, "r:gz") as tf:
					tf.extractall(extractDir)
			except tarfile.TarError:
				return False, _("The downloaded file is not a valid tar.gz archive.")
		else:
			return False, _("Unrecognized archive format (expected zip or tar.gz).")

		sourceDir = _findLamedbDir(extractDir)
		if sourceDir is None:
			return False, _("The downloaded package does not contain a valid lamedb.")

		# Nessun on/off separato: se l'utente non ha scelto nessun bouquet da
		# preservare (schermata "Scegli i bouquet da preservare"), selection
		# e' vuota e semplicemente non c'e' nulla da salvare/ripristinare.
		selection = getFavoritesSelection()
		savedCount = favorites.save(hubConfig.plugins.settingshub.favorites_snapshot, selection)

		# Metodo "preserve" per il bouquet LCNScanner (vedi lcn_integration.py):
		# va catturato PRIMA che _applyChannelList() sovrascriva il lamedb, non
		# dopo - qui, non in screens/browser.py, perche' e' l'unico punto che
		# vede ancora il lamedb VECCHIO. Il metodo "scan" invece non fa nulla
		# qui: se ne occupa browser.py con una vera scansione a installazione
		# finita (serve una sessione/UI che qui non c'e', essendo dentro
		# api.runInThread).
		usePreserve = (
			hubConfig.plugins.settingshub.recreate_lcn_after_update.value
			and lcn_integration.rebuildMethod() == "preserve"
			and lcn_integration.shouldRescanForLCN()
		)
		preservedLamedb = lcn_integration.capturePreservedLamedb() if usePreserve else None

		_applyChannelList(sourceDir)

		if preservedLamedb:
			lcn_integration.applyPreservedLamedb(preservedLamedb)

		restoredCount = 0
		if savedCount:
			restoredCount = favorites.restore(hubConfig.plugins.settingshub.favorites_snapshot)

		message = _("New setting applied.")
		if savedCount:
			message += " " + _("Favorite bouquets restored: %(restored)d/%(saved)d.") % {"restored": restoredCount, "saved": savedCount}
		if preservedLamedb:
			message += " " + _("LCN bouquet rebuilt from the existing lamedb (no DVB-T rescan).")
		return True, message
	finally:
		shutil.rmtree(workDir, ignore_errors=True)


def _findLamedbDir(root):
	for dirpath, _dirnames, filenames in os.walk(root):
		if "lamedb" in filenames or "lamedb5" in filenames:
			return dirpath
	return None


def _applyChannelList(sourceDir):
	# via i canali vecchi...
	for name in os.listdir(ENIGMA2_DIR):
		isChannelFile = name in CHANNEL_LIST_NAMES or (
			name.startswith("userbouquet.") and (name.endswith(".tv") or name.endswith(".radio"))
		)
		if isChannelFile:
			try:
				os.remove(os.path.join(ENIGMA2_DIR, name))
			except OSError:
				pass

	# ...dentro i nuovi.
	for name in os.listdir(sourceDir):
		srcPath = os.path.join(sourceDir, name)
		if not os.path.isfile(srcPath):
			continue
		isChannelFile = name in CHANNEL_LIST_NAMES or (
			name.startswith("userbouquet.") and (name.endswith(".tv") or name.endswith(".radio"))
		)
		if isChannelFile:
			shutil.copyfile(srcPath, os.path.join(ENIGMA2_DIR, name))

	satellitesPath = os.path.join(sourceDir, "satellites.xml")
	if os.path.exists(satellitesPath):
		os.makedirs("/etc/tuxbox", exist_ok=True)
		shutil.copyfile(satellitesPath, "/etc/tuxbox/satellites.xml")

	# Senza questo, eServiceCenter continua a rispondere con il lamedb VECCHIO
	# (ancora in cache) finche' enigma2 non viene riavviato. favorites.restore(),
	# chiamato subito dopo _applyChannelList(), cerca ogni canale salvato nel
	# lamedb "attuale" tramite _currentServicesByKey(): senza il reload qui,
	# quella ricerca risolve ancora contro il lamedb vecchio, e i riferimenti
	# scritti nel bouquet ripristinato smettono di funzionare (mostrando N/A)
	# non appena enigma2 ricarica per conto suo il lamedb NUOVO appena scritto
	# su disco (es. al riavvio successivo).
	from enigma import eDVBDB
	eDVBDB.getInstance().reloadServicelist()
