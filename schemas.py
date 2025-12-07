# schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

# ========== PRODUCT SCHEMAS ==========
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        from_attributes = True

# ========== CART SCHEMAS ==========
class CartItemBase(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price: float
    sugar_level: str = "regular"
    image: Optional[str] = None

class CartItemCreate(CartItemBase):
    pass

class CartItem(CartItemBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        from_attributes = True

# ========== ORDER SCHEMAS ==========
class OrderItem(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price: float
    sugar_level: Optional[str] = "regular"

class OrderBase(BaseModel):
    customer_name: str
    phone_number: str
    delivery_address: Optional[str] = None
    items: List[OrderItem]
    total_amount: float
    currency: str = "USD"
    notes: Optional[str] = None

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    admin_notes: Optional[str] = None

class Order(OrderBase):
    id: int
    order_number: str
    status: str = "pending"
    payment_status: str = "pending"
    payment_method: Optional[str] = "khqr"
    khqr_md5: Optional[str] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        from_attributes = True

# ========== ADMIN SCHEMAS ==========
class AdminUserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "admin"

class AdminUserCreate(AdminUserBase):
    password: str

class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class AdminUserLogin(BaseModel):
    email: EmailStr
    password: str

class AdminUser(AdminUserBase):
    id: int
    is_active: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        from_attributes = True

# ========== TOKEN SCHEMAS ==========
class TokenData(BaseModel):
    email: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    admin: Optional[Dict[str, Any]] = None

# ========== DASHBOARD SCHEMAS ==========
class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_products: int
    pending_orders: int
    completed_orders: int
    today_orders: int
    today_revenue: float

# ========== KHQR PAYMENT SCHEMAS ==========
class KHQRRequest(BaseModel):
    order_number: str
    amount: float
    currency: str = "USD"

class KHQRResponse(BaseModel):
    qr_data: str
    md5_hash: str
    deeplink: Optional[str] = None
    qr_image: Optional[str] = None

class PaymentStatusResponse(BaseModel):
    order_number: str
    payment_status: str
    transaction_data: Dict[str, Any]