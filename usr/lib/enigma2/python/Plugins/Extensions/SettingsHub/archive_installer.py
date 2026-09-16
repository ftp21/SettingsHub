# -*- coding: utf-8 -*-
"""
Download ed applicazione generica di un pacchetto di setting distribuito
come archivio (zip oppure tar.gz) contenente lamedb/bouquets - il formato
piu' comune tra i setting man. Condiviso tra provider diversi (vedi
providers/vhannibal, providers/morpheus) per non riscrivere la stessa logica
in ognuno: un provider nuovo il cui sito distribuisce zip o tar.gz con
lamedb dentro puo' limitarsi a chiamare installArchivePackage(), senza
reimplementare download/estrazione/merge.

Tutte le funzioni qui sono bloccanti di proposito (rete, disco, estrazione):
vanno chiamate SOLO dentro api.runInThread, mai sul thread GUI."""
import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

from Plugins.Extensions.SettingsHub import favorites
from Plugins.Extensions.SettingsHub.config import config as hubConfig, getFavoritesSelection

ENIGMA2_DIR = "/etc/enigma2"
CHANNEL_LIST_NAMES = ("lamedb", "lamedb5", "bouquets.tv", "bouquets.radio")


def installArchivePackage(url, user_agent, temp_prefix="settingshub_"):
	"""Scarica ed applica un pacchetto zip o tar.gz di setting standard
	(contiene lamedb/bouquets/satellites.xml alla radice o in una
	sottocartella, es. etc/enigma2/...). Il formato e' rilevato dai byte
	scaricati, non dall'estensione dell'url. Salva/ripristina automaticamente
	i bouquet preferiti scelti dall'utente (vedi favorites.py). Ritorna
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
				return False, "Il file scaricato non e' un archivio zip valido."
		elif data[:2] == b"\x1f\x8b":
			try:
				with tarfile.open(archivePath, "r:gz") as tf:
					tf.extractall(extractDir)
			except tarfile.TarError:
				return False, "Il file scaricato non e' un archivio tar.gz valido."
		else:
			return False, "Formato di archivio non riconosciuto (atteso zip o tar.gz)."

		sourceDir = _findLamedbDir(extractDir)
		if sourceDir is None:
			return False, "Il pacchetto scaricato non contiene un lamedb valido."

		# Nessun on/off separato: se l'utente non ha scelto nessun bouquet da
		# preservare (schermata "Scegli i bouquet da preservare"), selection
		# e' vuota e semplicemente non c'e' nulla da salvare/ripristinare.
		selection = getFavoritesSelection()
		savedCount = favorites.save(hubConfig.plugins.settingshub.favorites_snapshot, selection)

		_applyChannelList(sourceDir)

		restoredCount = 0
		if savedCount:
			restoredCount = favorites.restore(hubConfig.plugins.settingshub.favorites_snapshot)

		message = "Nuovo setting applicato."
		if savedCount:
			message += f" Bouquet preferiti ripristinati: {restoredCount}/{savedCount}."
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
