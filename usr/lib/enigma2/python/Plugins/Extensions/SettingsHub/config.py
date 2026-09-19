# -*- coding: utf-8 -*-
"""Tutta la config vive dentro config.plugins.settingshub, in
/etc/enigma2/settings come ogni altra config di sistema."""
import json
import time

from Components.config import config, configfile, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigClock, ConfigText

from Plugins.Extensions.SettingsHub.language import _

# ConfigClock vuole un timestamp epoch (ne legge solo ora/minuto in ora
# locale), non una tupla (ora, minuti): costruiamo un epoch qualsiasi che
# corrisponda alle 06:00 locali, indipendentemente dal fuso del sistema.
_DEFAULT_AUTOCHECK_TIME = time.mktime((2024, 1, 1, 6, 0, 0, 0, 0, -1))

AUTOCHECK_INTERVALS = [
	("off", _("Never")),
	("6h", _("Every 6 hours")),
	("12h", _("Every 12 hours")),
	("daily", _("Once a day")),
]

AUTOCHECK_INTERVAL_SECONDS = {
	"6h": 6 * 3600,
	"12h": 12 * 3600,
	"daily": 24 * 3600,
}

config.plugins.settingshub = ConfigSubsection()
# Diventa True la prima volta che l'utente salva le impostazioni base (vedi
# screens/setup.py): finche' resta False, aprire il plugin mostra prima la
# configurazione guidata invece della schermata dei setting (come EPGImport).
config.plugins.settingshub.configured = ConfigYesNo(default=False)
config.plugins.settingshub.active_provider_id = ConfigText(default="")  # un solo setting man alla volta
config.plugins.settingshub.autocheck_interval = ConfigSelection(default="daily", choices=AUTOCHECK_INTERVALS)
config.plugins.settingshub.autocheck_time = ConfigClock(default=_DEFAULT_AUTOCHECK_TIME)
config.plugins.settingshub.autocheck_notify_only = ConfigYesNo(default=False)  # solo notifica, non installa da solo
# Mostrato solo se Plugins.SystemPlugins.LCNScanner e' installato (vedi
# screens/setup.py): se Si' (default), un'installazione settings che trova un
# bouquet gestito da LCNScanner rifa' da sola lo scan DVB-T e ricostruisce il
# bouquet (vedi lcn_integration.py). Se No, l'update dei settings lascia stare
# quel bouquet - resta comunque disponibile l'azione manuale "Recreate LCN
# bouquet" per farlo a comando in qualsiasi momento.
config.plugins.settingshub.recreate_lcn_after_update = ConfigYesNo(default=True)
# Come ricostruire il bouquet quando recreate_lcn_after_update e' Si' (vedi
# lcn_integration.py): "scan" rifa' una vera scansione DVB-T dopo l'update
# (accurato, verifica il segnale, ma richiede qualche minuto e passa dal
# tuner); "preserve" non tocca il tuner - reinserisce nel lamedb nuovo le
# stesse voci DVB-T che c'erano in quello vecchio (istantaneo, ma non
# verifica che quei canali siano ancora ricevibili cosi' come sono).
config.plugins.settingshub.lcn_rebuild_method = ConfigSelection(default="scan", choices=[
	("scan", _("Rescan DVB-T (slower, verifies the signal)")),
	("preserve", _("Reuse existing lamedb (instant, no rescan)")),
])
config.plugins.settingshub.last_check = ConfigText(default="")  # ISO datetime dell'ultimo check, sola lettura
config.plugins.settingshub.favorites_snapshot = ConfigText(default="")  # JSON, gestito da favorites.py
# Quali bouquet preservare (vedi screens/choose_favorites.py): di default
# NESSUNO - l'utente deve scegliere esplicitamente quali vuole, altrimenti
# preservare "tutto" di default e' sia sorprendente sia pesante.
config.plugins.settingshub.favorites_selection = ConfigText(default="")  # JSON: lista di nomi file bouquet

# Stato "installato" UNICO per tutto l'hub, non uno per provider: sul
# decoder esiste un solo lamedb/bouquets alla volta. installed_provider_id
# dice a chi appartiene questo stato (vedi getInstalledInfo).
config.plugins.settingshub.installed_provider_id = ConfigText(default="")
config.plugins.settingshub.installed_entry_id = ConfigText(default="")
config.plugins.settingshub.installed_date = ConfigText(default="")
config.plugins.settingshub.installed_name = ConfigText(default="")


def _purgeLegacyConfig():
	"""Enigma2 non butta mai via una chiave orfana da /etc/enigma2/settings:
	ripulisce i rami di config abbandonati da versioni precedenti (il vecchio
	'providers.<id>.installed_*' per provider e 'favorites_selection_set')."""
	stored = config.plugins.settingshub.content.stored_values
	changed = False
	for legacyKey in ("providers", "favorites_selection_set"):
		if legacyKey in stored:
			del stored[legacyKey]
			changed = True
	if changed:
		persist()


def getFavoritesSelection():
	"""Il set dei nomi file bouquet scelti dall'utente (vedi
	screens/choose_favorites.py). Vuoto finche' non ha mai scelto nulla:
	nessun bouquet viene preservato finche' non e' l'utente stesso a dirlo."""
	raw = config.plugins.settingshub.favorites_selection.value
	if not raw:
		return set()
	try:
		return set(json.loads(raw))
	except ValueError:
		return set()


def getActiveProvider():
	"""Il setting man attualmente scelto (uno solo alla volta), o None se
	nessuno e' ancora stato scelto/registrato."""
	from Plugins.Extensions.SettingsHub import api
	pid = config.plugins.settingshub.active_provider_id.value
	if pid:
		provider = api.getProvider(pid)
		if provider:
			return provider
	providers = api.getProviders()
	return providers[0] if providers else None


def setActiveProvider(provider_id):
	config.plugins.settingshub.active_provider_id.value = provider_id
	config.plugins.settingshub.active_provider_id.save()
	persist()


def getInstalledInfo(provider_id):
	"""None se il provider passato non e' quello che ha scritto l'ultimo
	lamedb/bouquets (vedi il commento su installed_provider_id sopra): non
	c'e' uno storico per provider, solo lo stato attuale reale del decoder."""
	if config.plugins.settingshub.installed_provider_id.value != provider_id:
		return None
	if not config.plugins.settingshub.installed_entry_id.value:
		return None
	return {
		"entry_id": config.plugins.settingshub.installed_entry_id.value,
		"date": config.plugins.settingshub.installed_date.value,
		"name": config.plugins.settingshub.installed_name.value,
	}


def persist():
	"""ConfigElement.save() aggiorna solo il valore in memoria: la scrittura
	vera su /etc/enigma2/settings avviene solo qui. Va chiamata esplicitamente
	dopo ogni modifica fatta FUORI da una ConfigListScreen (che lo fa gia' da
	sola in saveAll())."""
	configfile.save()


def setInstalledInfo(provider_id, entry):
	config.plugins.settingshub.installed_provider_id.value = provider_id
	config.plugins.settingshub.installed_entry_id.value = entry.id
	config.plugins.settingshub.installed_date.value = entry.date or ""
	config.plugins.settingshub.installed_name.value = entry.name
	config.plugins.settingshub.installed_provider_id.save()
	config.plugins.settingshub.installed_entry_id.save()
	config.plugins.settingshub.installed_date.save()
	config.plugins.settingshub.installed_name.save()
	persist()


def resetInstalledInfo():
	"""Dimentica lo stato 'installato' corrente (usata da reset.py quando
	l'utente azzera i setting): il prossimo controllo/installazione non lo
	trattera' piu' come 'gia' aggiornato'."""
	config.plugins.settingshub.installed_provider_id.value = ""
	config.plugins.settingshub.installed_entry_id.value = ""
	config.plugins.settingshub.installed_date.value = ""
	config.plugins.settingshub.installed_name.value = ""
	config.plugins.settingshub.installed_provider_id.save()
	config.plugins.settingshub.installed_entry_id.save()
	config.plugins.settingshub.installed_date.save()
	config.plugins.settingshub.installed_name.save()
	persist()


_purgeLegacyConfig()
