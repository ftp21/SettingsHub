# -*- coding: utf-8 -*-
"""
Schermata principale di un setting man, stile EPGImport: due colonne fisse,
categorie a sinistra ed entry della categoria selezionata a destra. Skin
generica (nessun colore/font hardcoded oltre quelli di default), sovrascrivibile
da una skin esterna che ridefinisca '<screen name="SettingsBrowser">'."""
from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Plugins.Extensions.SettingsHub import abm_integration
from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub import lcn_integration
from Plugins.Extensions.SettingsHub.config import config, getInstalledInfo, setInstalledInfo
from Plugins.Extensions.SettingsHub.credits import CREDITS
from Plugins.Extensions.SettingsHub.language import _


class SettingsBrowser(Screen):
	skin = """
	<screen name="SettingsBrowser" position="center,center" size="980,570" resolution="1280,720" title="SettingsHub">
		<widget name="titleLeft" position="10,10" size="300,30" font="Regular;22" />
		<widget name="titleRight" position="320,10" size="650,30" font="Regular;22" />
		<eLabel position="10,44" size="300,1" backgroundColor="#00666666" />
		<eLabel position="320,44" size="650,1" backgroundColor="#00666666" />
		<widget name="categories" position="10,50" size="300,400" scrollbarMode="showOnDemand" />
		<widget name="entries" position="320,50" size="650,400" scrollbarMode="showOnDemand" />
		<widget name="info" position="10,455" size="960,40" font="Regular;18" valign="center" />
		<widget name="credits" position="10,495" size="960,20" font="Regular;14" halign="right" foregroundColor="#00888888" />
		<widget name="key_red" position="10,e-50" size="230,40" backgroundColor="#00A03030" halign="center" valign="center" font="Regular;20" />
		<widget name="key_green" position="250,e-50" size="230,40" backgroundColor="#0030A030" halign="center" valign="center" font="Regular;20" />
		<widget name="key_yellow" position="490,e-50" size="230,40" backgroundColor="#00A0A030" halign="center" valign="center" font="Regular;20" />
		<widget name="key_blue" position="730,e-50" size="230,40" backgroundColor="#003030A0" halign="center" valign="center" font="Regular;20" />
	</screen>"""

	def __init__(self, session, provider):
		Screen.__init__(self, session)
		self.provider = provider
		self.setTitle(provider.name)
		self.categories = []
		self.currentEntries = []
		self._deferTimer = None

		self["titleLeft"] = Label(_("Categories"))
		self["titleRight"] = Label(_("Packages"))
		self["categories"] = MenuList([])
		self["entries"] = MenuList([])
		self["info"] = Label(_("Loading categories..."))
		self["credits"] = Label(CREDITS)
		self["key_red"] = Label(_("Exit"))
		self["key_green"] = Label(_("Install"))
		self["key_yellow"] = Label(_("Refresh"))
		self["key_blue"] = Label(_("Setup"))

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "NavigationActions"], {
			"cancel": self.close,
			"red": self.close,
			"green": self.keyInstall,
			"ok": self.keyInstall,
			"yellow": self.refresh,
			"blue": self.openSettings,
			"left": self.focusCategories,
			"right": self.focusEntries,
			"up": self.keyUp,
			"down": self.keyDown,
			"pageUp": self.keyPageUp,
			"pageDown": self.keyPageDown,
			"top": self.keyTop,
			"bottom": self.keyBottom,
		}, -1)

		self.focusedList = "categories"
		self["entries"].selectionEnabled(0)
		self["categories"].onSelectionChanged.append(self.updateEntries)
		self.onLayoutFinish.append(self.refresh)

	# --- focus tra le due colonne -----------------------------------
	def focusCategories(self):
		self.focusedList = "categories"
		self["categories"].selectionEnabled(1)
		self["entries"].selectionEnabled(0)

	def focusEntries(self):
		if not self.currentEntries:
			return
		self.focusedList = "entries"
		self["entries"].selectionEnabled(1)
		self["categories"].selectionEnabled(0)

	def keyUp(self):
		self[self.focusedList].up()

	def keyDown(self):
		self[self.focusedList].down()

	def keyPageUp(self):
		self[self.focusedList].pageUp()

	def keyPageDown(self):
		self[self.focusedList].pageDown()

	def keyTop(self):
		self[self.focusedList].goTop()

	def keyBottom(self):
		self[self.focusedList].goBottom()

	# --- caricamento dati ---------------------------------------------
	def refresh(self):
		self["info"].setText(_("Loading categories..."))

		def work():
			return self.provider.getCategories()

		api.runInThread(work, self._onCategoriesLoaded)

	def _onCategoriesLoaded(self, categories, error):
		if error:
			self["info"].setText(_("Error: %s") % error)
			return
		self.categories = categories or []
		self["categories"].setList([c.name for c in self.categories])
		self.updateEntries()
		self._updateInfo()

	def updateEntries(self):
		index = self["categories"].getSelectionIndex() if self.categories else None
		if index is None or index < 0 or index >= len(self.categories):
			self["entries"].setList([])
			self.currentEntries = []
			return
		category = self.categories[index]
		try:
			# Il catalogo e' gia' in cache (scaricato da getCategories()): niente
			# rete qui, va bene chiamarla direttamente sul thread GUI.
			self.currentEntries = self.provider.listEntries(category.id) or []
		except Exception as e:
			self.currentEntries = []
			self["info"].setText(_("Error: %s") % e)
		self["entries"].setList([
			"%s  (%s)" % (e.name, e.date) if e.date else e.name
			for e in self.currentEntries
		])

	def _updateInfo(self):
		installed = getInstalledInfo(self.provider.id)
		if installed:
			self["info"].setText(_("Installed: %s (%s)") % (installed.get("name") or "?", installed.get("date") or "?"))
		else:
			self["info"].setText(_("Nothing installed yet for this provider."))

	# --- installazione ---------------------------------------------
	def keyInstall(self):
		if self.focusedList != "entries" or not self.currentEntries:
			self.focusEntries()
			return
		index = self["entries"].getSelectionIndex()
		if index is None or index < 0 or index >= len(self.currentEntries):
			return
		entry = self.currentEntries[index]
		installed = getInstalledInfo(self.provider.id)
		# Stessa data gia' installata: chiedi conferma esplicita invece di
		# riscaricare in silenzio lo stesso pacchetto.
		if installed and installed.get("name") == entry.name and entry.date and installed.get("date") == entry.date:
			self.session.openWithCallback(
				lambda confirmed: self._onInstallConfirmed(entry, confirmed),
				MessageBox,
				_("'%s' is already installed with this date (%s).\nDownload it again anyway?") % (entry.name, entry.date),
				MessageBox.TYPE_YESNO,
				default=False,
			)
			return
		self.session.openWithCallback(
			lambda confirmed: self._onInstallConfirmed(entry, confirmed),
			MessageBox,
			_("Install '%s'?\n%s") % (entry.name, entry.description or ""),
			MessageBox.TYPE_YESNO,
		)

	def _onInstallConfirmed(self, entry, confirmed):
		if not confirmed:
			return
		# Checked BEFORE the install runs, not after: installing replaces the
		# whole lamedb, so by the time install() returns, any bouquet
		# LCNScanner/ABM manages is already gone from bouquets.tv/radio -
		# checking afterwards would always see "nothing there" and never
		# trigger the rescan this is meant to cause. See lcn_integration.py/
		# abm_integration.py. Only the "scan" method is handled here (it needs
		# a session/UI, which only exists at this point, after install() has
		# returned): "preserve" has already run inside archive_installer.py,
		# in the background thread, before the lamedb was even replaced.
		rescanForLCN = (
			config.plugins.settingshub.recreate_lcn_after_update.value
			and lcn_integration.rebuildMethod() == "scan"
			and lcn_integration.shouldRescanForLCN()
		)
		# Stessa cosa di rescanForLCN sopra, ma per AutoBouquetsMaker (vedi
		# abm_integration.py). Le due cose sono indipendenti - un decoder
		# puo' avere sia LCNScanner sia ABM installati insieme - quindi
		# vengono messe in coda ed eseguite una dopo l'altra (vedi
		# _runRescanChain()) invece che in parallelo, per non litigarsi il
		# tuner.
		rescanForABM = (
			config.plugins.settingshub.recreate_abm_after_update.value
			and abm_integration.rebuildMethod() == "scan"
			and abm_integration.shouldRescanForABM()
		)
		progressBox = self.session.open(MessageBox, _("Installing '%s'...") % entry.name, MessageBox.TYPE_INFO, enable_input=False)

		def progress(percent, message=""):
			pass  # punto di estensione per una barra di progresso reale

		def done(success, message=""):
			if success:
				setInstalledInfo(self.provider.id, entry)
			# Rather than trying to preserve the old references (pointless - the
			# new lamedb doesn't have them), rescan and let LCNScanner/ABM
			# rebuild their bouquet(s) from what the rescan finds.
			pending = []
			if success and rescanForLCN:
				pending.append((lcn_integration.startRescan, _("The DVB-T tuner was rescanned and the LCN bouquet rebuilt."), "could not start the DVB-T rescan for LCNScanner"))
			if success and rescanForABM:
				pending.append((abm_integration.startRescan, _("The ABM bouquet(s) were rebuilt by AutoBouquetsMaker."), "could not start the AutoBouquetsMaker rescan"))
			if pending:
				self._afterClose(progressBox, lambda: self._runRescanChain(pending, success, message, entry))
			else:
				self._afterClose(progressBox, lambda: self._showInstallResult(success, message, entry))

		try:
			self.provider.install(entry, progress, done)
		except Exception as e:
			self._afterClose(progressBox, lambda: self.session.open(MessageBox, _("Could not start the install:\n%s") % e, MessageBox.TYPE_ERROR))

	def _runRescanChain(self, pending, success, message, entry, extraNotes=None):
		"""Esegue 'pending' (lista di (startFn, doneNote, warnLabel), vedi
		_onInstallConfirmed()) una voce alla volta, invece che in parallelo -
		vedi il commento su rescanForABM li'."""
		extraNotes = extraNotes or []
		if not pending:
			self._showInstallResult(success, message, entry, extraNotes=extraNotes)
			return

		startFn, doneNote, warnLabel = pending[0]
		rest = pending[1:]

		def onRescanDone(*unused_result):
			self._runRescanChain(rest, success, message, entry, extraNotes + [doneNote])

		try:
			startFn(self.session, onRescanDone)
		except Exception as err:
			print(f"[SettingsHub] Warning: {warnLabel}.  ({err})")
			self._runRescanChain(rest, success, message, entry, extraNotes)

	def _showInstallResult(self, success, message, entry, extraNotes=None):
		if success:
			self._updateInfo()
			for note in (extraNotes or []):
				message = (message + "\n" if message else "") + note
			self.session.open(MessageBox, _("Install complete:\n%s") % (message or entry.name), MessageBox.TYPE_INFO, timeout=5)
		else:
			self.session.open(MessageBox, _("Install failed:\n%s") % (message or "?"), MessageBox.TYPE_ERROR)

	def _afterClose(self, closeable, fn):
		if closeable is not None:
			try:
				closeable.close()
			except Exception:
				pass
		timer = eTimer()
		self._deferTimer = timer
		timer.callback.append(fn)
		timer.start(0, True)

	# --- azioni secondarie -------------------------------------------
	def openSettings(self):
		from Plugins.Extensions.SettingsHub.screens.setup import HubSetup
		self.session.openWithCallback(self._onSettingsClosed, HubSetup)

	def _onSettingsClosed(self, *args):
		# Se e' stato scelto un altro setting man, chiudi: main.py riapre
		# la schermata sul provider nuovo invece di restare su quello vecchio.
		from Plugins.Extensions.SettingsHub.config import getActiveProvider
		newProvider = getActiveProvider()
		if newProvider is not None and newProvider.id != self.provider.id:
			self.close("__switch__")
