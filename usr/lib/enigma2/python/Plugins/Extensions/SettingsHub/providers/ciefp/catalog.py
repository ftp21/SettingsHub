# -*- coding: utf-8 -*-
"""
Fetch e parsing del repo GitHub
https://github.com/ciefp/ciefpsettings-enigma2-zipped via GitHub Contents
API. Pacchetti tipo "ciefp-E2-<Nsat>sat<posizioni>-<gg>.<mm>.<aaaa>.zip";
categorie per numero di posizioni satellitari (Mono/Dual/Trial/Quad/Multi),
stesso schema di Vhannibal/Morpheus883. fetchCatalog va chiamata solo da un
thread di background (vedi provider.py)."""
import json
import re
import urllib.request

REPO = "ciefp/ciefpsettings-enigma2-zipped"
BRANCH = "master"
CONTENTS_URL = f"https://api.github.com/repos/{REPO}/contents/?ref={BRANCH}"
USER_AGENT = "SettingsHub"

_PREFIX_RE = re.compile(r"^ciefp-E2-", re.IGNORECASE)
_DATE_SUFFIX_RE = re.compile(r"-(\d{2})\.(\d{2})\.(\d{4})\.zip$", re.IGNORECASE)
_SAT_COUNT_RE = re.compile(r"^(\d+)sat[A-Za-z]?-", re.IGNORECASE)
_POSITION_RE = re.compile(r"\d+(?:\.\d+)?[EW]", re.IGNORECASE)

CATEGORY_ORDER = ["mono", "dual", "trial", "quad", "multi"]
CATEGORY_NAMES = {
	"mono": "Mono",
	"dual": "Dual",
	"trial": "Trial",
	"quad": "Quad",
	"multi": "Multi (5+ satelliti)",
}


def _parseDate(name):
	match = _DATE_SUFFIX_RE.search(name)
	if not match:
		return None
	dd, mm, yyyy = match.groups()
	return f"{yyyy}-{mm}-{dd}"


def _shortName(name):
	stripped = _PREFIX_RE.sub("", name)
	stripped = _DATE_SUFFIX_RE.sub("", stripped)
	return stripped


def _satCount(shortName):
	match = _SAT_COUNT_RE.match(shortName)
	if match:
		return int(match.group(1))
	return len(_POSITION_RE.findall(shortName))


def _categoryFor(count):
	if count <= 1:
		return "mono"
	if count == 2:
		return "dual"
	if count == 3:
		return "trial"
	if count == 4:
		return "quad"
	return "multi"


def _displayName(shortName):
	positions = _SAT_COUNT_RE.sub("", shortName)
	positions = positions.replace("-", " + ").strip(" +")
	return positions or shortName


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
		shortName = _shortName(name)
		count = _satCount(shortName)
		entries.append({
			"id": downloadUrl,
			"name": _displayName(shortName),
			"category": _categoryFor(count),
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
