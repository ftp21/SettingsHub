# -*- coding: utf-8 -*-
"""
Ogni sottocartella qui e' un provider incluso "di serie" nell'hub: espone
ID/NAME/getProvider() in __init__.py, opzionalmente ENABLED = False per
tenerlo nel codice senza mostrarlo all'utente (es. providers/demo/).
discover() importa ogni sottocartella e registra il provider restituito."""
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
