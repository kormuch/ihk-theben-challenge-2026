import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProductFamily(Base):
    __tablename__ = "product_families"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    attribute_schema = Column(JSON, default=dict)  # defines expected attributes
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="family")


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    article_number = Column(String(100), unique=True, nullable=False)
    family_id = Column(UUID(as_uuid=True), ForeignKey("product_families.id"), nullable=False)
    attributes = Column(JSON, default=dict)  # dynamic attributes (EAV via JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    family = relationship("ProductFamily", back_populates="products")
    documents = relationship("ProductDocument", back_populates="product")


class ProductDocument(Base):
    __tablename__ = "product_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    source_type = Column(String(50))   # csv, json, xml, xlsx, pdf, api
    doc_category = Column(String(100)) # Technisch, Regulatorik, Marketing, Qualität
    status = Column(String(50), default="pending")  # pending, processing, done, error
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="documents")
