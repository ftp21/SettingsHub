# -*- coding: utf-8 -*-
"""
Fetch e parsing del repo GitHub
https://github.com/Andreadel1984/Liste-Canali-Enigma2-Italia via GitHub
Contents API (niente scraping HTML). Nessuna dipendenza da 'enigma'/api:
testabile anche fuori da Enigma2. fetchCatalog va chiamata solo da un
thread di background (vedi provider.py)."""
import json
import re
import urllib.request

REPO = "Andreadel1984/Liste-Canali-Enigma2-Italia"
BRANCH = "main"
CONTENTS_URL = f"https://api.github.com/repos/{REPO}/contents/?ref={BRANCH}"
USER_AGENT = "SettingsHub"

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\.zip$", re.IGNORECASE)

CATEGORY_ORDER = ["mono", "dual", "tivusat"]
CATEGORY_NAMES = {
	"mono": "Mono Hotbird 13°E",
	"dual": "Dual Hotbird 13°E + Astra 19.2°E",
	"tivusat": "Solo Tivusat",
}


def _parseDate(name):
	match = _DATE_RE.search(name)
	if not match:
		return None
	dd, mm, yyyy = match.groups()
	return f"{yyyy}-{mm}-{dd}"


def _categoryFor(name):
	n = name.lower()
	if "tivusat" in n:
		return "tivusat"
	if "astra" in n:
		return "dual"
	return "mono"


def _displayName(name):
	base = re.sub(r"\.zip$", "", name, flags=re.IGNORECASE)
	base = _DATE_RE.sub("", name)
	base = re.sub(r"\.zip$", "", base, flags=re.IGNORECASE).strip(" -")
	return base or name


def parseCatalog(jsonText):
	"""Pura, senza rete: separata da fetchCatalog per poterla testare con un
	json gia' salvato (risposta della GitHub Contents API)."""
	try:
		items = json.loads(jsonText)
	except ValueError:
		return []

	entries = []
	for item in items:
		name = item.get("name", "")
		if item.get("type") != "file" or not name.lower().endswith(".zip"):
			continue
		downloadUrl = item.get("download_url")
		if not downloadUrl:
			continue
		entries.append({
			"id": downloadUrl,
			"name": _displayName(name),
			"category": _categoryFor(name),
			"date": _parseDate(name),
			"download_url": downloadUrl,
		})
	return entries


def fetchCatalog():
	req = urllib.request.Request(CONTENTS_URL, headers={
		"User-Agent": USER_AGENT,
		"Accept": "application/vnd.github+json",
	})
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
