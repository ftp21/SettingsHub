# -*- coding: utf-8 -*-
"""
Ogni sottocartella qui dentro e' un provider incluso "di serie" nell'hub
(usato per demo/collaudo). Un vero settingman esterno NON vive qui: e' un
plugin a se' stante che chiama api.registerProvider() nel proprio plugin.py.

Convenzione per ogni sottocartella providers/<nome>/:
  __init__.py  espone ID, NAME (l'"info provider"), getProvider() e
               opzionalmente ENABLED = True/False (default True se assente).
               ENABLED = False lo tiene nel codice (utile come esempio/
               riferimento, es. providers/demo/) senza farlo comparire nella
               lista che vede l'utente finale.
  provider.py  contiene l'implementazione della classe SettingProvider

discover() importa ogni sottocartella e registra il provider che restituisce,
saltando quelle con ENABLED = False.
"""
import importlib
import pkgutil

from Plugins.Extensions.SettingsHub import api


def discover():
	registered = []
	for _finder, moduleName, isPkg in pkgutil.iter_modules(__path__):
		if not isPkg:
			continue
		mod = importlib.import_module(f"{__name__}.{moduleName}")
		if not getattr(mod, "ENABLED", True):
			continue
		getProvider = getattr(mod, "getProvider", None)
		if getProvider is None:
			print(f"[SettingsHub] providers.{moduleName} non espone getProvider(), ignorato")
			continue
		provider = getProvider()
		api.registerProvider(provider)
		registered.append(provider)
	return registered
