# -*- coding: utf-8 -*-
"""
Preserva i bouquet personali dell'utente (TV o radio, qualsiasi tipo:
digitale terrestre, satellite, misto...) attraverso l'installazione di un
nuovo pacchetto di setting (qualunque provider). Approccio scelto
deliberatamente semplice: non ricalcola l'LCN da zero con tabelle regionali
(come faceva il vecchio NGsetting con rules.xml) - salva selezione, ordine
interno E POSIZIONE ASSOLUTA (l'indice in bouquets.tv/bouquets.radio) dei
bouquet correnti, che per l'utente e' gia' quella giusta, e ritrova ogni
canale nel nuovo lamedb cercando lo stesso servizio per identita'
(onid, tsid, sid), non per posizione nel file. Un canale non piu' presente
nel nuovo setting viene semplicemente saltato; un bouquet torna ad
ESATTAMENTE la sua posizione originale (es. terzo in lista prima -> terzo in
lista dopo), e viene riscritto come 'userbouquet.<nome-sanificato>.tv/radio'.

Salvato come JSON dentro un ConfigText (config.plugins.settingshub.*): resta
config nativa Enigma2, solo con un valore strutturato invece di uno scalare.
"""
import json
import os
import re
import unicodedata

ENIGMA2_DIR = "/etc/enigma2"

# type nel riferimento '#SERVICE 1:7:<type>:...FROM BOUQUET' e estensione file,
# per distinguere un bouquet TV da uno radio.
BOUQUET_KINDS = {
	"tv": {"list": "bouquets.tv", "ext": ".tv", "ref_type": 1},
	"radio": {"list": "bouquets.radio", "ext": ".radio", "ref_type": 2},
}


_GENERIC_FILENAME_RE = re.compile(r"^userbouquet\.\d+\.(tv|radio)$")


def _isGenericFileName(fileName):
	"""Vero solo per nomi generati automaticamente tipo
	'userbouquet.12345.tv' (puramente numerici): SOLO in quel caso vale la
	pena rinominare al momento del ripristino. Un bouquet che si chiamava
	gia' 'userbouquet.miopreferito.tv' mantiene il suo nome."""
	return bool(_GENERIC_FILENAME_RE.match(fileName))


def _sanitizeName(title):
	"""'Città del Capo' -> 'citta_del_capo': le accentate diventano la
	lettera senza accento invece di sparire, il resto (emoji, simboli...)
	viene scartato."""
	ascii_text = unicodedata.normalize("NFKD", (title or "")).encode("ascii", "ignore").decode("ascii")
	slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.strip().lower()).strip("_")
	return slug or "preferiti"


def _bouquetEntriesFor(kind):
	"""Tutti i bouquet utente correnti di tipo 'kind' ('tv' o 'radio'), come
	[(position, path), ...] dove position e' l'indice (0-based) della riga
	'FROM BOUQUET' nella lista corrispondente - la posizione che l'utente
	vede nell'elenco dei bouquet."""
	info = BOUQUET_KINDS[kind]
	if not os.path.isdir(ENIGMA2_DIR):
		return []
	result = []
	seen = set()
	position = 0
	listPath = os.path.join(ENIGMA2_DIR, info["list"])
	try:
		with open(listPath, "r", encoding="utf-8", errors="ignore") as f:
			for line in f:
				if 'FROM BOUQUET "' not in line:
					continue
				name = line.split('FROM BOUQUET "', 1)[1].split('"', 1)[0]
				if name.startswith("userbouquet.") and name.endswith(info["ext"]):
					path = os.path.join(ENIGMA2_DIR, name)
					if os.path.exists(path) and name not in seen:
						result.append((position, path))
						seen.add(name)
				position += 1
	except OSError:
		pass
	# eventuali userbouquet non elencati nella lista (raro, ma non li perdiamo)
	for name in sorted(os.listdir(ENIGMA2_DIR)):
		if name.startswith("userbouquet.") and name.endswith(info["ext"]) and name not in seen:
			result.append((position, os.path.join(ENIGMA2_DIR, name)))
			seen.add(name)
			position += 1
	return result


def _parseServiceKey(line):
	"""Da '#SERVICE 1:0:1:SID:TSID:ONID:NAMESPACE:...' estrae
	(onid, tsid, sid) come interi, o None se la riga non e' un servizio
	valido (o e' un marker/sotto-bouquet)."""
	line = line.strip()
	if not line.startswith("#SERVICE"):
		return None
	parts = line[8:].strip().split(":")
	if len(parts) < 7:
		return None
	try:
		serviceType = int(parts[1])
		sid = int(parts[3], 16)
		tsid = int(parts[4], 16)
		onid = int(parts[5], 16)
	except ValueError:
		return None
	if serviceType in (7, 64):  # 7=sotto-bouquet, 64=marker: non sono canali
		return None
	return (onid, tsid, sid)


def snapshot(selection=None):
	"""Legge tutti i bouquet utente correnti (TV e radio) e ritorna una lista
	di {fileName, title, kind, position, entries: [{name, key}]}. 'position'
	e' l'indice originale nella lista di appartenenza, riapplicato alla
	lettera in restore(). Se 'selection' non e' None, include solo i bouquet
	il cui nome file e' in quel set (vedi screens/choose_favorites.py e
	config.getFavoritesSelection)."""
	result = []
	for kind in BOUQUET_KINDS:
		for position, path in _bouquetEntriesFor(kind):
			fileName = os.path.basename(path)
			if selection is not None and fileName not in selection:
				continue
			try:
				with open(path, "r", encoding="utf-8", errors="ignore") as f:
					lines = f.readlines()
			except OSError:
				continue
			title = fileName
			bouquetEntries = []
			pendingName = None
			for line in lines:
				line = line.strip()
				if line.lower().startswith("#name"):
					title = line[5:].strip() or title
					continue
				if line.startswith("#DESCRIPTION"):
					pendingName = line[len("#DESCRIPTION"):].strip()
					continue
				key = _parseServiceKey(line)
				if key:
					bouquetEntries.append({"name": pendingName or "", "key": list(key)})
					pendingName = None
			if bouquetEntries:
				result.append({"fileName": fileName, "title": title, "kind": kind, "position": position, "entries": bouquetEntries})
	return result


def listUserBouquets():
	"""Versione leggera di snapshot(), solo per farli scegliere all'utente:
	ritorna [(fileName, title), ...] (TV e radio insieme) senza leggere i
	canali di ognuno."""
	result = []
	for kind in BOUQUET_KINDS:
		for _position, path in _bouquetEntriesFor(kind):
			fileName = os.path.basename(path)
			title = fileName
			try:
				with open(path, "r", encoding="utf-8", errors="ignore") as f:
					for line in f:
						if line.lower().startswith("#name"):
							title = line[5:].strip() or title
							break
			except OSError:
				pass
			result.append((fileName, title))
	return result


def save(configField, selection=None):
	"""Salva lo snapshot corrente (filtrato secondo 'selection', vedi
	snapshot()) in configField (un ConfigText). Ritorna quanti bouquet sono
	stati salvati."""
	data = snapshot(selection)
	configField.value = json.dumps(data)
	configField.save()
	return len(data)


def restore(configField):
	"""Ricostruisce i bouquet salvati in configField cercando ogni canale nel
	lamedb ATTUALE (quello appena installato) per identita', li scrive come
	'userbouquet.<nome-sanificato>.tv/radio' e li reinserisce nella lista
	giusta (bouquets.tv o bouquets.radio) alla loro POSIZIONE ORIGINALE (non
	in coda, non in testa). Ritorna quanti bouquet sono stati ricostruiti."""
	if not configField.value:
		return 0
	try:
		savedBouquets = json.loads(configField.value)
	except ValueError:
		return 0
	if not savedBouquets:
		return 0

	byKey = _currentServicesByKey()
	if not byKey:
		return 0

	restoredByKind = {kind: [] for kind in BOUQUET_KINDS}  # kind -> [(position, fileName), ...]
	usedNames = set()
	restoredCount = 0
	for bouquet in savedBouquets:
		kind = bouquet.get("kind", "tv")
		info = BOUQUET_KINDS.get(kind, BOUQUET_KINDS["tv"])
		matched = []
		for item in bouquet.get("entries", []):
			tref = byKey.get(tuple(item["key"]))
			if tref:
				matched.append((tref, item.get("name") or ""))
		if not matched:
			continue

		originalFileName = bouquet.get("fileName") or ""
		if originalFileName and not _isGenericFileName(originalFileName):
			# il bouquet aveva gia' un nome sensato (non generato
			# automaticamente tipo 'userbouquet.12345.tv'): lo ripristiniamo
			# com'era, senza rinominarlo - rinominare sempre sarebbe pesante
			# e inutile per bouquet che un nome chiaro ce l'avevano gia'.
			baseName = os.path.splitext(originalFileName)[0][len("userbouquet."):]
		else:
			baseName = _sanitizeName(bouquet.get("title"))
		fileName = "userbouquet.%s%s" % (baseName, info["ext"])
		# Il nome originale (se non generico) puo' scontrarsi con un file
		# creato dal pacchetto APPENA installato (es. un provider che rigenera
		# sempre lo stesso 'userbouquet.dbe00.tv'): senza controllare anche il
		# disco, non solo in usedNames, il ripristino sovrascriverebbe in
		# silenzio il bouquet nuovo invece di restare un preferito distinto.
		# In caso di scontro si antepone un prefisso al nome (non un suffisso
		# numerico) cosi' resta chiaro a colpo d'occhio che e' il preferito
		# preservato, non una seconda copia qualsiasi dello stesso bouquet.
		if fileName in usedNames or os.path.exists(os.path.join(ENIGMA2_DIR, fileName)):
			fileName = "userbouquet.preferiti_%s%s" % (baseName, info["ext"])
			suffix = 2
			while fileName in usedNames or os.path.exists(os.path.join(ENIGMA2_DIR, fileName)):
				fileName = "userbouquet.preferiti_%s_%d%s" % (baseName, suffix, info["ext"])
				suffix += 1
		usedNames.add(fileName)

		path = os.path.join(ENIGMA2_DIR, fileName)
		with open(path, "w", encoding="utf-8") as f:
			f.write("#NAME %s\n" % (bouquet.get("title") or "Preferiti"))
			for tref, name in matched:
				f.write("#SERVICE %s\n" % tref)
				if name:
					f.write("#DESCRIPTION %s\n" % name)

		restoredByKind[kind].append((bouquet.get("position", 10 ** 9), fileName))
		restoredCount += 1

	anyRestored = False
	for kind, entries in restoredByKind.items():
		if entries:
			_registerBouquetsAtPositions(kind, entries)
			anyRestored = True

	if anyRestored:
		from enigma import eDVBDB
		eDVBDB.getInstance().reloadBouquets()

	return restoredCount


def _currentServicesByKey():
	from enigma import eServiceCenter, eServiceReference
	refstr = "1:7:1:0:0:0:0:0:0:0:(type == 1) || (type == 17) || (type == 22) || (type == 25) || (type == 134) || (type == 195) || (type == 2) || (type == 10)"
	serviceHandler = eServiceCenter.getInstance()
	lst = serviceHandler.list(eServiceReference(refstr))
	byKey = {}
	if lst is None:
		return byKey
	while True:
		service = lst.getNext()
		if service is None or not service.valid():
			break
		tref = service.toString()
		key = _parseServiceKey("#SERVICE " + tref)
		if key:
			byKey[key] = tref
	return byKey


def _registerBouquetsAtPositions(kind, entries):
	"""entries: [(position, fileName), ...] per un solo 'kind' ('tv' o
	'radio'). Inserisce ciascuno il piu' vicino possibile alla sua posizione
	originale (indice tra le righe 'FROM BOUQUET' della lista giusta): se
	prima dell'installazione un bouquet era il terzo, torna ad essere il
	terzo, non l'ultimo ne' il primo."""
	info = BOUQUET_KINDS[kind]
	listPath = os.path.join(ENIGMA2_DIR, info["list"])
	try:
		with open(listPath, "r", encoding="utf-8", errors="ignore") as f:
			lines = f.readlines()
	except OSError:
		lines = ["#NAME Bouquets (%s)\n" % ("TV" if kind == "tv" else "Radio")]
	existing = "".join(lines)
	headerLen = 1 if lines and lines[0].lower().startswith("#name") else 0

	toInsert = [(position, name) for position, name in entries if name not in existing]
	toInsert.sort(key=lambda x: x[0])

	for position, fileName in toInsert:
		line = '#SERVICE 1:7:%d:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet\n' % (info["ref_type"], fileName)
		insertAt = max(headerLen, min(headerLen + position, len(lines)))
		lines.insert(insertAt, line)

	with open(listPath, "w", encoding="utf-8") as f:
		f.writelines(lines)
