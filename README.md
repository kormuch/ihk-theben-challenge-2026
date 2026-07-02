# IHK Theben Challenge 2026 — Product Information System

**Event:** Kollege Codex — IHK Innovationstage Zollernalb | Mi, 08. Juli 2026
**Team:** Korbinian Much + Christian Solva

## Ziel

Skalierbare Plattform zur Aggregation, Normalisierung und Verwaltung von Produktdaten aus heterogenen Quellen — als Fundament für den Digitalen Produktpass.

---

## Repo-Struktur

```
/data-layer       # Korbinian — Ingestion, Normalisierung, PostgreSQL, Originaldateien
/product-layer    # Christian — REST API, OpenAPI, Web-UI
```

---

## data-layer (Korbinian)

- Ingestion Pipeline: CSV, JSON, XML, XLSX, PDF
- Normalisierung auf gemeinsames Datenmodell
- Dynamisches Attribut-Schema (EAV) pro Produktfamilie
- Originaldatei-Speicherung + Verknüpfung (Traceability)
- PostgreSQL

## product-layer (Christian)

- REST API
- OpenAPI / Swagger Dokumentation
- Web-UI: Upload, Produktübersicht, Attribut-Editor, DPP-Preview
- data lakehouse
- modules for different users (governance model)
- 

---

## Setup

```bash
docker compose up
```

Konfiguration über `.env` und `config/`.
