from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import ProductCreate, ProductOut, ProductListItem, ProductUpdate
from app.core.database import get_db
from app.lineage.attribute_history import record_attribute_history
from app.models.product import Product, ProductFamily

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=list[ProductListItem])
def list_products(
    family_id: UUID | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if family_id:
        q = q.filter(Product.family_id == family_id)
    if search:
        q = q.filter(
            Product.name.ilike(f"%{search}%") |
            Product.article_number.ilike(f"%{search}%")
        )
    return q.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    if not db.get(ProductFamily, body.family_id):
        raise HTTPException(status_code=404, detail="Product family not found")
    if db.query(Product).filter_by(article_number=body.article_number).first():
        raise HTTPException(status_code=409, detail="Article number already exists")
    product = Product(**body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(joinedload(Product.documents), joinedload(Product.attribute_history))
        .filter(Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: UUID, body: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    data = body.model_dump(exclude_unset=True)
    # Merge attributes instead of replacing — preserves existing keys
    if "attributes" in data:
        previous_attributes = dict(product.attributes or {})
        merged = {**previous_attributes, **data["attributes"]}
        product.attributes = merged
        record_attribute_history(
            db,
            product=product,
            attributes=data["attributes"],
            previous_attributes=previous_attributes,
            source_uri=f"data-layer://api/products/{product_id}",
            source_system="paul-data-layer-api",
            lineage="data-layer-api -> data-layer-postgres -> curated-product",
            operation="api_patch",
            changed_by="data-layer-user",
        )
        data.pop("attributes")
    for field, value in data.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
