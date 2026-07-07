# How PAUL Works — AI Pipeline Transparency

Dieses Dokument beschreibt exakt, was PAULs KI-Pipeline in jedem Schritt tut,
welche Prompts verwendet werden und welche Entscheidungen automatisch vs. manuell getroffen werden.

**Live-Ansicht der Prompts:** `GET /api/v1/analyze/prompts` (auch unter `/docs` im Swagger UI)

---

## Überblick: Zwei-Stufen-Pipeline

```
Datei-Upload ──> Text-Extraktion ──> KI-Klassifikation ──> KI-Extraktion ──> Mensch prüft ──> Datenbank
 (beliebiges        (pdfplumber,      (Dokumenttyp +       (Produktdaten     (bearbeiten,     (Produkt
  Format)            OCR, openpyxl)     Confidence +         + Zitate pro      bestätigen)      anlegen/
                                        Begründung)          Attribut)                          updaten)
```

---

## Schritt 1: Text-Extraktion

Bevor die KI etwas sieht, wird der Rohtext aus der Datei extrahiert:

| Format | Methode |
|--------|---------|
| PDF | pdfplumber (Text + Tabellen), OCR-Fallback für Scans |
| PNG, JPG, TIFF, BMP, WEBP | Tesseract OCR (Deutsch + Englisch) |
| XLSX, XLS | openpyxl, alle Sheets |
| CSV, TSV | Python csv-Modul |
| JSON | json.loads + pretty-print |
| XML | Raw UTF-8 |
| TXT, MD, LOG | Direkt lesen |

**Kein Preprocessing, kein Cleaning** — die KI bekommt den Text so wie er aus der Datei kommt.

---

## Schritt 2: KI-Klassifikation (Stage 1)

### Was passiert

Das LLM erhält den extrahierten Text (max. 8.000 Zeichen) und soll bestimmen:

1. **Dokumenttyp** — einer von 10 bekannten Typen
2. **Confidence** — Sicherheit von 0 bis 100
3. **Begründung** — warum dieser Typ, mit Verweis auf konkrete Stellen im Dokument
4. **Multi-Produkt** — ob mehrere Produkte erkannt wurden

### Die 10 Dokumenttypen

| Typ | Was die KI erwartet |
|-----|---------------------|
| Datasheet | Technische Spezifikationen, Tabellen mit Werten |
| Lab Report | Testergebnisse, Prüfbedingungen, Pass/Fail |
| Certificate | Zertifikatsnummer, ausstellende Stelle, Normen |
| Software Documentation | Firmware, Protokolle, Konfiguration |
| Bill of Materials | Komponentenlisten, Materialien |
| Marketing Material | Werbetext, vereinfachte Specs |
| Compliance Declaration | EU-Konformität, Richtlinien, Normen |
| Safety Data Sheet | Gefahrstoffe, CAS-Nummern, Entsorgung |
| Product Specification | Detaillierte technische Parameter |
| Test Report | Messverfahren, Messwerte, Toleranzen |

### Confidence Gate

- **>= 85%**: Automatische Weiterleitung an Extraktion
- **< 85%**: Stopp — der Benutzer muss den Dokumenttyp manuell auswählen oder bestätigen

### Der Classifier-Prompt (vollständig)

```
You are a document classifier for an industrial product data platform.
Your job is to identify what type of product document this is.

Possible document types:
- Datasheet
- Lab Report
- Certificate
- Software Documentation
- Bill of Materials
- Marketing Material
- Compliance Declaration
- Safety Data Sheet
- Product Specification
- Test Report

Rules:
- Pick exactly ONE type from the list above, or "Unknown" if none fits.
- Provide a confidence score from 0 to 100.
- Explain WHY you chose this type — reference specific parts of the document
  (headers, tables, phrases, structure).
- If you detect multiple products in the document, set multi_product to true.

Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):
{"document_type": "...", "confidence": <0-100>, "reasoning": "...",
 "multi_product": <true|false>, "detected_products": ["article or name if visible", ...]}

<document>
[hier kommt der extrahierte Text, max 8.000 Zeichen]
</document>
```

---

## Schritt 3: KI-Extraktion (Stage 2)

### Was passiert

Ein zweites LLM-Call mit einem **dokumenttyp-spezifischen Prompt** extrahiert strukturierte Produktdaten.
Der Text wird auf max. 12.000 Zeichen gekürzt.

### Was extrahiert wird

Für jedes erkannte Produkt:
- **Artikelnummer** und **Name**
- **Produktfamilie** (Timer, Motion Sensor, Room Thermostat, KNX Actuator, Energy Meter — oder Vorschlag für neue)
- **Attribute** (Schlüssel-Wert-Paare, z.B. `voltage: "230V"`)
- **Zitate** — für JEDES extrahierte Attribut eine Quellenangabe, wo im Dokument der Wert gefunden wurde

### Typspezifische Anweisungen

Die KI bekommt je nach Dokumenttyp andere Hinweise, worauf sie achten soll:

**Datasheet:** Artikelnummer, elektrische Specs (Spannung, Strom, Leistung), physische Specs (Maße, Gewicht), IP-Schutzklasse, Zertifizierungen, RoHS/REACH, Detektions-Specs (Sensoren), Steuerungs-Specs (Thermostate), Kommunikation (KNX, BLE)

**Lab Report:** Prüfling, Prüfnorm (IEC, EN, UL), Prüfbedingungen, Ergebnisse (Pass/Fail), Abweichungen, Prüflabor, Prüfdatum

**Certificate:** Zertifikatsnummer, Stelle (TÜV, VDE, UL), zertifiziertes Produkt, Normen, Gültigkeit, Umfang, Einschränkungen

**Software Documentation:** Betroffene Produkte, Firmware-Version, Protokolle, Konfigurationsparameter, API-Endpoints

**Bill of Materials:** Elternprodukt, Komponentenliste mit Teilenummern, Materialien, Mengen, Lieferanten

**Marketing Material:** Produktname, Verkaufsargumente, Einsatzbereiche. Hinweis: "Be careful: marketing materials may overstate capabilities."

**Compliance Declaration:** Abgedeckte Produkte, Richtlinien (LVD, EMC, RED, RoHS, REACH, WEEE), harmonisierte Normen

**Safety Data Sheet:** Produktidentifikation, Gefahrstoffe + Konzentrationen, CAS-Nummern, Sicherheitsklassifikationen, Entsorgung

**Product Specification:** Alle technischen Parameter mit exakten Werten, Leistungsdaten, Bestellinformationen

**Test Report:** Prüfling, Prüfverfahren, Messwerte + Toleranzen, Pass/Fail-Kriterien, Prüfgeräte, Umgebungsbedingungen

### Zitat-Pflicht

Die KI muss für **jeden** extrahierten Wert angeben, wo sie ihn gefunden hat. Beispiele:
- `"Table on page 2, row 'Rated Voltage'"`
- `"Header: 'LUXA 500-360'"`
- `"Certificate number in upper right corner"`

Bei unsicheren Werten muss die KI dies im Zitat vermerken.

---

## Schritt 4: Menschliche Prüfung

Der Benutzer sieht im Frontend:
- **Klassifikation**: Dokumenttyp, Confidence-Score, Begründung der KI
- **Extrahierte Produkte**: Alle Attribute mit Zitaten
- **Diff-Anzeige** (falls Produkt bereits existiert):
  - Grün: Neues Attribut
  - Gelb: Geänderter Wert (mit "war: alter Wert")
  - Grau: Unverändert aus DB übernommen
- **Duplikat-Warnung** bei gleicher Artikelnummer über mehrere Dateien

Der Benutzer kann Werte bearbeiten, den Dokumenttyp korrigieren und neu extrahieren lassen, oder bestätigen.

---

## Schritt 5: Persistierung + Export

Nach Bestätigung:
1. Produkt wird in PostgreSQL angelegt oder aktualisiert
2. Originaldatei wird unter UUID gespeichert (Download unter `/api/v1/ingest/documents/{id}/download`)
3. Automatischer Export an Product-Layer (`/api/v1/export/products.json`, Schema `0.1.0`)

---

## LLM-Konfiguration

- **Provider-Chain**: Konfigurierbar über `config/llm_agents.json` und `DATA_LAYER_LLM_CHAIN`
- **Retry**: 3 Versuche mit exponentiellem Backoff pro Provider
- **Fallback**: Wenn ein Provider ausfällt, wird der nächste in der Chain versucht
- **Cooldown**: 2 Sekunden zwischen Calls, 60 Sekunden Sperre nach erschöpften Retries
- **Temperatur**: 0.1 (niedrig = deterministisch, wenig kreativ)

Aktive Konfiguration live einsehbar unter `GET /api/v1/analyze/prompts`.

---

## Was PAUL NICHT tut

- **Kein Training**: Es wird kein eigenes Modell trainiert — PAUL nutzt existierende LLMs
- **Keine automatische Freigabe**: Jede Extraktion muss von einem Menschen bestätigt werden
- **Kein Text-Cleaning**: Der Rohtext geht unverändert an die KI
- **Keine Halluzinations-Garantie**: Die Zitat-Pflicht und der Human-Review-Schritt minimieren das Risiko, schließen es aber nicht aus
