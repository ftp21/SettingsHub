# -*- coding: utf-8 -*-
import time

from Plugins.Extensions.SettingsHub import api
from Plugins.Extensions.SettingsHub.config import getInstalledInfo

from . import ID, NAME, DESCRIPTION
from . import catalog
from . import installer


class VhannibalProvider(api.SettingProvider):
	id = ID
	name = NAME
	description = DESCRIPTION

	CATALOG_MAX_AGE = 300  # secondi: evita di ri-scaricare asd.php ad ogni click

	def __init__(self):
		self._catalog = None
		self._catalogTime = 0

	def _ensureCatalog(self, maxAge=None):
		age = self.CATALOG_MAX_AGE if maxAge is None else maxAge
		if self._catalog is not None and (time.time() - self._catalogTime) < age:
			return self._catalog
		self._catalog = catalog.fetchCatalog()
		self._catalogTime = time.time()
		return self._catalog

	# --- Le due funzioni sotto fanno rete vera (fetch di asd.php): la UI
	# dell'hub le chiama sempre dentro api.runInThread, mai direttamente sul
	# thread GUI (vedi screens/main.py).
	def getCategories(self):
		entries = self._ensureCatalog()
		return [
			api.SettingCategory(id=cid, name=catalog.CATEGORY_NAMES[cid])
			for cid in catalog.categoriesPresent(entries)
		]

	def listEntries(self, category_id):
		entries = catalog.entriesFor(self._ensureCatalog(), category_id)
		return [
			api.SettingEntry(id=e["id"], name=e["name"], category_id=category_id, date=e["date"])
			for e in entries
		]

	def getInstalledInfo(self):
		return getInstalledInfo(self.id)

	def checkForUpdates(self):
		installed = self.getInstalledInfo()
		if not installed or not installed.get("name"):
			return None
		entries = self._ensureCatalog(maxAge=0)
		candidates = [e for e in entries if e["name"] == installed["name"]]
		if not candidates:
			return None
		candidates.sort(key=lambda e: e["date"] or "", reverse=True)
		latest = candidates[0]
		if (latest["date"] or "") > (installed.get("date") or ""):
			return api.SettingEntry(id=latest["id"], name=latest["name"], category_id=latest["category"], date=latest["date"])
		return None

	def install(self, entry, progress, done):
		def work():
			return installer.installEntry(entry.id)

		def onDone(result, error):
			if error:
				done(False, str(error))
				return
			success, message = result
			if success:
				from enigma import eDVBDB
				eDVBDB.getInstance().reloadServicelist()
				eDVBDB.getInstance().reloadBouquets()
			done(success, message)

		api.runInThread(work, onDone)
