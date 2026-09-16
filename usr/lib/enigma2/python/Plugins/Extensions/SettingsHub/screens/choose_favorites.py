# -*- coding: utf-8 -*-
"""
Scelta di QUALI bouquet preservare attraverso un cambio di setting (non
necessariamente 'digitale terrestre': puo' essere qualsiasi bouquet). Lista
multiselezione vera (Components.SelectionList, lo stesso widget usato per le
selezioni multiple in giro per Enigma2): OK alterna la spunta, niente
scorciatoie numeriche ne' altro."""
import json

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.SelectionList import SelectionEntryComponent, SelectionList
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Plugins.Extensions.SettingsHub import favorites
from Plugins.Extensions.SettingsHub.config import config, persist
from Plugins.Extensions.SettingsHub.language import _


class ChooseFavorites(Screen):
	skin = """
	<screen name="ChooseFavorites" position="center,center" size="900,540" resolution="1280,720" title="SettingsHub">
		<widget name="title" position="10,10" size="880,30" font="Regular;22" />
		<widget name="list" position="10,50" size="880,420" scrollbarMode="showOnDemand" />
		<widget name="key_red" position="10,e-50" size="290,40" backgroundColor="#00A03030" halign="center" valign="center" font="Regular;20" />
		<widget name="key_green" position="305,e-50" size="290,40" backgroundColor="#0030A030" halign="center" valign="center" font="Regular;20" />
		<widget name="key_yellow" position="600,e-50" size="290,40" backgroundColor="#00A0A030" halign="center" valign="center" font="Regular;20" />
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Scegli i bouquet da preservare"))
		self["title"] = Label(_("Scegli i bouquet da preservare nei prossimi setting - OK per selezionare/deselezionare"))

		self.bouquets = favorites.listUserBouquets()  # [(fileName, title), ...]
		selected = self._loadSelection()

		self["list"] = SelectionList()
		for index, (fileName, title) in enumerate(self.bouquets):
			self["list"].addSelection(title, fileName, index, fileName in selected)

		self["key_red"] = Label(_("Annulla"))
		self["key_green"] = Label(_("Salva"))
		self["key_yellow"] = Label(_("Tutti/Nessuno"))

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "NavigationActions"], {
			"cancel": self.close,
			"red": self.close,
			"ok": self["list"].toggleSelection,
			"select": self["list"].toggleSelection,
			"green": self.save,
			"yellow": self.toggleAllSelection,
			"up": self["list"].up,
			"down": self["list"].down,
			"pageUp": self["list"].pageUp,
			"pageDown": self["list"].pageDown,
			"top": self["list"].goTop,
			"bottom": self["list"].goBottom,
		}, -1)

	def toggleAllSelection(self):
		"""SelectionList.toggleAllSelection() di sistema fa un NOT su ogni
		voce (chi era selezionato si deseleziona e viceversa): qui invece
		vogliamo un vero 'seleziona tutti' / 'deseleziona tutti' - se anche
		una sola voce non e' selezionata, il tasto le seleziona tutte;
		altrimenti le deseleziona tutte."""
		lst = self["list"]
		allSelected = all(item[0][3] for item in lst.list)
		newState = not allSelected
		lst.list = [
			SelectionEntryComponent(item[0][0], item[0][1], item[0][2], newState)
			for item in lst.list
		]
		lst.setList(lst.list)

	def _loadSelection(self):
		# Default: NESSUN bouquet selezionato. L'utente deve scegliere
		# esplicitamente quali preservare, mai il contrario.
		raw = config.plugins.settingshub.favorites_selection.value
		try:
			return set(json.loads(raw)) if raw else set()
		except ValueError:
			return set()

	def save(self):
		selected = {fileName for _description, fileName, _index in self["list"].getSelectionsList()}
		config.plugins.settingshub.favorites_selection.value = json.dumps(sorted(selected))
		config.plugins.settingshub.favorites_selection.save()
		persist()
		self.close()


def openChooseFavorites(session):
	if not favorites.listUserBouquets():
		session.open(MessageBox, _("Nessun bouquet personale trovato."), MessageBox.TYPE_INFO, timeout=5)
		return
	session.open(ChooseFavorites)
