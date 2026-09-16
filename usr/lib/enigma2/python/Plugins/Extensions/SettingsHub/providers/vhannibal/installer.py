# -*- coding: utf-8 -*-
"""Wrapper sottile su archive_installer (logica di download/estrazione/merge
condivisa tra provider): qui solo i dettagli specifici di Vhannibal."""
from Plugins.Extensions.SettingsHub.archive_installer import installArchivePackage

from . import catalog


def installEntry(entry_id):
	"""Scarica, estrae ed applica il pacchetto identificato da entry_id (il
	link relativo di download.php). Va chiamata SOLO dentro api.runInThread."""
	url = entry_id if entry_id.startswith("http") else catalog.BASE_URL + entry_id
	return installArchivePackage(url, catalog.USER_AGENT, temp_prefix="settingshub_vhannibal_")
