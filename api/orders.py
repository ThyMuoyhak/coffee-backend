from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import crud
import schemas

router = APIRouter(prefix="/api/v1", tags=["orders"])

@router.get("/orders/", response_model=List[schemas.Order])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_orders(db, skip=skip, limit=limit)

@router.post("/orders/", response_model=schemas.Order)
def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        db_order = crud.create_order(db=db, order=order)
        
        # Start background payment checking (demo mode)
        from main import KHQR_AVAILABLE, check_payment_status_demo
        if not KHQR_AVAILABLE:
            background_tasks.add_task(check_payment_status_demo, db_order.order_number, db)
        
        return db_order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@router.get("/orders/{order_number}", response_model=schemas.Order)
def read_order(order_number: str, db: Session = Depends(get_db)):
    db_order = crud.get_order_by_number(db, order_number=order_number)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@router.put("/orders/{order_id}", response_model=schemas.Order)
def update_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
    db_order = crud.update_order_status(db=db, order_id=order_id, status=status)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order