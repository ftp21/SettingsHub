# -*- coding: utf-8 -*-
"""Scheduler del controllo automatico nuovi setting, intervallo/orario
configurabile dall'utente (vedi config.py). Non blocca mai il thread GUI:
ogni provider viene interrogato dentro api.runInThread.

Lo scheduling e' ancorato all'orologio/last_check, non al momento del boot:
molti decoder vanno ogni giorno in standby profondo con wakeup RTC, quindi
la sessione enigma2 non arriva mai a 24h continue di uptime. Un timer
relativo avviato da zero ad ogni SessionStart (come startLongTimer(24h))
non scatta mai in quel caso. Ricalcolando qui "quanti secondi mancano"
rispetto a un orario fisso (per "daily") o all'ultimo check riuscito (per
6h/12h), il riavvio giornaliero non azzera piu' il progresso."""
import time

from enigma import eTimer

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub.config import config, getActiveProvider, persist, setInstalledInfo, AUTOCHECK_INTERVAL_SECONDS
from Plugins.Extensions.SettingsHub.language import _


class AutoCheckService:
	def __init__(self):
		self.session = None
		self.timer = eTimer()
		self.timer.callback.append(self.runCheck)
		self._checking = False

	def gotSession(self, session):
		self.session = session
		self.scheduleNext()

	def scheduleNext(self):
		self.timer.stop()
		interval = config.plugins.settingshub.autocheck_interval.value
		if interval == "off":
			return
		if interval == "daily":
			seconds = self._secondsUntilNextDailySlot()
		else:
			intervalSeconds = AUTOCHECK_INTERVAL_SECONDS.get(interval)
			if not intervalSeconds:
				return
			seconds = self._secondsUntilNextRelativeSlot(intervalSeconds)
		self.timer.startLongTimer(max(int(seconds), 1))

	def _lastCheckEpoch(self):
		raw = config.plugins.settingshub.last_check.value
		if not raw:
			return None
		try:
			return time.mktime(time.strptime(raw, "%Y-%m-%d %H:%M:%S"))
		except ValueError:
			return None

	CATCH_UP_DELAY = 120  # secondi: margine per lasciare respirare l'avvio sessione/rete
	CATCH_UP_THRESHOLD = 20 * 3600  # secondi

	def _secondsUntilNextDailySlot(self):
		"""Prossimo orario configurato (autocheck_time): oggi se non ancora
		passato, altrimenti domani. Ricalcolato da zero ad ogni chiamata,
		quindi non serve restare accesi 24h filate perche' il check scatti.

		Caso da non rompere di nuovo: un decoder che va ogni giorno in
		standby profondo e si risveglia SEMPRE dopo l'orario configurato
		(es. sveglia alle 9-10, target 06:00) non e' mai acceso esattamente
		a quell'ora - se ci limitassimo a "rimanda a domani alla stessa ora"
		il check non scatterebbe mai, in pratica lo stesso bug di prima solo
		spostato. Se l'ultimo check risale a piu' di CATCH_UP_THRESHOLD fa
		(o non e' mai stato fatto), consideriamo lo slot di oggi "perso per
		spegnimento" e recuperiamo a breve invece di aspettare un altro
		giorno intero."""
		lastCheck = self._lastCheckEpoch()
		now = time.time()
		if lastCheck is None or (now - lastCheck) >= self.CATCH_UP_THRESHOLD:
			return self.CATCH_UP_DELAY

		hour, minute = config.plugins.settingshub.autocheck_time.value
		local = time.localtime(now)
		target = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, hour, minute, 0, 0, 0, -1))
		if target <= now:
			target += 24 * 3600
		return target - now

	def _secondsUntilNextRelativeSlot(self, intervalSeconds):
		"""Per 6h/12h: ancorato all'ultimo check riuscito (config.last_check),
		non al boot corrente - un riavvio a meta' intervallo non fa ripartire
		il conto da capo. Se non c'e' ancora mai stato un check, parte
		dall'intervallo pieno."""
		lastCheck = self._lastCheckEpoch()
		if lastCheck is None:
			return intervalSeconds
		remaining = (lastCheck + intervalSeconds) - time.time()
		return remaining if remaining > 0 else 1

	def checkNow(self, resultCallback=None):
		"""Avvia un check manuale/automatico. resultCallback(updates), dove
		updates e' una lista di tuple (provider, SettingEntry) - chiamata sul
		thread GUI a fine lavoro. Non fa nulla se un check e' gia' in corso."""
		if self._checking:
			return False
		self._checking = True

		provider = getActiveProvider()

		def work():
			if provider is None:
				return []
			try:
				entry = provider.checkForUpdates()
			except Exception as e:
				print(f"[SettingsHub] checkForUpdates fallito per '{provider.id}': {e}")
				return []
			return [(provider, entry)] if entry is not None else []

		def done(result, error):
			self._checking = False
			config.plugins.settingshub.last_check.value = time.strftime("%Y-%m-%d %H:%M:%S")
			config.plugins.settingshub.last_check.save()
			persist()
			updates = result or []
			if error:
				print(f"[SettingsHub] Errore durante il check automatico: {error}")
			if resultCallback:
				resultCallback(updates)
			elif updates and self.session:
				if config.plugins.settingshub.autocheck_notify_only.value:
					self._notify(updates)
				else:
					self._autoInstall(updates[0])

		api.runInThread(work, done)
		return True

	def _notify(self, updates):
		from Screens.MessageBox import MessageBox
		names = ", ".join(f"{p.name} ({e.date or e.name})" for p, e in updates)
		self.session.open(
			MessageBox,
			_("New settings available for: %s") % names,
			MessageBox.TYPE_INFO,
			timeout=10,
		)

	def _autoInstall(self, update):
		# 'Solo notifica' su No: scarica ed applica subito, stesso percorso
		# usato per un'installazione manuale (browser.py).
		provider, entry = update

		def progress(percent, message=""):
			pass

		def installDone(success, message=""):
			if success:
				setInstalledInfo(provider.id, entry)
			self._notifyInstallResult(provider, entry, success, message)

		try:
			provider.install(entry, progress, installDone)
		except Exception as e:
			print(f"[SettingsHub] Installazione automatica fallita per '{provider.id}': {e}")
			self._notifyInstallResult(provider, entry, False, str(e))

	def _notifyInstallResult(self, provider, entry, success, message):
		from Screens.MessageBox import MessageBox
		if not self.session:
			return
		if success:
			text = _("New setting installed automatically for %s:\n%s") % (provider.name, message or entry.name)
			msgType = MessageBox.TYPE_INFO
		else:
			text = _("Automatic install failed for %s:\n%s") % (provider.name, message or entry.name)
			msgType = MessageBox.TYPE_ERROR
		self.session.open(MessageBox, text, msgType, timeout=10)

	def runCheck(self):
		self.checkNow()
		self.scheduleNext()


autoCheckService = AutoCheckService()
