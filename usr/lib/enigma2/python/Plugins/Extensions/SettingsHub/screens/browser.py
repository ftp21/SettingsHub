# -*- coding: utf-8 -*-
"""
Schermata principale di un setting man, in stile EPGImport: due colonne
persistenti, a sinistra le categorie, a destra i setting della categoria
selezionata (niente piu' catena di ChoiceBox). Skin custom (qui non esiste un
template di sistema per un browser a due colonne), ma generica: solo widget
standard, nessun colore/font hardcoded fuori da quelli di default della
skin attiva - una skin che vuole personalizzarla puo' sempre definire il suo
'<screen name="SettingsBrowser">' e questa viene ignorata automaticamente."""
from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub.config import getInstalledInfo, setInstalledInfo
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

		self["titleLeft"] = Label(_("Categorie"))
		self["titleRight"] = Label(_("Setting"))
		self["categories"] = MenuList([])
		self["entries"] = MenuList([])
		self["info"] = Label(_("Caricamento categorie..."))
		self["credits"] = Label(CREDITS)
		self["key_red"] = Label(_("Esci"))
		self["key_green"] = Label(_("Installa"))
		self["key_yellow"] = Label(_("Aggiorna"))
		self["key_blue"] = Label(_("Impostazioni"))

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
		self["info"].setText(_("Caricamento categorie..."))

		def work():
			return self.provider.getCategories()

		api.runInThread(work, self._onCategoriesLoaded)

	def _onCategoriesLoaded(self, categories, error):
		if error:
			self["info"].setText(_("Errore: %s") % error)
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
			# a questo punto il catalogo e' gia' in cache nel provider (lo ha
			# appena scaricato getCategories()): niente rete qui, va bene
			# chiamarla direttamente sul thread GUI.
			self.currentEntries = self.provider.listEntries(category.id) or []
		except Exception as e:
			self.currentEntries = []
			self["info"].setText(_("Errore: %s") % e)
		self["entries"].setList([
			"%s  (%s)" % (e.name, e.date) if e.date else e.name
			for e in self.currentEntries
		])

	def _updateInfo(self):
		installed = getInstalledInfo(self.provider.id)
		if installed:
			self["info"].setText(_("Installato: %s (%s)") % (installed.get("name") or "?", installed.get("date") or "?"))
		else:
			self["info"].setText(_("Nessun setting installato per questo provider."))

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
		# Scarichiamo solo se la data e' diversa da quella gia' installata:
		# se e' lo stesso pacchetto con la stessa data, serve una conferma
		# esplicita in piu' (non un download silenzioso e inutile).
		if installed and installed.get("name") == entry.name and entry.date and installed.get("date") == entry.date:
			self.session.openWithCallback(
				lambda confirmed: self._onInstallConfirmed(entry, confirmed),
				MessageBox,
				_("'%s' e' gia' installato con questa data (%s).\nRiscaricarlo comunque?") % (entry.name, entry.date),
				MessageBox.TYPE_YESNO,
				default=False,
			)
			return
		self.session.openWithCallback(
			lambda confirmed: self._onInstallConfirmed(entry, confirmed),
			MessageBox,
			_("Installare '%s'?\n%s") % (entry.name, entry.description or ""),
			MessageBox.TYPE_YESNO,
		)

	def _onInstallConfirmed(self, entry, confirmed):
		if not confirmed:
			return
		progressBox = self.session.open(MessageBox, _("Installazione di '%s' in corso...") % entry.name, MessageBox.TYPE_INFO, enable_input=False)

		def progress(percent, message=""):
			pass  # punto di estensione: una barra di progresso reale verra' aggiunta in seguito

		def done(success, message=""):
			if success:
				setInstalledInfo(self.provider.id, entry)
			self._afterClose(progressBox, lambda: self._showInstallResult(success, message, entry))

		try:
			self.provider.install(entry, progress, done)
		except Exception as e:
			self._afterClose(progressBox, lambda: self.session.open(MessageBox, _("Errore nell'avviare l'installazione:\n%s") % e, MessageBox.TYPE_ERROR))

	def _showInstallResult(self, success, message, entry):
		if success:
			self._updateInfo()
			self.session.open(MessageBox, _("Installazione completata:\n%s") % (message or entry.name), MessageBox.TYPE_INFO, timeout=5)
		else:
			self.session.open(MessageBox, _("Installazione fallita:\n%s") % (message or "?"), MessageBox.TYPE_ERROR)

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
		# Se in Impostazioni e' stato scelto un altro setting man, questa
		# schermata (gia' legata al provider vecchio) si chiude e main.py la
		# riapre da capo su quello nuovo - non basta tornare qui, altrimenti
		# si vedrebbe ancora la lista del provider precedente.
		from Plugins.Extensions.SettingsHub.config import getActiveProvider
		newProvider = getActiveProvider()
		if newProvider is not None and newProvider.id != self.provider.id:
			self.close("__switch__")
