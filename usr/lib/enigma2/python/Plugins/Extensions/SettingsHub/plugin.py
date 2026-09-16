# -*- coding: utf-8 -*-
"""
SettingsHub - scheletro base modulare per "setting man" multipli.

Un settingman e' un plugin Extensions/<Nome> a se stante che, nel proprio
plugin.py, registra un provider tramite api.registerProvider(). Questo
plugin.py qui dentro carica solo:
  - i provider inclusi in providers/ (solo il demo, per ora - vedi
    providers/__init__.py:discover());
  - il servizio di autocheck configurabile (autocheck.py);
  - le voci di menu per aprire la UI (screens/main.py).
"""
from Plugins.Plugin import PluginDescriptor

from .autocheck import autoCheckService
from .language import _
from . import providers

providers.discover()

Version = "0.1"


def Main(session, **kwargs):
	from .screens.main import Main as openMain
	openMain(session)


def openFromInfoBar(infobar):
	from Screens.InfoBarGenerics import InfoBarExtensions
	infobar.addExtension(
		extension=(lambda: _("Setting Manager Hub"), lambda: Main(infobar.session), lambda: True),
		type=InfoBarExtensions.EXTENSION_SINGLE,
	)


def SessionStart(reason, **kwargs):
	if reason == 0:
		autoCheckService.gotSession(kwargs["session"])


def AutoStart(reason, **kwargs):
	if reason == 1:
		autoCheckService.timer.stop()


def Plugins(**kwargs):
	return [
		PluginDescriptor(
			name=_("Setting Manager Hub"),
			description=_("Base modulare per setting man multipli"),
			where=[PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_PLUGINMENU],
			fnc=Main,
		),
		PluginDescriptor(where=PluginDescriptor.WHERE_EXTENSIONSINGLE, fnc=openFromInfoBar),
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=SessionStart),
		PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=AutoStart),
	]
