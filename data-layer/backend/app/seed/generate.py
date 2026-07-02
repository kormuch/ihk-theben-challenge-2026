"""
Generate 1000 realistic Theben-style products across multiple families.
Run inside the backend container: python -m app.seed.generate
"""
import random
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
import app.models  # noqa
from app.models.product import ProductFamily, Product
from app.seed.families import FAMILIES

# Extended family definitions for generation
FAMILY_TEMPLATES = {
    "Timer": {
        "prefixes": ["TR", "SU", "BT", "DTR", "WT"],
        "models": list(range(100, 999)),
        "suffixes": ["top2", "top3", "S", "R", "KNX", "BLE", "Pro", "Eco", ""],
        "attrs": lambda: {
            "voltage": random.choice(["230 V AC", "230V AC", "110 V AC", "24 V DC"]),
            "switching_capacity": random.choice(["3680 W", "2300 W", "1000 W", "3600W"]),
            "switching_cycles_per_day": random.choice([24, 48, 96, 144, 288]),
            "accuracy": random.choice(["±1 s/day", "±0.5 s/day", "±2 s/day"]),
            "protection_class": random.choice(["IP 20", "IP20", "IP 40", "IP 54"]),
            "module_width": random.choice(["1 MW", "2 MW", "3 MW", "4 MW"]),
            "certifications": random.choice([["CE"], ["CE", "VDE"], ["CE", "VDE", "UL"], ["CE", "KNX"]]),
            "rohs_compliant": True,
            "operating_temperature": random.choice(["-10 … +55 °C", "-20 … +50 °C", "-10 to +45 °C"]),
            "launch_date": f"{random.randint(2015, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        },
    },
    "Motion Sensor": {
        "prefixes": ["LUXA", "PD", "ARGUS", "MD", "PS"],
        "models": list(range(100, 999)),
        "suffixes": ["KNX", "BLE", "IP55", "Outdoor", "Flush", "360", "180", ""],
        "attrs": lambda: {
            "voltage": random.choice(["230 V AC", "230V AC", "29 V DC (KNX)", "24 V DC"]),
            "detection_angle": random.choice([90, 120, 180, 220, 280, 360]),
            "range": random.choice(["8 m", "10 m", "12 m", "16 m", "20m", "24 m"]),
            "switching_capacity": random.choice(["1000 W", "2000 W", "2300 W", None]),
            "follow_up_time": random.choice(["1 s … 30 min", "10 s … 30 min", "10 s … 60 min"]),
            "light_threshold": random.choice(["10 … 2000 Lux", "2 … 2000 Lux", "0 … 2000 Lux"]),
            "protection_class": random.choice(["IP 20", "IP 44", "IP 55", "IP55", "IP 65"]),
            "mounting": random.choice(["Ceiling", "Wall", "Ceiling/Wall", "Flush mount"]),
            "certifications": random.choice([["CE"], ["CE", "VDE"], ["CE", "KNX"], ["CE", "KNX", "VDE"]]),
            "rohs_compliant": True,
            "reach_compliant": random.choice([True, True, False, None]),
            "launch_date": f"{random.randint(2015, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        },
    },
    "Room Thermostat": {
        "prefixes": ["RAMSES", "LUXORliving", "ELPA", "RTH", "THR"],
        "models": list(range(100, 999)),
        "suffixes": ["top2", "top3", "KNX", "BLE", "S", "E", "Pro", ""],
        "attrs": lambda: {
            "voltage": random.choice(["230 V AC", "24 V AC/DC", "29 V DC (KNX)"]),
            "temperature_range": random.choice(["+5 … +30 °C", "+5 … +35 °C", "+7 … +32 °C"]),
            "switching_differential": random.choice(["0.1 K", "0.2 K", "0.3 K", "0.5 K"]),
            "output": random.choice(["Relay 1A", "Relay 2A", "Relay 5A", "KNX Bus", "0-10V"]),
            "display": random.choice([True, True, True, False]),
            "knx_capable": random.choice([True, False, False]),
            "protection_class": random.choice(["IP 20", "IP 30", "IP20"]),
            "mounting_type": random.choice(["Surface mount", "Flush mount", "DIN rail"]),
            "certifications": random.choice([["CE"], ["CE", "VDE"], ["CE", "KNX", "VDE"]]),
            "rohs_compliant": True,
            "energy_efficiency_class": random.choice(["A", "A+", "A++", "B"]),
            "launch_date": f"{random.randint(2015, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        },
    },
}

TARGET_COUNT = 1000


def run(db: Session) -> None:
    # Ensure families exist
    family_map: dict[str, ProductFamily] = {}
    for fdef in FAMILIES:
        existing = db.query(ProductFamily).filter_by(name=fdef["name"]).first()
        if existing:
            family_map[fdef["name"]] = existing
        else:
            family = ProductFamily(**fdef)
            db.add(family)
            db.flush()
            family_map[fdef["name"]] = family

    existing_count = db.query(Product).count()
    if existing_count >= TARGET_COUNT:
        print(f"Already {existing_count} products in DB, skipping generation.")
        return

    to_create = TARGET_COUNT - existing_count
    existing_articles = {r[0] for r in db.query(Product.article_number).all()}
    family_names = list(FAMILY_TEMPLATES.keys())
    created = 0

    for i in range(to_create * 2):  # overshoot to handle collisions
        if created >= to_create:
            break

        fname = random.choice(family_names)
        tmpl = FAMILY_TEMPLATES[fname]
        prefix = random.choice(tmpl["prefixes"])
        model = random.choice(tmpl["models"])
        suffix = random.choice(tmpl["suffixes"])
        article = f"{prefix} {model}" + (f" {suffix}" if suffix else "")

        if article in existing_articles:
            continue

        # Randomly drop some optional attributes to simulate real-world gaps
        attrs = tmpl["attrs"]()
        if random.random() < 0.15:
            keys = [k for k in attrs if attrs[k] is not None]
            if keys:
                del attrs[random.choice(keys)]

        product = Product(
            name=f"{fname} {article}",
            article_number=article,
            family_id=family_map[fname].id,
            attributes=attrs,
        )
        db.add(product)
        existing_articles.add(article)
        created += 1

        if created % 100 == 0:
            print(f"  {created}/{to_create} products created...")

    db.commit()
    print(f"\nDone. {created} products generated. Total: {existing_count + created}")


if __name__ == "__main__":
    print("Creating tables if not exists...")
    Base.metadata.create_all(bind=engine)
    print("Generating 1000 products...")
    db = SessionLocal()
    try:
        run(db)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()
