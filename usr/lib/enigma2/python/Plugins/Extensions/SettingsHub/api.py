# -*- coding: utf-8 -*-
"""
Contratto pubblico di SettingsHub.

Un "settingman" e' un normale plugin Enigma2 (Extensions/<NomePlugin>) che,
nel proprio plugin.py, importa questo modulo e registra un'istanza di
SettingProvider:

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

Questo modulo non importa MAI screens/plugin.py dell'hub: deve restare
leggero e sicuro da importare da qualsiasi altro plugin, in qualsiasi ordine
di caricamento.
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
		"""Ritorna una lista di SettingCategory. Puo' fare rete (l'hub la
		chiama sempre dentro api.runInThread con un indicatore di
		caricamento, mai direttamente sul thread GUI - vedi screens/main.py)."""
		return []

	def listEntries(self, category_id):
		"""Ritorna una lista di SettingEntry per la categoria data. Stessa
		regola di getCategories: puo' fare rete, l'hub la chiama sempre in
		background."""
		return []

	def getInstalledInfo(self):
		"""Ritorna un dict con lo stato corrente, es.
		{'entry_id': ..., 'date': ..., 'name': ...} oppure None se nulla e'
		mai stato installato. Letto dalla config del provider (vedi config.py),
		non da file propri."""
		return None

	def checkForUpdates(self):
		"""Chiamata SOLO in un thread di background (mai sul thread GUI):
		puo' fare rete. Deve ritornare un SettingEntry se e' disponibile un
		aggiornamento rispetto a getInstalledInfo(), altrimenti None."""
		return None

	def install(self, entry, progress, done):
		"""Avvia l'installazione di 'entry'. Deve essere non bloccante per il
		thread GUI: usa runInThread() qui sotto per il lavoro pesante.
		- progress(percent, message): callback opzionale per aggiornare l'UI (0-100)
		- done(success, message): callback OBBLIGATORIA da invocare a fine lavoro,
		  chiamata gia' sul thread GUI."""
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
	sul thread GUI (via eTimer, l'unico modo sicuro di rientrare nella UI di
	Enigma2 da un thread esterno). error e' un'eccezione oppure None.

	Questo e' L'UNICO modo supportato per un provider di fare lavoro
	potenzialmente bloccante (rete, disco lento, unzip, ...): mai chiamare
	direttamente funzioni bloccanti dal thread GUI."""
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
