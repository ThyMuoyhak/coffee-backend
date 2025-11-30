from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import crud
import schemas

router = APIRouter(prefix="/api/v1", tags=["cart"])

@router.get("/cart/", response_model=List[schemas.CartItem])
def read_cart_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_cart_items(db, skip=skip, limit=limit)

@router.post("/cart/", response_model=schemas.CartItem)
def add_to_cart(cart_item: schemas.CartItemCreate, db: Session = Depends(get_db)):
    return crud.create_cart_item(db=db, cart_item=cart_item)

@router.delete("/cart/{cart_item_id}")
def remove_from_cart(cart_item_id: int, db: Session = Depends(get_db)):
    db_cart_item = crud.delete_cart_item(db=db, cart_item_id=cart_item_id)
    if db_cart_item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Item removed from cart"}

@router.delete("/cart/")
def clear_cart(db: Session = Depends(get_db)):
    return crud.clear_cart(db=db)