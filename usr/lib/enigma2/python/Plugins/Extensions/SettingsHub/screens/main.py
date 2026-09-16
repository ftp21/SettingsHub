# -*- coding: utf-8 -*-
"""
Punto d'ingresso di SettingsHub: al primo avvio apre la configurazione
guidata (setup.py in modalita' firstRun), poi va dritto al browser del
setting man attivo (browser.py)."""
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
		session.open(MessageBox, _("No setting man installed."), MessageBox.TYPE_INFO, timeout=5)
		return
	# SettingsBrowser puo' chiudersi con self.close() SENZA argomenti (es. il
	# tasto rosso/Esci, che nell'ActionMap e' collegato direttamente a
	# self.close): la callback deve accettare zero o piu' argomenti, mai
	# esigerne esattamente uno.
	session.openWithCallback(lambda *result: _onBrowserClosed(session, result[0] if result else None), SettingsBrowser, provider)


def _onBrowserClosed(session, result):
	if result == "__switch__":
		session.openWithCallback(lambda *a: _openActiveProvider(session), HubSetup)
