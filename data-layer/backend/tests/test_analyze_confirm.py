import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("sqlalchemy") is None, "sqlalchemy is not installed")
class AnalyzeConfirmPersistenceTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base

        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.tmp.name) / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        self.tmp.cleanup()

    def _confirm(self, body, db):
        from app.api import analyze

        with (
            patch("app.api.export.export_products_json"),
            patch("app.lakehouse.iceberg_writer.write_product_to_iceberg", return_value=False),
            patch("app.lakehouse.iceberg_writer.write_document_lineage"),
        ):
            return analyze.confirm_extraction(body, db)

    def test_confirm_creates_unsorted_product_with_review_added_attribute(self):
        from app.api.analyze import ConfirmProduct, ConfirmRequest
        from app.models.product import Product, ProductAttributeHistory

        db = self.Session()
        try:
            response = self._confirm(
                ConfirmRequest(
                    stored_as="review-source.pdf",
                    doc_type="Datasheet",
                    products=[
                        ConfirmProduct(
                            article_number="NEW-100",
                            name="New Review Product",
                            family_id=None,
                            attributes={"manual_voltage": "230 V"},
                        )
                    ],
                ),
                db,
            )

            product = db.query(Product).filter_by(article_number="NEW-100").one()
            self.assertEqual(response["created"], ["NEW-100"])
            self.assertEqual(product.name, "New Review Product")
            self.assertEqual(product.family.name, "Unsorted")
            self.assertEqual(product.attributes["manual_voltage"], "230 V")
            history = db.query(ProductAttributeHistory).filter_by(
                product_id=product.id,
                attribute_key="manual_voltage",
            ).one()
            self.assertEqual(history.value, "230 V")
            self.assertEqual(history.source_uri, "data-layer://ai-ingest/review-source.pdf")
            self.assertEqual(history.operation, "ai_confirm")
        finally:
            db.close()

    def test_confirm_updates_existing_product_review_fields_and_attributes(self):
        from app.api.analyze import ConfirmProduct, ConfirmRequest
        from app.models.product import Product, ProductAttributeHistory, ProductFamily

        db = self.Session()
        try:
            old_family = ProductFamily(name="Old Family", attribute_schema={})
            reviewed_family = ProductFamily(name="Reviewed Family", attribute_schema={})
            db.add_all([old_family, reviewed_family])
            db.commit()
            db.refresh(old_family)
            db.refresh(reviewed_family)

            existing = Product(
                article_number="EXIST-200",
                name="Old Name",
                family_id=old_family.id,
                attributes={"kept": "yes", "changed": "old"},
            )
            db.add(existing)
            db.commit()

            response = self._confirm(
                ConfirmRequest(
                    stored_as="review-source.pdf",
                    doc_type="Certificate",
                    products=[
                        ConfirmProduct(
                            article_number="EXIST-200",
                            name="Reviewed Name",
                            family_id=str(reviewed_family.id),
                            attributes={"changed": "new", "manual_note": "persist me"},
                        )
                    ],
                ),
                db,
            )

            product = db.query(Product).filter_by(article_number="EXIST-200").one()
            self.assertEqual(response["updated"], ["EXIST-200"])
            self.assertEqual(product.name, "Reviewed Name")
            self.assertEqual(product.family_id, reviewed_family.id)
            self.assertEqual(product.attributes["kept"], "yes")
            self.assertEqual(product.attributes["changed"], "new")
            self.assertEqual(product.attributes["manual_note"], "persist me")
            changed_history = db.query(ProductAttributeHistory).filter_by(
                product_id=product.id,
                attribute_key="changed",
            ).one()
            manual_history = db.query(ProductAttributeHistory).filter_by(
                product_id=product.id,
                attribute_key="manual_note",
            ).one()
            self.assertEqual(changed_history.value, "new")
            self.assertEqual(changed_history.previous_value, "old")
            self.assertEqual(manual_history.value, "persist me")
            self.assertIsNone(manual_history.previous_value)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
