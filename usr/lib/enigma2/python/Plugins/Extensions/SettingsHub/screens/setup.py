# -*- coding: utf-8 -*-
from Components.ActionMap import HelpableActionMap
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry, ConfigNothing, ConfigSelection
from Components.Label import Label
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup as SystemSetup

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub.autocheck import autoCheckService
from Plugins.Extensions.SettingsHub.config import config, persist
from Plugins.Extensions.SettingsHub.credits import CREDITS
from Plugins.Extensions.SettingsHub.language import _


class HubSetup(ConfigListScreen, Screen):
	"""Impostazioni generali di SettingsHub: quando controllare i nuovi
	setting e QUALE (uno solo) setting man usare. Nessuno skin custom: usa
	esattamente lo skin di sistema per 'Setup' (skinName=['Setup']), lo
	stesso di ogni altra schermata di configurazione Enigma2.

	'Bouquet da preservare' e' una riga normale: si usa abbastanza spesso da
	meritare di essere visibile. 'Azzera i setting' invece e' rarissima e
	distruttiva: sta dietro al tasto MENU (qui in Impostazioni, non nella
	schermata principale che si usa in continuazione), senza nemmeno un
	sottomenu visto che e' l'unica voce li' dentro.

	Fa anche da configurazione guidata al primo avvio (firstRun=True): in tal
	caso il tasto rosso e' disabilitato (non si puo' annullare una
	configurazione che non esiste ancora) e serve un setting man scelto per
	poter salvare."""

	skin = SystemSetup.skin

	def __init__(self, session, firstRun=False):
		Screen.__init__(self, session)
		self.firstRun = firstRun
		self.setTitle(_("Configurazione guidata SettingsHub") if firstRun else _("Impostazioni SettingsHub"))
		self.skinName = ["Setup"]

		providers = api.getProviders()
		providerChoices = [(p.id, p.name) for p in providers] or [("", _("Nessun setting man installato"))]
		currentActive = config.plugins.settingshub.active_provider_id.value
		if currentActive not in [c[0] for c in providerChoices]:
			currentActive = providerChoices[0][0]
		self.activeProviderConfig = ConfigSelection(default=providerChoices[0][0], choices=providerChoices)
		self.activeProviderConfig.value = currentActive

		self.favoritesEntry = getConfigListEntry(_("Bouquet da preservare (OK per scegliere)"), ConfigNothing())

		self.list = [
			getConfigListEntry(_("Setting man da usare"), self.activeProviderConfig),
			getConfigListEntry(_("Controlla nuovi setting"), config.plugins.settingshub.autocheck_interval),
			getConfigListEntry(_("Orario del controllo"), config.plugins.settingshub.autocheck_time),
			getConfigListEntry(_("Solo notifica (non installare da solo)"), config.plugins.settingshub.autocheck_notify_only),
			self.favoritesEntry,
		]

		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry, fullUI=True)
		# Il skin di sistema 'Setup' si aspetta anche questi due widget
		# (li crea normalmente Screens.Setup.Setup, che qui non chiamiamo).
		self["footnote"] = Label()
		self["footnote"].hide()
		descriptionText = (
			_("Benvenuto! Scegli il setting man da usare e quando controllare i nuovi setting, poi salva.")
			if firstRun else _("MENU per azzerare i setting installati (ripristina base).")
		)
		self["description"] = Label(descriptionText + "\n\n" + CREDITS)

		actions = {"green": (self.keySave, _("Salva"))}
		if not firstRun:
			actions["red"] = (self.keyCancel, _("Annulla"))
		self["setupActions"] = HelpableActionMap(self, ["ColorActions"], actions, prio=0, description=_("Azioni SettingsHub"))
		self["menuActions"] = HelpableActionMap(self, ["MenuActions"], {
			"menu": (self._confirmReset, _("Azzera i setting installati")),
		}, prio=0, description=_("Azioni SettingsHub"))
		if firstRun:
			self["key_red"].setText("")

	def changedEntry(self):
		pass

	def keySelect(self):
		if self["config"].getCurrent() is self.favoritesEntry:
			from Plugins.Extensions.SettingsHub.screens.choose_favorites import openChooseFavorites
			openChooseFavorites(self.session)
			return
		ConfigListScreen.keySelect(self)

	def _confirmReset(self):
		if self.firstRun:
			return  # niente da azzerare prima ancora di aver scelto e salvato
		providerName = self.activeProviderConfig.getText()
		self.session.openWithCallback(
			self._onResetConfirmed,
			MessageBox,
			_("Cancellare TUTTI i canali e bouquet attuali e dimenticare il setting installato per '%s'?\nNon torna indietro: serve per ripartire da una base pulita e riscaricare tutto da capo.") % providerName,
			MessageBox.TYPE_YESNO,
			default=False,
		)

	def _onResetConfirmed(self, confirmed):
		if not confirmed:
			return
		from Plugins.Extensions.SettingsHub import reset
		reset.resetChannelData()
		reset.resetProviderInstalledInfo(self.activeProviderConfig.value)
		self.session.open(MessageBox, _("Fatto: canali azzerati e setting dimenticato. Ora puoi reinstallare da capo."), MessageBox.TYPE_INFO, timeout=5)

	def keySave(self):
		if not self.activeProviderConfig.value:
			self.session.open(MessageBox, _("Nessun setting man disponibile: installa un plugin setting man e riprova."), MessageBox.TYPE_WARNING, timeout=5)
			return
		config.plugins.settingshub.active_provider_id.value = self.activeProviderConfig.value
		config.plugins.settingshub.active_provider_id.save()
		ConfigListScreen.keySave(self)
		autoCheckService.scheduleNext()
		if not config.plugins.settingshub.configured.value:
			config.plugins.settingshub.configured.value = True
			config.plugins.settingshub.configured.save()
		persist()
