# -*- coding: utf-8 -*-
"""Wrapper sottile su archive_installer (logica di download/estrazione/merge
condivisa tra provider): qui solo i dettagli specifici di Andrea del 1984."""
from Plugins.Extensions.SettingsHub.archive_installer import installArchivePackage

from . import catalog


def installEntry(entry_id):
	"""Scarica, estrae ed applica il pacchetto identificato da entry_id (l'URL
	raw.githubusercontent.com diretto dello zip). Va chiamata SOLO dentro
	api.runInThread."""
	return installArchivePackage(entry_id, catalog.USER_AGENT, temp_prefix="settingshub_andreadel_")
