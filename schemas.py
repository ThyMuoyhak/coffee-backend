from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# Coffee Product Schemas
class CoffeeProductBase(BaseModel):
    name: str
    price: float
    image: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = 0.0
    brew_time: Optional[str] = None
    is_available: bool = True
    stock: int = 100

class CoffeeProductCreate(CoffeeProductBase):
    pass

class CoffeeProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    brew_time: Optional[str] = None
    is_available: Optional[bool] = None
    stock: Optional[int] = None

class CoffeeProduct(CoffeeProductBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Cart Item Schemas
class CartItemBase(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price: float
    sugar_level: str = "regular"
    image: str

class CartItemCreate(CartItemBase):
    pass

class CartItem(CartItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Order Schemas
class OrderBase(BaseModel):
    customer_name: str
    phone_number: str
    delivery_address: str
    items: List[Dict[str, Any]]
    total_amount: float
    currency: str = "USD"

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    order_number: str
    status: str
    khqr_md5: Optional[str] = None
    payment_status: str
    created_at: datetime

    class Config:
        from_attributes = True

# KHQR Schemas
class KHQRRequest(BaseModel):
    amount: float
    currency: str
    order_number: str

class KHQRResponse(BaseModel):
    qr_data: str
    md5_hash: str
    deeplink: Optional[str] = None
    qr_image: Optional[str] = None

class PaymentStatusResponse(BaseModel):
    order_number: str
    payment_status: str
    transaction_data: Optional[Dict[str, Any]] = None