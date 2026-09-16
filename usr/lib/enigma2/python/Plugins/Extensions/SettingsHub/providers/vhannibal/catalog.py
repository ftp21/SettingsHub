# -*- coding: utf-8 -*-
"""
Fetch e parsing di https://www.vhannibal.net/asd.php. Nessuna dipendenza da
'enigma'/api: testabile anche fuori da Enigma2. fetchCatalog va chiamata
solo da un thread di background (vedi provider.py)."""
import html
import re
import urllib.request
from urllib.parse import urljoin

BASE_URL = "https://www.vhannibal.net/"
LIST_URL = BASE_URL + "asd.php"
USER_AGENT = "VAS14"

_ROW_RE = re.compile(r'<td><a href="(.+?)">(.+?)</a></td>\s*<td>(.+?)</td>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

CATEGORY_ORDER = ["hotbird", "dual", "trial", "quadri", "motor", "estero", "extra"]
CATEGORY_NAMES = {
	"hotbird": "Hot Bird 13°E",
	"dual": "Dual",
	"trial": "Trial",
	"quadri": "Quadri",
	"motor": "Motor",
	"estero": "Estero",
	"extra": "Altro",
}


def _cleanName(raw):
	text = _TAG_RE.sub("", raw)
	text = html.unescape(text)
	return text.replace("Vhannibal", "").strip()


def _parseDate(raw):
	raw = raw.strip()
	if len(raw) != 6 or not raw.isdigit():
		return None
	yy, mm, dd = raw[:2], raw[2:4], raw[4:6]
	return f"20{yy}-{mm}-{dd}"


def _categoryFor(name):
	n = name.lower()
	if "picon" in n:
		return "extra"
	if "deutschland" in n or "polska" in n:
		return "estero"
	if "hot bird" in n:
		return "hotbird"
	if "dual" in n:
		return "dual"
	if "trial" in n:
		return "trial"
	if "quadri" in n:
		return "quadri"
	if "motor" in n:
		return "motor"
	return "extra"


def parseCatalog(htmlText):
	"""Pura, senza rete: separata da fetchCatalog per poterla testare con un
	html gia' salvato."""
	entries = []
	for link, rawName, dateRaw in _ROW_RE.findall(htmlText):
		name = _cleanName(rawName)
		if not name:
			continue
		entries.append({
			"id": link,
			"name": name,
			"category": _categoryFor(name),
			"date": _parseDate(dateRaw),
			"download_url": urljoin(BASE_URL, link),
		})
	return entries


def fetchCatalog():
	req = urllib.request.Request(LIST_URL, headers={"User-Agent": USER_AGENT})
	with urllib.request.urlopen(req, timeout=15) as response:
		raw = response.read()
	return parseCatalog(raw.decode("iso-8859-1", errors="replace"))


def categoriesPresent(entries):
	present = {e["category"] for e in entries}
	return [cid for cid in CATEGORY_ORDER if cid in present]


def entriesFor(entries, category_id):
	items = [e for e in entries if e["category"] == category_id]
	items.sort(key=lambda e: e["date"] or "", reverse=True)
	return items
