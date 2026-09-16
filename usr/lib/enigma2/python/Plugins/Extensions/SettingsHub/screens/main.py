# -*- coding: utf-8 -*-
"""
Punto d'ingresso di SettingsHub, in stile EPGImport:
  - primo avvio (nessuna configurazione salvata): apre la configurazione
    guidata (screens/setup.py in modalita' firstRun) prima di qualunque altra
    cosa - l'utente sceglie li' quale (uno solo) setting man usare e quando
    controllare i nuovi setting;
  - avvii successivi: va dritto alla schermata a due colonne del setting man
    attivo (screens/browser.py). Da li', MENU -> 'Cambia setting man' riapre
    la configurazione per sceglierne un altro."""
from Screens.MessageBox import MessageBox

from Plugins.Extensions.SettingsHub.config import config, getActiveProvider
from Plugins.Extensions.SettingsHub.language import _
from Plugins.Extensions.SettingsHub.screens.browser import SettingsBrowser
from Plugins.Extensions.SettingsHub.screens.setup import HubSetup


def Main(session, **kwargs):
	if not config.plugins.settingshub.configured.value:
		session.openWithCallback(lambda *a: _afterFirstRun(session), HubSetup, firstRun=True)
		return
	_openActiveProvider(session)


def _afterFirstRun(session):
	if config.plugins.settingshub.configured.value:
		_openActiveProvider(session)
	# altrimenti l'utente ha annullato senza salvare: si riprovera' la
	# prossima volta che apre il plugin.


def _openActiveProvider(session):
	provider = getActiveProvider()
	if provider is None:
		session.open(MessageBox, _("Nessun setting man installato."), MessageBox.TYPE_INFO, timeout=5)
		return
	# SettingsBrowser puo' chiudersi con self.close() SENZA argomenti (es. il
	# tasto rosso/Esci, che nell'ActionMap e' collegato direttamente a
	# self.close): la callback deve accettare zero o piu' argomenti, mai
	# esigerne esattamente uno.
	session.openWithCallback(lambda *result: _onBrowserClosed(session, result[0] if result else None), SettingsBrowser, provider)


def _onBrowserClosed(session, result):
	if result == "__switch__":
		session.openWithCallback(lambda *a: _openActiveProvider(session), HubSetup)
