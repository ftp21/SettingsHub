# -*- coding: utf-8 -*-
"""
Integrazione opzionale con Plugins.SystemPlugins.AutoBouquetsMaker (ABM).

Stesso problema di lcn_integration.py, stessa soluzione a due meccanismi -
vedi quel modulo per la spiegazione generale. La differenza e' che ABM non
ha un metodo "ricostruisci il bouquet da quello che c'e' gia' nel lamedb,
senza toccare il tuner" come LCNScanner().lcnScan(): puo' solo (ri)scansionare
davvero (satellite/cavo/terrestre, secondo i provider che l'utente ha scelto
dentro ABM). Quindi:

- "preserve" (sempre, in archive_installer.py): oltre a reinserire nel
  lamedb nuovo le righe transponder/servizio che i bouquet ABM referenziano
  (stessa idea di lcn_integration.py, ma per identita' di servizio invece
  che per un namespace fisso - ABM puo' gestire satellite/cavo/terrestre a
  seconda dei provider scelti, non c'e' un unico namespace da filtrare come
  EEEE0000 per LCNScanner), riscrive anche i FILE bouquet ABM stessi
  (cancellati da _applyChannelList() insieme a tutti gli altri
  userbouquet.*.tv/.radio) esattamente come erano, e li rimette nella lista
  bouquets.tv/.radio alla loro posizione originale. E' l'unica rete di
  sicurezza disponibile quando l'installazione parte senza sessione/UI
  (autocheck.py chiama provider.install() direttamente, mai
  screens/browser.py).
- "scan" (in aggiunta, solo se config.plugins.settingshub.abm_rebuild_method
  == "scan", vedi screens/setup.py): apre la vera schermata di scansione di
  ABM (usa i provider gia' configurati dall'utente dentro ABM stesso - non
  decidiamo noi cosa scansionare), che sovrascrive il risultato "grezzo" di
  preserve con dati verificati. Serve una sessione/UI, quindi puo' scattare
  solo dal flusso manuale (screens/browser.py, DOPO che l'installazione e'
  finita).

Questo modulo non fa nulla se non e' presente nessun bouquet il cui nome
inizi per favorites.ABM_BOUQUET_PREFIX ("userbouquet.abm.", lo stesso
prefisso che usa AutoBouquetsMaker per i propri bouquet - vedi
ABM_BOUQUET_PREFIX in
Plugins.SystemPlugins.AutoBouquetsMaker.scanner.main.AutoBouquetsMaker) - in
quel caso un update dei settings si comporta esattamente come prima, senza
toccare nulla di questo."""

import os

from Plugins.Extensions.SettingsHub import favorites
from Plugins.Extensions.SettingsHub.config import config as hubConfig

LAMEDB_PATH = "/etc/enigma2/lamedb"
ENIGMA2_DIR = "/etc/enigma2"


def _abmBouquetEntries():
	"""[(kind, position, fileName), ...] per ogni bouquet che ABM gestisce
	(nome che inizia per favorites.ABM_BOUQUET_PREFIX), TV e radio insieme."""
	result = []
	for kind in ("tv", "radio"):
		for position, path in favorites._bouquetEntriesFor(kind):
			fileName = os.path.basename(path)
			if fileName.startswith(favorites.ABM_BOUQUET_PREFIX):
				result.append((kind, position, fileName))
	return result


def shouldRescanForABM():
	"""True se e' presente almeno un bouquet che ABM gestisce."""
	try:
		return bool(_abmBouquetEntries())
	except Exception as err:
		print(f"[SettingsHub] Warning: could not check for ABM-managed bouquets, skipping the ABM rebuild.  ({err})")
		return False


def isABMInstalled():
	try:
		from Plugins.SystemPlugins.AutoBouquetsMaker.scanner.main import AutoBouquetsMaker  # noqa: F401
	except ImportError:
		return False
	return True


def rebuildMethod():
	"""'scan' o 'preserve', dal config (vedi screens/setup.py)."""
	return hubConfig.plugins.settingshub.abm_rebuild_method.value


# --- Metodo "scan": vera scansione, eseguita DOPO l'installazione ----------

def startRescan(session, finished_cb):
	"""Apre la schermata di scansione di ABM cosi' com'e' (usa i provider
	gia' configurati dall'utente dentro ABM - non costruiamo nessuna lista di
	scan qui, a differenza di lcn_integration.startRescan()). La schermata di
	ABM si chiude gia' da sola sia a scansione completata (2 secondi dopo, in
	AutoBouquetsMaker.scanComplete()) sia in caso di errore (es. nessun
	provider configurato, in AutoBouquetsMaker.showError()): finished_cb()
	viene chiamata al suo close(), qualunque sia stato l'esito - non serve
	nessun wrapping extra come per ServiceScan in lcn_integration.py."""
	from Plugins.SystemPlugins.AutoBouquetsMaker.scanner.main import AutoBouquetsMaker
	session.openWithCallback(lambda *unused_result: finished_cb(), AutoBouquetsMaker)


# --- Metodo "preserve": nessuno scan, ririniezione + riscrittura bouquet ---

def _readLines(path):
	try:
		with open(path, "r", encoding="utf-8", errors="ignore") as f:
			return f.readlines()
	except OSError:
		return None


def _serviceKeysFromBouquetLines(lines):
	"""{(sid, namespace, tsid, onid), ...} per ogni '#SERVICE' valido (non
	sotto-bouquet/marker) in 'lines' - stessa logica/stesso formato di
	favorites._parseServiceKey ('#SERVICE 1:flags:type:sid:tsid:onid:namespace:...'),
	ma qui serve anche il namespace per poter ritrovare la voce giusta nel
	lamedb (che a differenza del riferimento di servizio non ha un formato
	fisso di posizione unico per tutti e tre onid/tsid/namespace - vedi
	sotto)."""
	keys = set()
	for line in lines:
		line = line.strip()
		if not line.startswith("#SERVICE"):
			continue
		parts = line[8:].strip().split(":")
		if len(parts) < 7:
			continue
		try:
			flags = int(parts[1])
			sid = int(parts[3], 16)
			tsid = int(parts[4], 16)
			onid = int(parts[5], 16)
			namespace = int(parts[6], 16)
		except ValueError:
			continue
		if flags in (7, 64):  # 7=sotto-bouquet, 64=marker: non sono canali
			continue
		keys.add((sid, namespace, tsid, onid))
	return keys


def capturePreservedABM():
	"""Da chiamare PRIMA che _applyChannelList() (archive_installer.py)
	cancelli i vecchi userbouquet.*.tv/.radio e sovrascriva il lamedb.

	Cattura, per ogni bouquet ABM trovato: il suo contenuto grezzo (per
	riscriverlo identico dopo) e le righe transponder/servizio del lamedb
	VECCHIO che i suoi canali referenziano, individuate per identita'
	(sid/namespace/tsid/onid) invece che per un namespace fisso come fa
	lcn_integration.capturePreservedLamedb() - il formato e' quello scritto
	da eDVBDB::saveServicelist() (lib/dvb/db.cpp): un transponder e'
	'namespace:tsid:onid', un servizio e' 'sid:namespace:tsid:onid:tipo:0:sourceid',
	entrambi seguiti sempre da altre 2 righe di dati (3 righe totali per voce).

	Ritorna None se non c'e' nessun bouquet ABM, o nessuna voce di lamedb da
	salvare per loro (bouquet vuoto/canali gia' irraggiungibili)."""
	entries = _abmBouquetEntries()
	if not entries:
		return None

	bouquets = []
	wantedServiceKeys = set()
	for kind, position, fileName in entries:
		lines = _readLines(os.path.join(ENIGMA2_DIR, fileName))
		if lines is None:
			continue
		bouquets.append({"kind": kind, "position": position, "fileName": fileName, "content": "".join(lines)})
		wantedServiceKeys |= _serviceKeysFromBouquetLines(lines)

	if not bouquets or not wantedServiceKeys:
		return None

	wantedTransponderKeys = {(namespace, tsid, onid) for _sid, namespace, tsid, onid in wantedServiceKeys}

	lamedbLines = _readLines(LAMEDB_PATH)
	if lamedbLines is None:
		print("[SettingsHub] Warning: could not read the old lamedb to preserve ABM entries.")
		return None

	transponders = []
	services = []
	section = None  # None | "transponders" | "services"
	i = 0
	n = len(lamedbLines)
	while i < n:
		stripped = lamedbLines[i].strip()
		if stripped in ("transponders", "services"):
			section = stripped
			i += 1
			continue
		if stripped == "end":
			section = None
			i += 1
			continue
		if section == "transponders":
			headerParts = stripped.split(":")
			try:
				key = (int(headerParts[0], 16), int(headerParts[1], 16), int(headerParts[2], 16)) if len(headerParts) == 3 else None
			except ValueError:
				key = None
			if key in wantedTransponderKeys:
				transponders.extend(lamedbLines[i:i + 3])
			i += 3
			continue
		if section == "services":
			headerParts = stripped.split(":")
			try:
				key = (int(headerParts[0], 16), int(headerParts[1], 16), int(headerParts[2], 16), int(headerParts[3], 16)) if len(headerParts) >= 4 else None
			except ValueError:
				key = None
			if key in wantedServiceKeys:
				services.extend(lamedbLines[i:i + 3])
			i += 3
			continue
		i += 1

	if not transponders and not services:
		return None
	return {"bouquets": bouquets, "transponders": transponders, "services": services}


def applyPreservedABM(data):
	"""Da chiamare DOPO che _applyChannelList() ha scritto il lamedb nuovo e
	fatto il suo reloadServicelist(): reinserisce le righe catturate da
	capturePreservedABM() dentro le sezioni 'transponders'/'services' del
	lamedb nuovo, ricarica di nuovo, riscrive i file bouquet ABM esattamente
	come erano e li rimette nella lista bouquets.tv/.radio alla loro
	posizione originale (stessa logica di favorites._registerBouquetsAtPositions(),
	riusata direttamente da li'). Puro I/O e chiamate eDVBDB, nessuna
	sessione/UI: puo' girare nel thread di background dell'installazione.
	Ritorna True se ha fatto qualcosa."""
	if not data or not data.get("bouquets"):
		return False

	if data.get("transponders") or data.get("services"):
		lamedbLines = _readLines(LAMEDB_PATH)
		if lamedbLines is None:
			print("[SettingsHub] Error: could not read the new lamedb to re-inject preserved ABM entries.")
			return False

		out = []
		for line in lamedbLines:
			out.append(line)
			stripped = line.strip()
			if stripped == "transponders" and data.get("transponders"):
				out.extend(data["transponders"])
			elif stripped == "services" and data.get("services"):
				out.extend(data["services"])

		try:
			with open(LAMEDB_PATH, "w", encoding="utf-8") as f:
				f.writelines(out)
		except OSError as err:
			print(f"[SettingsHub] Error: could not write the new lamedb with the preserved ABM entries.  ({err})")
			return False

		from enigma import eDVBDB
		eDVBDB.getInstance().reloadServicelist()

	entriesByKind = {"tv": [], "radio": []}
	wroteAny = False
	for bouquet in data["bouquets"]:
		path = os.path.join(ENIGMA2_DIR, bouquet["fileName"])
		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write(bouquet["content"])
		except OSError as err:
			print(f"[SettingsHub] Error: could not restore the ABM bouquet '{bouquet['fileName']}'.  ({err})")
			continue
		entriesByKind[bouquet["kind"]].append((bouquet["position"], bouquet["fileName"]))
		wroteAny = True

	if not wroteAny:
		return False

	for kind, kindEntries in entriesByKind.items():
		if kindEntries:
			favorites._registerBouquetsAtPositions(kind, kindEntries)

	from enigma import eDVBDB
	eDVBDB.getInstance().reloadBouquets()
	print("[SettingsHub] ABM bouquet(s) rebuilt from the preserved (pre-update) lamedb, no rescan.")
	return True
