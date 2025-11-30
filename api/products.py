from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import crud
import schemas

router = APIRouter(prefix="/api/v1", tags=["products"])

@router.get("/products/", response_model=List[schemas.CoffeeProduct])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_products(db, skip=skip, limit=limit)

@router.get("/products/{product_id}", response_model=schemas.CoffeeProduct)
def read_product(product_id: int, db: Session = Depends(get_db)):
    db_product = crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.post("/products/", response_model=schemas.CoffeeProduct)
def create_product(product: schemas.CoffeeProductCreate, db: Session = Depends(get_db)):
    return crud.create_product(db=db, product=product)

@router.get("/categories/")
def get_categories(db: Session = Depends(get_db)):
    products = crud.get_products(db)
    categories = list(set(product.category for product in products if product.category))
    return {"categories": categories}

@router.get("/products/category/{category}")
def get_products_by_category(category: str, db: Session = Depends(get_db)):
    products = crud.get_products(db)
    filtered_products = [product for product in products if product.category == category]
    return filtered_products