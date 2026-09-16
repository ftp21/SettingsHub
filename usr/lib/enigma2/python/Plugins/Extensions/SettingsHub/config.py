# -*- coding: utf-8 -*-
"""
Tutta la config di SettingsHub vive SOLO dentro config.plugins.settingshub,
quindi in /etc/enigma2/settings come ogni altra config di sistema. Nessun
file proprio sparso nella cartella del plugin (a differenza del vecchio
NGsetting, che scriveva un suo 'Date' fatto a mano).
"""
import json
import time

from Components.config import config, configfile, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigClock, ConfigText

from Plugins.Extensions.SettingsHub.language import _

# ConfigClock vuole un timestamp epoch (ne legge solo ora/minuto in ora
# locale), non una tupla (ora, minuti): costruiamo un epoch qualsiasi che
# corrisponda alle 06:00 locali, indipendentemente dal fuso del sistema.
_DEFAULT_AUTOCHECK_TIME = time.mktime((2024, 1, 1, 6, 0, 0, 0, 0, -1))

AUTOCHECK_INTERVALS = [
	("off", _("Mai")),
	("6h", _("Ogni 6 ore")),
	("12h", _("Ogni 12 ore")),
	("daily", _("Una volta al giorno")),
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
config.plugins.settingshub.autocheck_notify_only = ConfigYesNo(default=True)  # solo notifica, non installa da solo
config.plugins.settingshub.last_check = ConfigText(default="")  # ISO datetime dell'ultimo check, sola lettura
config.plugins.settingshub.favorites_snapshot = ConfigText(default="")  # JSON, gestito da favorites.py
# Quali bouquet preservare (vedi screens/choose_favorites.py): di default
# NESSUNO - l'utente deve scegliere esplicitamente quali vuole, altrimenti
# preservare "tutto" di default e' sia sorprendente sia pesante.
config.plugins.settingshub.favorites_selection = ConfigText(default="")  # JSON: lista di nomi file bouquet

# Stato "installato" UNICO per tutto l'hub, non uno per provider: sul
# decoder esiste un solo lamedb/bouquets alla volta, quindi non ha senso
# ricordare per sempre cosa era installato per un provider usato una volta
# mesi fa (e poi mai piu' selezionato) - risultato che si otterrebbe con una
# ConfigSubsection per ogni provider mai scelto, che Enigma2 oltretutto non
# butta mai via da /etc/enigma2/settings anche quando smette di essere
# referenziata in codice. installed_provider_id dice A CHI appartiene questo
# stato: se non corrisponde al provider attivo, per quel provider non e'
# installato nulla (vedi getInstalledInfo).
config.plugins.settingshub.installed_provider_id = ConfigText(default="")
config.plugins.settingshub.installed_entry_id = ConfigText(default="")
config.plugins.settingshub.installed_date = ConfigText(default="")
config.plugins.settingshub.installed_name = ConfigText(default="")


def _purgeLegacyConfig():
	"""Enigma2 non elimina mai da /etc/enigma2/settings una chiave che smette
	di essere referenziata in codice (la tiene per non perdere impostazioni
	di plugin temporaneamente disinstallati) - quindi ogni volta che questo
	plugin ha smesso di usare un ramo di config, quel ramo resta orfano per
	sempre a meno di ripulirlo esplicitamente. Rami noti diventati orfani in
	versioni precedenti:
	  - 'providers.<id>.installed_*': una ConfigSubsection per OGNI provider
	    mai scelto (anche una volta soltanto, mesi fa), sostituita da un
	    unico stato 'installato' globale (vedi sopra).
	  - 'favorites_selection_set': flag on/off eliminato quando la selezione
	    bouquet e' diventata 'vuoto = nessuno' invece di richiedere un
	    interruttore separato.
	Va chiamata una volta al modulo import; e' un no-op silenzioso se non
	c'e' nulla da ripulire."""
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
