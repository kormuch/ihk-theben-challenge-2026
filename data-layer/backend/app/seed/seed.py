"""
Seed script: inserts product families into the database.
Products are created via AI Ingest — no pre-generated data.
Run inside the backend container: python -m app.seed.seed
"""
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.database import Base
import app.models  # noqa — register all models

from app.models.product import ProductFamily
from app.seed.families import FAMILIES


def run(db: Session) -> None:
    for fdef in FAMILIES:
        existing = db.query(ProductFamily).filter_by(name=fdef["name"]).first()
        if existing:
            print(f"  [skip] Family already exists: {fdef['name']}")
        else:
            family = ProductFamily(**fdef)
            db.add(family)
            db.flush()
            print(f"  [+] Family created: {fdef['name']}")

    db.commit()
    print("\nDone.")


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
