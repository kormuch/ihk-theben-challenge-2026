"""
Seed script: inserts product families and 10 products into the database.
Run inside the backend container: python -m app.seed.seed
"""
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.database import Base
import app.models  # noqa — register all models

from app.models.product import ProductFamily, Product
from app.seed.families import FAMILIES
from app.seed.products import PRODUCTS


def run(db: Session) -> None:
    # ── Families ──────────────────────────────────────────────────────────────
    family_map: dict[str, ProductFamily] = {}
    for fdef in FAMILIES:
        existing = db.query(ProductFamily).filter_by(name=fdef["name"]).first()
        if existing:
            family_map[fdef["name"]] = existing
            print(f"  [skip] Family already exists: {fdef['name']}")
        else:
            family = ProductFamily(**fdef)
            db.add(family)
            db.flush()
            family_map[fdef["name"]] = family
            print(f"  [+] Family created: {fdef['name']}")

    # ── Products ──────────────────────────────────────────────────────────────
    created = 0
    skipped = 0
    for pdef in PRODUCTS:
        if db.query(Product).filter_by(article_number=pdef["article_number"]).first():
            print(f"  [skip] Product already exists: {pdef['article_number']}")
            skipped += 1
            continue
        family = family_map.get(pdef["family"])
        if not family:
            print(f"  [warn] Unknown family '{pdef['family']}' for {pdef['article_number']} — skipping")
            continue
        product = Product(
            name=pdef["name"],
            article_number=pdef["article_number"],
            family_id=family.id,
            attributes=pdef["attributes"],
        )
        db.add(product)
        created += 1
        print(f"  [+] Product created: {pdef['article_number']}")

    db.commit()
    print(f"\nDone. {created} products created, {skipped} skipped.")


if __name__ == "__main__":
    print("Creating tables if not exists...")
    Base.metadata.create_all(bind=engine)
    print("Seeding database...")
    db = SessionLocal()
    try:
        run(db)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()
