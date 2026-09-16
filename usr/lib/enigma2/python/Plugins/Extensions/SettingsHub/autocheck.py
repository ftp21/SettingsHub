# -*- coding: utf-8 -*-
"""Scheduler del controllo automatico nuovi setting, intervallo/orario
configurabile dall'utente (vedi config.py). Non blocca mai il thread GUI:
ogni provider viene interrogato dentro api.runInThread."""
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
		seconds = AUTOCHECK_INTERVAL_SECONDS.get(interval)
		if not seconds:
			return
		self.timer.startLongTimer(seconds)

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
