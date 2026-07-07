import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ProductFamily(Base):
    __tablename__ = "product_families"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    attribute_schema = Column(JSON, default=dict)  # defines expected attributes
    created_at = Column(DateTime, default=_utcnow)

    products = relationship("Product", back_populates="family", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    article_number = Column(String(100), unique=True, nullable=False)
    family_id = Column(Uuid, ForeignKey("product_families.id"), nullable=False)
    attributes = Column(JSON, default=dict)  # dynamic attributes (EAV via JSONB)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    family = relationship("ProductFamily", back_populates="products")
    documents = relationship("ProductDocument", back_populates="product", cascade="all, delete-orphan")
    attribute_history = relationship("ProductAttributeHistory", back_populates="product", cascade="all, delete-orphan")


class ProductDocument(Base):
    __tablename__ = "product_documents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id = Column(Uuid, ForeignKey("products.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    source_type = Column(String(50))   # csv, json, xml, xlsx, pdf, api
    doc_category = Column(String(100)) # Technisch, Regulatorik, Marketing, Qualität
    status = Column(String(50), default="pending")  # pending, processing, done, error
    error_message = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    product = relationship("Product", back_populates="documents")
    attribute_history = relationship("ProductAttributeHistory", back_populates="source_document")


class ProductAttributeHistory(Base):
    __tablename__ = "product_attribute_history"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id = Column(Uuid, ForeignKey("products.id"), nullable=False)
    attribute_key = Column(String(255), nullable=False)
    value = Column(JSON, default=dict)
    previous_value = Column(JSON, nullable=True)
    source_document_id = Column(Uuid, ForeignKey("product_documents.id"), nullable=True)
    source_uri = Column(String(1000))
    source_name = Column(String(500))
    source_type = Column(String(100))
    source_system = Column(String(255), default="paul-data-layer")
    lineage = Column(Text)
    operation = Column(String(50), default="upsert")
    owner = Column(String(255), default="Product Data Domain")
    domain = Column(String(100), default="product")
    classification = Column(String(100), default="internal")
    changed_by = Column(String(255), default="paul-ai-ingest")
    changed_at = Column(DateTime, default=_utcnow)

    product = relationship("Product", back_populates="attribute_history")
    source_document = relationship("ProductDocument", back_populates="attribute_history")
