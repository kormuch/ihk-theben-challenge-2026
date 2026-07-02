"""
10 realistische Theben-Produkte als Seed-Daten.
Absichtlich mit leichten Inkonsistenzen (fehlende Felder, unterschiedliche Einheitenschreibweisen)
um die Normalisierung zu demonstrieren.
"""

PRODUCTS = [
    # ── Zeitschaltuhren ──────────────────────────────────────────────────────
    {
        "article_number": "TR 610 top2",
        "name": "Zeitschaltuhr TR 610 top2",
        "family": "Zeitschaltuhr",
        "attributes": {
            "spannung": "230 V AC",
            "schaltleistung": "3680 W",
            "schaltvorgaenge_pro_tag": 48,
            "ganggenauigkeit": "±1 s/Tag",
            "schutzklasse": "IP 20",
            "einbaubreite": "2 TE",
            "zertifizierungen": ["CE", "VDE"],
            "rohs_konform": True,
            "betriebstemperatur": "-10 … +55 °C",
            "einfuehrungsdatum": "2019-03-01",
        },
    },
    {
        "article_number": "TR 612 top2",
        "name": "Zeitschaltuhr TR 612 top2 (16A)",
        "family": "Zeitschaltuhr",
        "attributes": {
            "spannung": "230V AC",          # Schreibweise absichtlich anders als TR 610
            "schaltleistung": "3680W",      # ohne Leerzeichen
            "schaltvorgaenge_pro_tag": 48,
            "ganggenauigkeit": "±1 s/Tag",
            "schutzklasse": "IP20",         # ohne Leerzeichen
            "einbaubreite": "2 TE",
            "zertifizierungen": ["CE", "VDE", "UL"],
            "rohs_konform": True,
            "betriebstemperatur": "-10 bis +55 °C",
            "einfuehrungsdatum": "2020-06-15",
        },
    },
    {
        "article_number": "TR 624 top2",
        "name": "Jahresschaltuhr TR 624 top2",
        "family": "Zeitschaltuhr",
        "attributes": {
            "spannung": "230 V AC",
            "schaltleistung": "3680 W",
            "schaltvorgaenge_pro_tag": 96,
            "ganggenauigkeit": "±0,5 s/Tag",
            "schutzklasse": "IP 20",
            "einbaubreite": "4 TE",
            "zertifizierungen": ["CE", "VDE"],
            "rohs_konform": True,
            "betriebstemperatur": "-10 … +55 °C",
            "einfuehrungsdatum": "2021-01-10",
            # fehlende Felder absichtlich weggelassen
        },
    },

    # ── Bewegungsmelder ──────────────────────────────────────────────────────
    {
        "article_number": "LUXA 102-360",
        "name": "Bewegungsmelder LUXA 102-360",
        "family": "Bewegungsmelder",
        "attributes": {
            "spannung": "230 V AC",
            "erfassungswinkel": 360,
            "reichweite": "12 m",
            "schaltleistung": "1000 W",
            "nachlaufzeit": "1 s … 30 min",
            "helligkeitsschwelle": "10 … 2000 Lux",
            "schutzklasse": "IP 44",
            "montage": "Decke",
            "zertifizierungen": ["CE"],
            "rohs_konform": True,
            "reach_konform": True,
            "einfuehrungsdatum": "2018-09-01",
        },
    },
    {
        "article_number": "LUXA 104-360",
        "name": "Bewegungsmelder LUXA 104-360 (Außen)",
        "family": "Bewegungsmelder",
        "attributes": {
            "spannung": "230 V AC",
            "erfassungswinkel": 360,
            "reichweite": "12m",            # ohne Leerzeichen
            "schaltleistung": "2300 W",
            "nachlaufzeit": "10 s … 30 min",
            "helligkeitsschwelle": "2 … 2000 Lux",
            "schutzklasse": "IP 55",
            "montage": "Decke/Wand",
            "zertifizierungen": ["CE", "VDE"],
            "rohs_konform": True,
            # reach_konform fehlt
            "einfuehrungsdatum": "2019-02-14",
        },
    },
    {
        "article_number": "PD 180i KNX",
        "name": "Präsenzmelder PD 180i KNX",
        "family": "Bewegungsmelder",
        "attributes": {
            "spannung": "29 V DC (KNX)",
            "erfassungswinkel": 180,
            "reichweite": "8 m",
            "schaltleistung": None,         # KNX-Bus, keine direkte Schaltleistung
            "nachlaufzeit": "10 s … 60 min",
            "helligkeitsschwelle": "0 … 2000 Lux",
            "schutzklasse": "IP 20",
            "montage": "Decke",
            "zertifizierungen": ["CE", "KNX"],
            "rohs_konform": True,
            "reach_konform": True,
            "einfuehrungsdatum": "2022-03-07",
        },
    },
    {
        "article_number": "ARGUS 220 KNX",
        "name": "Präsenzmelder ARGUS 220 KNX",
        "family": "Bewegungsmelder",
        "attributes": {
            "spannung": "29V DC (KNX)",
            "erfassungswinkel": 220,
            "reichweite": "10 m",
            "schaltleistung": None,
            "nachlaufzeit": "10 s … 60 min",
            "helligkeitsschwelle": "0 … 2000 Lux",
            "schutzklasse": "IP 20",
            "montage": "Wand",
            "zertifizierungen": ["CE", "KNX", "VDE"],
            "rohs_konform": True,
            "reach_konform": True,
            "einfuehrungsdatum": "2023-01-20",
        },
    },

    # ── Raumthermostate ──────────────────────────────────────────────────────
    {
        "article_number": "RAMSES 831 top2",
        "name": "Raumthermostat RAMSES 831 top2",
        "family": "Raumthermostat",
        "attributes": {
            "spannung": "230 V AC",
            "temperaturbereich": "+5 … +30 °C",
            "schaltdifferenz": "0,3 K",
            "ausgang": "Relais 1A",
            "display": True,
            "knx_faehig": False,
            "schutzklasse": "IP 30",
            "einbauart": "Aufputz",
            "zertifizierungen": ["CE", "VDE"],
            "rohs_konform": True,
            "energieeffizienzklasse": "A",
            "einfuehrungsdatum": "2017-11-01",
        },
    },
    {
        "article_number": "RAMSES 833 top2",
        "name": "Raumthermostat RAMSES 833 top2",
        "family": "Raumthermostat",
        "attributes": {
            "spannung": "230 V AC",
            "temperaturbereich": "+5 … +30 °C",
            "schaltdifferenz": "0,2 K",
            "ausgang": "Relais 2A",
            "display": True,
            "knx_faehig": False,
            "schutzklasse": "IP 30",
            "einbauart": "Unterputz",
            "zertifizierungen": ["CE", "VDE"],
            "rohs_konform": True,
            "energieeffizienzklasse": "A+",
            "einfuehrungsdatum": "2018-04-03",
        },
    },
    {
        "article_number": "RAMSES 862 top2",
        "name": "Raumthermostat RAMSES 862 top2 KNX",
        "family": "Raumthermostat",
        "attributes": {
            "spannung": "29 V DC (KNX)",
            "temperaturbereich": "+5 … +35 °C",
            "schaltdifferenz": "0,1 K",
            "ausgang": "KNX-Bus",
            "display": True,
            "knx_faehig": True,
            "schutzklasse": "IP 20",
            "einbauart": "Unterputz",
            "zertifizierungen": ["CE", "KNX", "VDE"],
            "rohs_konform": True,
            "energieeffizienzklasse": "A++",
            "einfuehrungsdatum": "2021-09-15",
        },
    },
]
