from sqlalchemy.orm import Session
from models import CoffeeProduct, CartItem, Order
import schemas
import uuid
from datetime import datetime

# Coffee Product CRUD
def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(CoffeeProduct).filter(CoffeeProduct.is_available == True).offset(skip).limit(limit).all()

def get_product(db: Session, product_id: int):
    return db.query(CoffeeProduct).filter(CoffeeProduct.id == product_id).first()

def create_product(db: Session, product: schemas.CoffeeProductCreate):
    db_product = CoffeeProduct(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, product_id: int, product: schemas.CoffeeProductUpdate):
    db_product = db.query(CoffeeProduct).filter(CoffeeProduct.id == product_id).first()
    if db_product:
        update_data = product.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_product, field, value)
        db.commit()
        db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int):
    db_product = db.query(CoffeeProduct).filter(CoffeeProduct.id == product_id).first()
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product

# Cart CRUD
def get_cart_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(CartItem).offset(skip).limit(limit).all()

def create_cart_item(db: Session, cart_item: schemas.CartItemCreate):
    db_cart_item = CartItem(**cart_item.dict())
    db.add(db_cart_item)
    db.commit()
    db.refresh(db_cart_item)
    return db_cart_item

def delete_cart_item(db: Session, cart_item_id: int):
    db_cart_item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()
    if db_cart_item:
        db.delete(db_cart_item)
        db.commit()
    return db_cart_item

def clear_cart(db: Session):
    db.query(CartItem).delete()
    db.commit()
    return {"message": "Cart cleared successfully"}

# Order CRUD
def get_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Order).offset(skip).limit(limit).all()

def get_order_by_number(db: Session, order_number: str):
    return db.query(Order).filter(Order.order_number == order_number).first()

def create_order(db: Session, order: schemas.OrderCreate):
    # Generate unique order number
    order_number = f"BH{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    
    # Create order data dictionary
    order_data = order.dict()
    order_data['order_number'] = order_number
    
    db_order = Order(**order_data)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def update_order_status(db: Session, order_id: int, status: str):
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order

def update_order_payment_status(db: Session, order_number: str, payment_status: str, khqr_md5: str = None):
    db_order = db.query(Order).filter(Order.order_number == order_number).first()
    if db_order:
        db_order.payment_status = payment_status
        if khqr_md5:
            db_order.khqr_md5 = khqr_md5
        db.commit()
        db.refresh(db_order)
    return db_order
    db_order = db.query(Order).filter(Order.order_number == order_number).first()
    if db_order:
        db_order.payment_status = payment_status
        if khqr_md5:
            db_order.khqr_md5 = khqr_md5
        db.commit()
        db.refresh(db_order)
    return db_order