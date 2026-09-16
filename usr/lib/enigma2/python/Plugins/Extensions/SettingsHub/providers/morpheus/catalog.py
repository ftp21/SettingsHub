# -*- coding: utf-8 -*-
"""
Fetch e parsing di http://morpheus883.altervista.org/settings/morph883.xml,
il feed XML ufficiale che elenca i pacchetti di setting disponibili (molto
piu' semplice e stabile del parsing della homepage HTML usato in precedenza).
Nessuna dipendenza da 'enigma'/api qui dentro apposta: e' testabile anche
fuori da Enigma2 con un python3 qualsiasi.

Le funzioni di rete (fetchCatalog) vanno chiamate SOLO da un thread di
background (vedi provider.py, che usa api.runInThread)."""
import re
import urllib.request
from xml.etree import ElementTree

BASE_URL = "https://morpheus883.altervista.org/"
FEED_URL = "http://morpheus883.altervista.org/settings/morph883.xml"
DOWNLOAD_BASE_URL = "http://morpheus883.altervista.org/settings/"
USER_AGENT = "Mozilla/5.0 (SettingsHub)"

_NAME_PREFIX_RE = re.compile(r"^Settings_Morph883_", re.IGNORECASE)

CATEGORY_ORDER = ["mono", "dual", "trial", "quad", "motor", "full"]
CATEGORY_NAMES = {
	"mono": "Mono",
	"dual": "Dual",
	"trial": "Trial",
	"quad": "Quad",
	"motor": "Motor",
	"full": "Full / Altro",
}


def _parseDate(raw):
	raw = (raw or "").strip()
	if len(raw) != 8 or not raw.isdigit():
		return None
	return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def _displayName(shortName):
	stripped = _NAME_PREFIX_RE.sub("", shortName)
	return stripped.replace("-", " + ")


def _categoryFor(shortName):
	stripped = _NAME_PREFIX_RE.sub("", shortName)
	if "motor" in stripped.lower():
		return "motor"
	positions = [token for token in stripped.split("-") if token]
	count = len(positions)
	if count == 1:
		return "mono"
	if count == 2:
		return "dual"
	if count == 3:
		return "trial"
	if count == 4:
		return "quad"
	return "full"


def parseCatalog(xmlText):
	"""Pura, senza rete: separata da fetchCatalog per poterla testare con un
	xml gia' salvato."""
	entries = []
	try:
		root = ElementTree.fromstring(xmlText)
	except ElementTree.ParseError:
		return entries

	for node in root.findall("package"):
		filename = node.get("filename")
		if not filename:
			continue
		shortName = (node.text or "").strip() or filename
		url = DOWNLOAD_BASE_URL + filename
		entries.append({
			"id": url,
			"name": _displayName(shortName),
			"category": _categoryFor(shortName),
			"date": _parseDate(node.get("date")),
			"download_url": url,
		})
	return entries


def fetchCatalog():
	req = urllib.request.Request(FEED_URL, headers={"User-Agent": USER_AGENT})
	with urllib.request.urlopen(req, timeout=15) as response:
		raw = response.read()
	return parseCatalog(raw.decode("utf-8", errors="replace"))


def categoriesPresent(entries):
	present = {e["category"] for e in entries}
	return [cid for cid in CATEGORY_ORDER if cid in present]


def entriesFor(entries, category_id):
	items = [e for e in entries if e["category"] == category_id]
	items.sort(key=lambda e: e["name"])
	return items
