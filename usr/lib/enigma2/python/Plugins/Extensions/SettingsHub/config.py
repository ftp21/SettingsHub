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

# Config per-provider create la prima volta che servono. Non note in anticipo
# (i provider si registrano a runtime), quindi niente ConfigSubsection statica:
# usiamo un dict Python che fa da cache dei sotto-nodi gia' creati.
_providerConfigs = {}


def getProviderConfig(provider_id):
	"""Ritorna (creandola se serve) la ConfigSubsection per un provider:
	  .installed_entry_id ConfigText, id dell'ultima entry installata
	  .installed_date     ConfigText
	  .installed_name     ConfigText
	Persistita comunque dentro config.plugins.settingshub.providers.<id>.
	"""
	if provider_id in _providerConfigs:
		return _providerConfigs[provider_id]

	if not hasattr(config.plugins.settingshub, "providers"):
		config.plugins.settingshub.providers = ConfigSubsection()
	providersRoot = config.plugins.settingshub.providers

	# ConfigSubsection non accetta id provider arbitrari come attributo se
	# contengono caratteri non validi in python: normalizziamo la chiave.
	safe_id = "".join(c if c.isalnum() else "_" for c in provider_id)
	if not hasattr(providersRoot, safe_id):
		sub = ConfigSubsection()
		sub.installed_entry_id = ConfigText(default="")
		sub.installed_date = ConfigText(default="")
		sub.installed_name = ConfigText(default="")
		setattr(providersRoot, safe_id, sub)

	sub = getattr(providersRoot, safe_id)
	_providerConfigs[provider_id] = sub
	return sub


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
	cfg = getProviderConfig(provider_id)
	if not cfg.installed_entry_id.value:
		return None
	return {
		"entry_id": cfg.installed_entry_id.value,
		"date": cfg.installed_date.value,
		"name": cfg.installed_name.value,
	}


def persist():
	"""ConfigElement.save() aggiorna solo il valore in memoria: la scrittura
	vera su /etc/enigma2/settings avviene solo qui. Va chiamata esplicitamente
	dopo ogni modifica fatta FUORI da una ConfigListScreen (che lo fa gia' da
	sola in saveAll())."""
	configfile.save()


def setInstalledInfo(provider_id, entry):
	cfg = getProviderConfig(provider_id)
	cfg.installed_entry_id.value = entry.id
	cfg.installed_date.value = entry.date or ""
	cfg.installed_name.value = entry.name
	cfg.installed_entry_id.save()
	cfg.installed_date.save()
	cfg.installed_name.save()
	persist()
