# -*- coding: utf-8 -*-
"""
Contratto pubblico di SettingsHub: un settingman e' un plugin
Extensions/<Nome> che nel suo plugin.py registra un SettingProvider.

    from Plugins.Extensions.SettingsHub.api import SettingProvider, SettingCategory, SettingEntry, registerProvider

    class MyProvider(SettingProvider):
        id = "miosettingman"
        name = "Il Mio Setting Man"

        def getCategories(self):
            return [SettingCategory(id="hot", name="Hot Bird 13°E")]

        def listEntries(self, category_id):
            return [SettingEntry(id="2026-09-01", name="Setting completo", category_id="hot", date="2026-09-01")]

        def install(self, entry, progress, done):
            ...

    registerProvider(MyProvider())
"""
import threading

from enigma import eTimer


class SettingCategory:
	def __init__(self, id, name, description=""):
		self.id = id
		self.name = name
		self.description = description


class SettingEntry:
	"""Una singola voce installabile (es. un pacchetto di settings per una data)."""

	def __init__(self, id, name, category_id, date=None, description="", size=None):
		self.id = id
		self.name = name
		self.category_id = category_id
		self.date = date  # stringa ISO 'YYYY-MM-DD' o None
		self.description = description
		self.size = size  # bytes, opzionale


class SettingProvider:
	"""Classe base che ogni settingman deve implementare (duck-typing: non e'
	obbligatorio ereditare da questa classe, basta esporre gli stessi metodi,
	ma ereditare da' i default piu' sicuri)."""

	id = None          # stringa univoca stabile, es. 'vhannibal'. OBBLIGATORIA.
	name = None        # nome visualizzato, es. 'Vhannibal AutoSetting'. OBBLIGATORIA.
	description = ""
	icon = None         # path assoluto a un png, opzionale

	def getCategories(self):
		"""Puo' fare rete: chiamata sempre dentro api.runInThread, mai sul thread GUI."""
		return []

	def listEntries(self, category_id):
		"""SettingEntry della categoria data. Stessa regola di getCategories."""
		return []

	def getInstalledInfo(self):
		"""{'entry_id', 'date', 'name'} oppure None se non installato."""
		return None

	def checkForUpdates(self):
		"""Solo in background. SettingEntry se c'e' un aggiornamento, altrimenti None."""
		return None

	def install(self, entry, progress, done):
		"""Non bloccante: usa runInThread() per il lavoro pesante.
		progress(percent, message) e' opzionale, done(success, message) e' obbligatoria."""
		raise NotImplementedError


_providers = {}


def registerProvider(provider):
	if not provider.id or not provider.name:
		raise ValueError("SettingProvider.id e .name sono obbligatori")
	_providers[provider.id] = provider


def unregisterProvider(provider_id):
	_providers.pop(provider_id, None)


def getProviders():
	return list(_providers.values())


def getProvider(provider_id):
	return _providers.get(provider_id)


_activeTimers = set()


def runInThread(work, callback):
	"""Esegue work() in un thread separato e richiama callback(result, error)
	sul thread GUI (via eTimer: l'unico modo sicuro di rientrare nella UI
	da un thread esterno)."""
	result_box = {}

	def target():
		try:
			result_box["result"] = work()
		except Exception as e:
			result_box["error"] = e

	t = threading.Thread(target=target, daemon=True)

	timer = eTimer()
	_activeTimers.add(timer)  # tieni viva una reference finche' il poll non finisce

	def poll():
		if t.is_alive():
			timer.start(150, True)
			return
		_activeTimers.discard(timer)
		callback(result_box.get("result"), result_box.get("error"))

	timer.callback.append(poll)
	t.start()
	timer.start(150, True)
	return t
