# -*- coding: utf-8 -*-
from Components.ActionMap import HelpableActionMap
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry, ConfigNothing, ConfigSelection
from Components.Label import Label
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup as SystemSetup

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub import lcn_integration
from Plugins.Extensions.SettingsHub.autocheck import autoCheckService
from Plugins.Extensions.SettingsHub.config import config, persist
from Plugins.Extensions.SettingsHub.credits import CREDITS
from Plugins.Extensions.SettingsHub.language import _

try:
	from Plugins.SystemPlugins.LCNScanner.plugin import hasManagedBouquetInstalled  # noqa: F401
	_LCNSCANNER_INSTALLED = True
except ImportError:
	_LCNSCANNER_INSTALLED = False


class HubSetup(ConfigListScreen, Screen):
	"""Impostazioni generali: quale setting man usare e quando controllare
	aggiornamenti. Skin di sistema 'Setup'. 'Azzera i setting' e' rara e
	distruttiva, quindi sta dietro al tasto MENU invece che in lista.

	Fa anche da configurazione guidata al primo avvio (firstRun=True): tasto
	rosso disabilitato e serve un setting man scelto per poter salvare."""

	skin = SystemSetup.skin

	def __init__(self, session, firstRun=False):
		Screen.__init__(self, session)
		self.firstRun = firstRun
		self.setTitle(_("SettingsHub setup wizard") if firstRun else _("SettingsHub settings"))
		self.skinName = ["Setup"]

		providers = api.getProviders()
		providerChoices = [(p.id, p.name) for p in providers] or [("", _("No setting man installed"))]
		currentActive = config.plugins.settingshub.active_provider_id.value
		if currentActive not in [c[0] for c in providerChoices]:
			currentActive = providerChoices[0][0]
		self.activeProviderConfig = ConfigSelection(default=providerChoices[0][0], choices=providerChoices)
		self.activeProviderConfig.value = currentActive

		self.favoritesEntry = getConfigListEntry(_("Bouquets to preserve (OK to choose)"), ConfigNothing())

		self.list = [
			getConfigListEntry(_("Setting man to use"), self.activeProviderConfig),
			getConfigListEntry(_("Check for new settings"), config.plugins.settingshub.autocheck_interval),
			getConfigListEntry(_("Check time"), config.plugins.settingshub.autocheck_time),
			getConfigListEntry(_("Notify only (don't install automatically)"), config.plugins.settingshub.autocheck_notify_only),
			self.favoritesEntry,
		]
		# Entrambe solo se LCNScanner e' installato: il toggle abilita/disabilita
		# lo scan DVB-T + ricostruzione bouquet automatici dopo un update dei
		# settings (vedi screens/browser.py e lcn_integration.py); l'azione sotto
		# fa la stessa cosa ma subito, a comando, indipendentemente dal toggle.
		self.restoreLCNEntry = None
		if _LCNSCANNER_INSTALLED:
			self.list.append(getConfigListEntry(_("Recreate LCN bouquet after settings update"), config.plugins.settingshub.recreate_lcn_after_update))
			self.list.append(getConfigListEntry(_("Rebuild method"), config.plugins.settingshub.lcn_rebuild_method))
			self.restoreLCNEntry = getConfigListEntry(_("Recreate LCN bouquet now (DVB-T) - OK to run"), ConfigNothing())
			self.list.append(self.restoreLCNEntry)

		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry, fullUI=True)
		# Il skin di sistema 'Setup' si aspetta anche questi due widget
		# (li crea normalmente Screens.Setup.Setup, che qui non chiamiamo).
		self["footnote"] = Label()
		self["footnote"].hide()
		descriptionText = (
			_("Welcome! Choose which setting man to use and when to check for updates, then save.")
			if firstRun else _("MENU to reset the installed settings.")
		)
		self["description"] = Label(descriptionText + "\n\n" + CREDITS)

		actions = {"green": (self.keySave, _("Save"))}
		if not firstRun:
			actions["red"] = (self.keyCancel, _("Cancel"))
		self["setupActions"] = HelpableActionMap(self, ["ColorActions"], actions, prio=0, description=_("SettingsHub actions"))
		self["menuActions"] = HelpableActionMap(self, ["MenuActions"], {
			"menu": (self._confirmReset, _("Reset installed settings")),
		}, prio=0, description=_("SettingsHub actions"))
		if firstRun:
			self["key_red"].setText("")

	def changedEntry(self):
		pass

	def keySelect(self):
		if self["config"].getCurrent() is self.favoritesEntry:
			from Plugins.Extensions.SettingsHub.screens.choose_favorites import openChooseFavorites
			openChooseFavorites(self.session)
			return
		if self.restoreLCNEntry is not None and self["config"].getCurrent() is self.restoreLCNEntry:
			self._confirmRestoreLCN()
			return
		ConfigListScreen.keySelect(self)

	def _confirmRestoreLCN(self):
		if not lcn_integration.shouldRescanForLCN():
			self.session.open(MessageBox, _("No LCN bouquet found: run 'LCN Scanner' at least once first."), MessageBox.TYPE_INFO, timeout=5)
			return
		self.session.openWithCallback(self._onRestoreLCNConfirmed, MessageBox, _("Rescan the DVB-T tuner now and rebuild the LCN bouquet from it?"), MessageBox.TYPE_YESNO, default=True)

	def _onRestoreLCNConfirmed(self, confirmed):
		if not confirmed:
			return
		lcn_integration.startRescan(self.session, self._onRestoreLCNDone)

	def _onRestoreLCNDone(self, *unused_result):
		self.session.open(MessageBox, _("Done: DVB-T tuner rescanned and the LCN bouquet rebuilt."), MessageBox.TYPE_INFO, timeout=5)

	def _confirmReset(self):
		if self.firstRun:
			return  # niente da azzerare prima ancora di aver scelto e salvato
		providerName = self.activeProviderConfig.getText()
		self.session.openWithCallback(
			self._onResetConfirmed,
			MessageBox,
			_("Delete ALL current channels and bouquets and forget the setting installed for '%s'?\nThis cannot be undone: use it to start fresh and re-download everything.") % providerName,
			MessageBox.TYPE_YESNO,
			default=False,
		)

	def _onResetConfirmed(self, confirmed):
		if not confirmed:
			return
		from Plugins.Extensions.SettingsHub import reset
		reset.resetChannelData()
		reset.resetProviderInstalledInfo(self.activeProviderConfig.value)
		self.session.open(MessageBox, _("Done: channels reset and setting forgotten. You can now reinstall from scratch."), MessageBox.TYPE_INFO, timeout=5)

	def keySave(self):
		if not self.activeProviderConfig.value:
			self.session.open(MessageBox, _("No setting man available: install a setting man plugin and try again."), MessageBox.TYPE_WARNING, timeout=5)
			return
		config.plugins.settingshub.active_provider_id.value = self.activeProviderConfig.value
		config.plugins.settingshub.active_provider_id.save()
		ConfigListScreen.keySave(self)
		autoCheckService.scheduleNext()
		if not config.plugins.settingshub.configured.value:
			config.plugins.settingshub.configured.value = True
			config.plugins.settingshub.configured.save()
		persist()
