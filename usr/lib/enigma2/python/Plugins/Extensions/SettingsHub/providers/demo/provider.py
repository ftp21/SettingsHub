# -*- coding: utf-8 -*-
"""Implementazione del provider demo. I metadati (ID/NAME/DESCRIPTION)
vivono in __init__.py: qui li importiamo per non ripeterli due volte."""
import time

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub.config import getInstalledInfo

from . import ID, NAME, DESCRIPTION


class DemoProvider(api.SettingProvider):
	id = ID
	name = NAME
	description = DESCRIPTION

	_catalog = {
		"hotbird": [
			api.SettingEntry(id="hotbird-2026-09-01", name="Hot Bird completo", category_id="hotbird", date="2026-09-01", description="Pacchetto di esempio, nessun download reale."),
			api.SettingEntry(id="hotbird-2026-08-01", name="Hot Bird completo", category_id="hotbird", date="2026-08-01", description="Versione precedente di esempio."),
		],
		"astra": [
			api.SettingEntry(id="astra-2026-09-05", name="Astra 19.2E completo", category_id="astra", date="2026-09-05", description="Pacchetto di esempio, nessun download reale."),
		],
	}

	def getCategories(self):
		return [
			api.SettingCategory(id="hotbird", name="Hot Bird 13°E"),
			api.SettingCategory(id="astra", name="Astra 19.2°E"),
		]

	def listEntries(self, category_id):
		return self._catalog.get(category_id, [])

	def getInstalledInfo(self):
		return getInstalledInfo(self.id)

	def checkForUpdates(self):
		# Simula una chiamata di rete lenta: questo gira SOLO in un thread di
		# background (vedi autocheck.py), mai sul thread GUI.
		time.sleep(1)
		installed = self.getInstalledInfo()
		latest = self._catalog["hotbird"][0]
		if not installed or installed.get("entry_id") != latest.id:
			return latest
		return None

	def install(self, entry, progress, done):
		def work():
			for pct in (25, 50, 75, 100):
				time.sleep(0.3)
			return True

		def onDone(result, error):
			if error:
				done(False, str(error))
			else:
				done(True, f"'{entry.name}' installato (simulato).")

		api.runInThread(work, onDone)
