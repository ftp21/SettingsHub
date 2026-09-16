# -*- coding: utf-8 -*-
"""
Fetch e parsing di http://www.manutek.it/isetting/index.php?dir= (pagina di
tipo AutoIndex con l'elenco degli zip "NemoxyzRLS_Manutek_<Tipo>_E2[_Dtt_
<Zona>] <gg> <mm> <aaaa>.zip"). Nessuna dipendenza da 'enigma'/api qui dentro
apposta: e' testabile anche fuori da Enigma2 con un python3 qualsiasi.

Le categorie qui NON sono i tipi (Mono/Dual/Trial/noSAT) ma le zone
DTT/citta': ogni zona raccoglie i pacchetti Mono/Dual/Trial/Solo-DTT
disponibili per quella zona (richiesta esplicita: "per ogni citta' ci sta
Mono, Dual, NoSat"). I pacchetti senza zona (solo satellite, nessun DTT
locale) finiscono nella categoria speciale "Nazionale (solo SAT)".

Le funzioni di rete (fetchCatalog) vanno chiamate SOLO da un thread di
background (vedi provider.py, che usa api.runInThread)."""
import html
import re
import urllib.parse
import urllib.request

BASE_URL = "http://www.manutek.it/isetting/"
LIST_URL = BASE_URL + "index.php?dir="
DOWNLOAD_URL = BASE_URL + "index.php?dir=&file={0}"
USER_AGENT = "Mozilla/5.0 (SettingsHub)"

NATIONAL_CATEGORY_ID = "__national__"
NATIONAL_CATEGORY_NAME = "Nazionale (solo SAT)"

TYPE_ORDER = ["mono", "dual", "trial", "nosat"]
TYPE_NAMES = {
	"mono": "Mono",
	"dual": "Dual",
	"trial": "Trial",
	"nosat": "Solo DTT (no SAT)",
}

_HREF_RE = re.compile(r'href="/isetting/index\.php\?dir=&amp;file=([^"]+\.zip)"')
_ENTRY_RE = re.compile(
	r"^NemoxyzRLS_Manutek_(Mono|Dual|Trial|noSAT)_E2(?:_DTT_(.+?))? (\d{2}) (\d{2}) (\d{4})\.zip$",
	re.IGNORECASE,
)


def _zoneDisplayName(zone):
	return zone.replace("_", " ")


def parseCatalog(htmlText):
	"""Pura, senza rete: separata da fetchCatalog per poterla testare con un
	html gia' salvato."""
	entries = []
	seen = set()
	for match in _HREF_RE.finditer(htmlText):
		encoded = match.group(1)
		fileName = html.unescape(urllib.parse.unquote(encoded))
		if fileName in seen:
			continue

		entryMatch = _ENTRY_RE.match(fileName)
		if not entryMatch:
			continue
		seen.add(fileName)

		typeRaw, zone, dd, mm, yyyy = entryMatch.groups()
		typeId = typeRaw.lower()

		categoryId = NATIONAL_CATEGORY_ID if not zone else zone
		# Il nome include la zona (non solo il tipo) perche' deve restare
		# univoco tra tutte le 150+ categorie/zone: sia per il confronto
		# "stesso pacchetto, stessa data" in screens/browser.py, sia per la
		# riga "Installato: ..." che non mostra la categoria.
		name = f"{TYPE_NAMES[typeId]} – {categoryDisplayName(categoryId)}"
		entries.append({
			"id": DOWNLOAD_URL.format(urllib.parse.quote(fileName)),
			"name": name,
			"type": typeId,
			"category": categoryId,
			"date": f"{yyyy}-{mm}-{dd}",
			"download_url": DOWNLOAD_URL.format(urllib.parse.quote(fileName)),
		})
	return entries


def fetchCatalog():
	req = urllib.request.Request(LIST_URL, headers={"User-Agent": USER_AGENT})
	with urllib.request.urlopen(req, timeout=20) as response:
		raw = response.read()
	return parseCatalog(raw.decode("utf-8", errors="replace"))


def categoryDisplayName(category_id):
	if category_id == NATIONAL_CATEGORY_ID:
		return NATIONAL_CATEGORY_NAME
	return _zoneDisplayName(category_id)


def categoriesPresent(entries):
	present = {e["category"] for e in entries}
	zones = sorted(z for z in present if z != NATIONAL_CATEGORY_ID)
	ordered = zones
	if NATIONAL_CATEGORY_ID in present:
		ordered = [NATIONAL_CATEGORY_ID] + ordered
	return ordered


def entriesFor(entries, category_id):
	items = [e for e in entries if e["category"] == category_id]
	items.sort(key=lambda e: TYPE_ORDER.index(e["type"]) if e["type"] in TYPE_ORDER else len(TYPE_ORDER))
	return items
