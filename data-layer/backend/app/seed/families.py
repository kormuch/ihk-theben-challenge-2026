"""
Produktfamilien-Definitionen mit ihren erwarteten Attributen (attribute_schema).
Das Schema definiert welche Felder für diese Familie relevant sind —
es erzwingt sie nicht, aber das UI kann daraus Vollständigkeits-Checks bauen.
"""

FAMILIES = [
    {
        "name": "Zeitschaltuhr",
        "description": "Analoge und digitale Zeitschaltuhren für Hausinstallation und Industrie",
        "attribute_schema": {
            "spannung": {"type": "string", "label": "Nennspannung", "unit": "V", "required": True},
            "schaltleistung": {"type": "string", "label": "Schaltleistung", "unit": "W", "required": True},
            "schaltvorgaenge_pro_tag": {"type": "integer", "label": "Schaltvorgänge/Tag", "required": False},
            "ganggenauigkeit": {"type": "string", "label": "Ganggenauigkeit", "unit": "s/Tag", "required": False},
            "schutzklasse": {"type": "string", "label": "Schutzklasse (IP)", "required": True},
            "einbaubreite": {"type": "string", "label": "Einbaubreite", "unit": "TE", "required": False},
            "zertifizierungen": {"type": "list", "label": "Zertifizierungen", "required": True},
            "rohs_konform": {"type": "boolean", "label": "RoHS-konform", "required": True},
            "betriebstemperatur": {"type": "string", "label": "Betriebstemperatur", "unit": "°C", "required": False},
            "einfuehrungsdatum": {"type": "date", "label": "Einführungsdatum", "required": False},
        },
    },
    {
        "name": "Bewegungsmelder",
        "description": "Präsenz- und Bewegungsmelder für Innen- und Außenbereich",
        "attribute_schema": {
            "spannung": {"type": "string", "label": "Betriebsspannung", "unit": "V", "required": True},
            "erfassungswinkel": {"type": "integer", "label": "Erfassungswinkel", "unit": "°", "required": True},
            "reichweite": {"type": "string", "label": "Reichweite", "unit": "m", "required": True},
            "schaltleistung": {"type": "string", "label": "Schaltleistung max.", "unit": "W", "required": True},
            "nachlaufzeit": {"type": "string", "label": "Nachlaufzeit", "required": False},
            "helligkeitsschwelle": {"type": "string", "label": "Helligkeitsschwelle", "unit": "Lux", "required": False},
            "schutzklasse": {"type": "string", "label": "Schutzklasse (IP)", "required": True},
            "montage": {"type": "string", "label": "Montageart", "required": True},
            "zertifizierungen": {"type": "list", "label": "Zertifizierungen", "required": True},
            "rohs_konform": {"type": "boolean", "label": "RoHS-konform", "required": True},
            "reach_konform": {"type": "boolean", "label": "REACH-konform", "required": False},
            "einfuehrungsdatum": {"type": "date", "label": "Einführungsdatum", "required": False},
        },
    },
    {
        "name": "Raumthermostat",
        "description": "Elektronische Raumthermostate für Heizung, Kühlung und Lüftungssteuerung",
        "attribute_schema": {
            "spannung": {"type": "string", "label": "Betriebsspannung", "unit": "V", "required": True},
            "temperaturbereich": {"type": "string", "label": "Regelbereich", "unit": "°C", "required": True},
            "schaltdifferenz": {"type": "string", "label": "Schaltdifferenz", "unit": "K", "required": False},
            "ausgang": {"type": "string", "label": "Ausgangstyp", "required": True},
            "display": {"type": "boolean", "label": "Display vorhanden", "required": False},
            "knx_faehig": {"type": "boolean", "label": "KNX-fähig", "required": False},
            "schutzklasse": {"type": "string", "label": "Schutzklasse (IP)", "required": True},
            "einbauart": {"type": "string", "label": "Einbauart", "required": True},
            "zertifizierungen": {"type": "list", "label": "Zertifizierungen", "required": True},
            "rohs_konform": {"type": "boolean", "label": "RoHS-konform", "required": True},
            "energieeffizienzklasse": {"type": "string", "label": "Energieeffizienzklasse", "required": False},
            "einfuehrungsdatum": {"type": "date", "label": "Einführungsdatum", "required": False},
        },
    },
]
