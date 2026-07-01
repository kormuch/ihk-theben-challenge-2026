# Theben Challenge — IHK Innovationstage Zollernalb 2026

**Event:** Kollege Codex — Mi, 08. Juli 2026 | 13:00 Uhr
**Ort:** Theben AG, Haigerloch
**Team:** Korbinian Much + Christian Solva

---

## Problem

Produktinformationen bei Theben sind über zahlreiche Systeme und Formate verteilt:
- ERP, PLM, externe Portale, Datenbanken
- CSV, XLSX, JSON, XML, PDF, REST APIs
- Dokumente von Produktmanagern, Laboren (Prüfberichte), Tickets, Marketing

**Kern-Pain-Point:** Kein Single Source of Truth → kein verlässlicher Digitaler Produktpass möglich.

Zusätzliche Anforderungsbereiche:
- Analytics & Reporting (Compliance, KPIs)
- Cybersecurity (CRA, SBOM)
- Umwelt & Nachhaltigkeit (CO₂, Materialien, Recycling)
- Normen & Zertifizierungen (IEC/EN, CE, UL)
- Regulatorik (CRA, RED, RoHS, REACH, ESPR, Data Act)
- Lebenszyklus (Einführung, Service Life, End-of-Life)

---

## Challenge

Skalierbare, erweiterbare Plattform die:

- Produktdaten aus heterogenen Quellen einsammelt
- Daten normalisiert und harmonisiert (gemeinsames Datenmodell)
- Vielzahl von Produktattributen trackt
- Mehrere Produktfamilien mit unterschiedlichen Eigenschaften unterstützt
- Flexibles Datenmodell hat das mit neuen Regularien mitwächst
- Querying, Reporting, Analytics ermöglicht
- Als Fundament für Digitalen Produktpass dient
- Interaktives Web-UI bietet (suchen, filtern, bearbeiten, validieren, visualisieren)

**Schlagworte:** Abstraction — Generic — Informative — Interactive

---

## Architektur-Kernpunkte

### Ingestion Pipeline
- Quellen: JSON, XML, CSV, XLSX, PDF, REST API
- Normalisierung auf gemeinsames internes Datenmodell
- **Originaldokumente werden mitgespeichert und dem Produkt zugeordnet** (kein Datenverlust, volle Traceability zur Quelle)

### Datenmodell
- Dynamische/flexible Attributstruktur pro Produktfamilie (EAV-ähnlich)
- Referenz: Open Product Data (Attribute, Bauteile, variables Datenblatt)
- PostgreSQL als Datenbank

### API
- REST API (Kern der Lösung)
- OpenAPI/Swagger Dokumentation (Standard-Doku für alle Endpoints)
- Endpoints u.a.: Produkt anlegen, löschen, Attribute tracken, Dokumente anhängen, Queries

### UI
- Interaktives Web-Frontend
- Suche, Filter, Edit, Validierung, Visualisierung

---

## Constraints

- Docker Compose (containerisierte Lösung, ein oder mehrere Container)
- Persistenter Storage (Daten überleben Container-Restart)
- Keine zwingend externen Cloud-Services (Präferenz: lokal/Docker)
- Beliebiger Tech-Stack, Open-Source bevorzugt
- Konfiguration über Config-Files und/oder Umgebungsvariablen
- Config-Files sind wichtig

---

## Mock-Daten

- Keine Beispieldaten von Theben — wir generieren selbst
- **1000 Produkte**, mehrere Produktfamilien
- Theben-typische Produkte: Zeitschaltuhren, Bewegungsmelder, HVAC-Regler, etc.

---

## Extras

- **Jury-Agent:** KI-Agent der unsere Lösung bewertet (wird von Korbinian gebaut)

---

## Stack (vorläufig)

| Komponente | Tech |
|---|---|
| Datenbank | PostgreSQL |
| Container | Docker Compose |
| API | REST + OpenAPI/Swagger |
| Datenmodell | Dynamisch/EAV, Open Product Data |
| Mock-Daten | Generiert (1000 Produkte) |
| Docs | OpenAPI |
