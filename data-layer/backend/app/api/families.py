from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ProductFamilyCreate, ProductFamilyOut, ProductFamilyUpdate
from app.core.database import get_db
from app.models.product import ProductFamily

router = APIRouter(prefix="/families", tags=["families"])


@router.get("/", response_model=list[ProductFamilyOut])
def list_families(db: Session = Depends(get_db)):
    return db.query(ProductFamily).order_by(ProductFamily.name).all()


@router.post("/", response_model=ProductFamilyOut, status_code=201)
def create_family(body: ProductFamilyCreate, db: Session = Depends(get_db)):
    if db.query(ProductFamily).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="Family name already exists")
    family = ProductFamily(**body.model_dump())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@router.get("/{family_id}", response_model=ProductFamilyOut)
def get_family(family_id: UUID, db: Session = Depends(get_db)):
    family = db.get(ProductFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.patch("/{family_id}", response_model=ProductFamilyOut)
def update_family(family_id: UUID, body: ProductFamilyUpdate, db: Session = Depends(get_db)):
    family = db.get(ProductFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(family, field, value)
    db.commit()
    db.refresh(family)
    return family


@router.delete("/{family_id}", status_code=204)
def delete_family(family_id: UUID, db: Session = Depends(get_db)):
    family = db.get(ProductFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    db.delete(family)
    db.commit()
