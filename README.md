# SettingsHub

Framework modulare per Enigma2 che permette di installare e aggiornare
i canali/bouquet da diversi "setting man" (provider di setting satellitari),
tutti tramite un'unica interfaccia in stile EPGImport.

## Caratteristiche

- Configurazione salvata esclusivamente in `config.plugins.settingshub.*`
  (nessun file sparso), quindi portabile tra decoder.
- Un solo setting man attivo alla volta, scelto dalla schermata Impostazioni.
- Controllo automatico dei nuovi setting con intervallo/orario configurabili.
- Preservazione dei bouquet preferiti (posizione esatta, TV e radio) durante
  la reinstallazione dei setting.
- Reinstalla solo se la data del pacchetto e' diversa da quella gia'
  installata (con conferma esplicita per un reinstallo forzato).
- Funzione di reset per ripartire da una base pulita.

## Provider inclusi

- **Vhannibal** (vhannibal.net)
- **Morpheus883** (morpheus883.altervista.org)
- **Andrea del 1984** (github.com/Andreadel1984/Liste-Canali-Enigma2-Italia)
- **ManuTEK** (manutek.it, per zona/citta')
- **Ciefp** (github.com/ciefp/ciefpsettings-enigma2-zipped)

Ogni provider vive nella propria sottocartella in `providers/` e implementa
il contratto definito in `api.py` (`SettingProvider`).

## Installazione

Copiare il contenuto di
`usr/lib/enigma2/python/Plugins/Extensions/SettingsHub/` in
`/usr/lib/enigma2/python/Plugins/Extensions/SettingsHub/` sul decoder,
poi riavviare Enigma2.
