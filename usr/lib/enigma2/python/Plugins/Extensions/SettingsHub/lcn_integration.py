# -*- coding: utf-8 -*-
"""
Integrazione opzionale con Plugins.SystemPlugins.LCNScanner.

Un pacchetto di settings sostituisce l'intero lamedb, DVB-T incluso: i vecchi
servizi terrestri (e quindi ogni bouquet che li referenzia, come quello creato
da LCNScanner) restano orfani finche' qualcosa non li rimette a posto. Due
meccanismi, non alternativi:

- "preserve" (sempre, in archive_installer.py): salva le righe transponder/
  servizi DVB-T (namespace EEEE0000) del lamedb VECCHIO prima che venga
  sovrascritto, e le rimette dentro quello NUOVO cosi' come sono - stessa
  idea di NGsetting/plugin/Moduli/Setting.py (SaveTrasponderService/
  CreateBouquetForce): nessuna verifica che i canali siano ancora ricevibili
  cosi', ma e' immediato, non tocca il tuner e non serve nessuna sessione/UI
  - gira nello stesso thread di background dell'installazione. E' l'unica
  rete di sicurezza disponibile quando l'installazione parte senza una
  sessione utente attiva (autocheck.py chiama provider.install()
  direttamente, mai screens/browser.py): senza questo, un'installazione
  automatica cancellerebbe il bouquet gestito da LCNScanner senza mai
  ricostruirlo.
- "scan" (in aggiunta, solo se config.plugins.settingshub.lcn_rebuild_method
  == "scan", vedi screens/setup.py): rifa' una vera scansione DVB-T (solo
  aggiunta, niente satellite/cavo) e lascia che LCNScanner ricostruisca il
  bouquet sui canali appena trovati, sovrascrivendo il risultato "grezzo" di
  preserve con dati verificati. Serve una sessione/UI, quindi puo' scattare
  solo dal flusso manuale (screens/browser.py, DOPO che l'installazione e'
  finita) - un'installazione automatica resta con il risultato di preserve.

Questo modulo non fa nulla se LCNScanner non e' installato, o se non e'
presente nessun bouquet che LCNScanner gestisce (vedi
hasManagedBouquetInstalled() in quel plugin) - in quel caso un update dei
settings si comporta esattamente come prima, senza toccare nulla di questo."""

import os

from Plugins.Extensions.SettingsHub.config import config as hubConfig

LAMEDB_PATH = "/etc/enigma2/lamedb"
TERRESTRIAL_NAMESPACE = "eeee0000"  # DVB-T, confrontato case-insensitive come fa NGsetting


def shouldRescanForLCN():
	"""True se e' presente un bouquet che LCNScanner gestisce (a prescindere
	da quale metodo - scan o preserve - sia configurato per ricostruirlo)."""
	try:
		from Plugins.SystemPlugins.LCNScanner.plugin import hasManagedBouquetInstalled
	except ImportError:
		return False
	try:
		return hasManagedBouquetInstalled()
	except Exception as err:
		print(f"[SettingsHub] Warning: hasManagedBouquetInstalled() failed, skipping the LCN rebuild.  ({err})")
		return False


def rebuildMethod():
	"""'scan' o 'preserve', dal config (vedi screens/setup.py)."""
	return hubConfig.plugins.settingshub.lcn_rebuild_method.value


# --- Metodo "scan": vera scansione DVB-T, eseguita DOPO l'installazione -----

def _buildTerrestrialOnlyScanList():
	"""[{'transponders': [...], 'feid': slot, 'flags': 0}, ...] per ogni tuner
	compatibile DVB-T configurato (di solito uno solo), nello stesso formato
	che Screens.ServiceScan.ServiceScan si aspetta in scanList=. flags=0 (non
	eComponentScan.scanRemoveServices) vuol dire: aggiungi/aggiorna i servizi
	trovati, non toccare quelli gia' presenti che questa scansione non rivede
	(es. i satellitari) e non rimuovere nulla."""
	from Components.NimManager import nimmanager
	from Screens.ScanSetup import getInitialTerrestrialTransponderList

	scanList = []
	for nim in nimmanager.nim_slots:
		if not nim.canBeCompatible("DVB-T"):
			continue
		if nim.config.dvbt.configMode.value == "nothing":
			continue
		tlist = []
		getInitialTerrestrialTransponderList(tlist, nim.config.dvbt.terrestrial.value, False)
		if tlist:
			scanList.append({"transponders": tlist, "feid": nim.slot, "flags": 0})
	return scanList


def startRescan(session, finished_cb):
	"""Avvia una scansione DVB-T (solo aggiunta, nessuna rimozione) sul/sui
	tuner terrestri gia' configurati, senza toccare satellite o cavo e senza
	mostrare nessuna schermata di scelta transponder - solo il progresso
	della scansione vera e propria (ServiceScan). Quando la scansione finisce,
	ServiceScan.py chiama gia' da solo LCNScanner().lcnScan() per ricostruire
	il bouquet (vedi Plugins/SystemPlugins/LCNScanner/plugin.py); noi
	aspettiamo che finisca anche quello e SOLO A QUEL PUNTO chiudiamo la
	schermata da soli (ServiceScan normalmente resta aperta ad aspettare OK/
	Chiudi dall'utente, cosa che qui non arriverebbe mai).

	finished_cb() viene chiamata a schermata chiusa. Se non c'e' nessun tuner
	DVB-T configurato, viene chiamata subito, senza aprire nulla."""
	from enigma import eTimer
	from Screens.ServiceScan import ServiceScan

	scanList = _buildTerrestrialOnlyScanList()
	if not scanList:
		print("[SettingsHub] No configured DVB-T tuner found, skipping the rescan for LCNScanner.")
		finished_cb()
		return

	scanScreen = session.open(ServiceScan, scanList=scanList)

	# ServiceScan.runLCNScanner() e' chiamata da ServiceScan stessa (vedi
	# Screens/ServiceScan.py) appena lo scan finisce; il suo stesso codice,
	# 2 secondi dopo che il rebuild e' completato, nasconde solo l'overlay di
	# progresso e lascia la schermata aperta per l'utente. Avvolgendo questo
	# metodo sull'istanza (non tocca ServiceScan.py) sappiamo esattamente
	# quando il rebuild e' partito e possiamo chiudere subito dopo, con un
	# margine di sicurezza sopra quei 2 secondi, invece di aspettare che
	# qualcuno prema OK/Chiudi (che qui non succederebbe mai).
	originalRunLCNScanner = scanScreen.runLCNScanner

	def runLCNScannerThenClose():
		originalRunLCNScanner()
		closeTimer = eTimer()

		def doClose():
			closeTimer.stop()
			try:
				scanScreen.close(True)
			except Exception as err:
				print(f"[SettingsHub] Warning: could not auto-close the scan screen.  ({err})")
			# finished_cb() is deferred by one more tick instead of being called
			# right here: calling it in the same stack frame as close() can hit
			# "Modal open are allowed only from a screen which is modal!" if
			# finished_cb tries to open anything (e.g. a MessageBox) - the
			# session hasn't finished promoting the previous screen back to the
			# front yet at this exact point.
			yieldTimer = eTimer()

			def callFinished():
				yieldTimer.stop()
				finished_cb()

			yieldTimer.callback.append(callFinished)
			yieldTimer.start(0, True)
			scanScreen._lcnYieldTimer = yieldTimer

		closeTimer.callback.append(doClose)
		closeTimer.startLongTimer(4)
		scanScreen._lcnAutoCloseTimer = closeTimer  # tiene viva la reference

	scanScreen.runLCNScanner = runLCNScannerThenClose


# --- Metodo "preserve": nessuno scan, ririniezione del lamedb vecchio ------

def capturePreservedLamedb():
	"""Da chiamare PRIMA che _applyChannelList() (archive_installer.py)
	sovrascriva il lamedb: estrae le righe transponder/servizi DVB-T (le
	stesse tre/due righe per voce che scrive lamedb, individuate dal
	namespace EEEE0000, esattamente come NGsetting) e le ritorna come
	{'transponders': [...righe...], 'services': [...righe...]}, o None se il
	lamedb non esiste o non contiene nessuna voce terrestre."""
	if not os.path.exists(LAMEDB_PATH):
		return None
	try:
		with open(LAMEDB_PATH, "r", encoding="utf-8", errors="ignore") as f:
			lines = f.readlines()
	except OSError as err:
		print(f"[SettingsHub] Warning: could not read the old lamedb to preserve DVB-T entries.  ({err})")
		return None

	transponders = []
	services = []
	section = None  # None | "transponders" | "services"
	found = False
	i = 0
	n = len(lines)
	while i < n:
		stripped = lines[i].strip()
		if stripped in ("transponders", "services"):
			section = stripped
			i += 1
			continue
		if stripped == "end":
			section = None
			i += 1
			continue
		if section == "transponders" and TERRESTRIAL_NAMESPACE in lines[i].lower():
			# Una voce di transponder e' sempre 3 righe: intestazione + 2 di dati.
			transponders.extend(lines[i:i + 3])
			found = True
			i += 3
			continue
		if section == "services" and TERRESTRIAL_NAMESPACE in lines[i].lower():
			# Una voce di servizio e' sempre 3 righe: intestazione + 2 di dati.
			services.extend(lines[i:i + 3])
			found = True
			i += 3
			continue
		i += 1

	if not found:
		return None
	return {"transponders": transponders, "services": services}


def applyPreservedLamedb(data):
	"""Da chiamare DOPO che _applyChannelList() ha scritto il lamedb nuovo e
	fatto il suo reloadServicelist(): reinserisce le righe catturate da
	capturePreservedLamedb() dentro le sezioni 'transponders'/'services' del
	lamedb nuovo, ricarica di nuovo, e chiama direttamente LCNScanner().lcnScan()
	per ricostruire il bouquet - qui non c'e' nessuno scan e quindi nessuno
	ServiceScan che lo farebbe scattare da solo. Puro I/O e chiamate
	eDVBDB/LCNScanner, nessuna sessione/UI: puo' girare nel thread di
	background dell'installazione. Ritorna True se ha fatto qualcosa."""
	if not data or not (data.get("transponders") or data.get("services")):
		return False
	try:
		with open(LAMEDB_PATH, "r", encoding="utf-8", errors="ignore") as f:
			lines = f.readlines()
	except OSError as err:
		print(f"[SettingsHub] Error: could not read the new lamedb to re-inject preserved DVB-T entries.  ({err})")
		return False

	out = []
	for line in lines:
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
		print(f"[SettingsHub] Error: could not write the new lamedb with the preserved DVB-T entries.  ({err})")
		return False

	from enigma import eDVBDB
	eDVBDB.getInstance().reloadServicelist()

	try:
		from Plugins.SystemPlugins.LCNScanner.plugin import LCNScanner
		LCNScanner().lcnScan()
	except Exception as err:
		print(f"[SettingsHub] Error: could not rebuild the LCN bouquet from the preserved lamedb.  ({err})")
		return False
	print("[SettingsHub] LCN bouquet rebuilt from the preserved (pre-update) lamedb, no DVB-T rescan.")
	return True
