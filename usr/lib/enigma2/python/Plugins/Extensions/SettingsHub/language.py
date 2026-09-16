# -*- coding: utf-8 -*-
import gettext
import os

from Components.Language import language
from Tools.Directories import SCOPE_LANGUAGE, SCOPE_PLUGINS, resolveFilename

PluginLanguageDomain = "SettingsHub"
PluginLanguagePath = resolveFilename(SCOPE_PLUGINS, "Extensions/SettingsHub/po")


def localeInit():
	lang = language.getLanguage()[:2]
	os.environ["LANGUAGE"] = lang
	gettext.bindtextdomain(PluginLanguageDomain, PluginLanguagePath)
	gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE, ""))


def _(txt):
	t = gettext.dgettext(PluginLanguageDomain, txt)
	if t == txt:
		t = gettext.dgettext("enigma2", txt)
	return t


localeInit()
language.addCallback(localeInit)
