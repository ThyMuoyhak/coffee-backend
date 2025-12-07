from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
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

    model_config = ConfigDict(from_attributes=True)

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
    updated_at: Optional[datetime] = None

# Cart Item Schemas
class CartItemBase(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price: float
    sugar_level: str = "regular"
    image: str

    model_config = ConfigDict(from_attributes=True)

class CartItemCreate(CartItemBase):
    pass

class CartItem(CartItemBase):
    id: int
    created_at: datetime

# Order Schemas
class OrderBase(BaseModel):
    customer_name: str
    phone_number: str
    delivery_address: str
    items: List[Dict[str, Any]]
    total_amount: float
    currency: str = "USD"
    payment_method: str = "khqr"
    notes: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)

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
    khqr_md5: Optional[str] = None
    payment_status: str = "pending"
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('status', 'payment_status', mode='before')
    @classmethod
    def set_default_status(cls, v):
        return v or "pending"

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

# Admin User Schemas
class AdminUserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "admin"

    model_config = ConfigDict(from_attributes=True)

class AdminUserCreate(AdminUserBase):
    password: str = Field(..., min_length=6)

class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

class AdminUserLogin(BaseModel):
    email: EmailStr
    password: str

class AdminUser(AdminUserBase):
    id: int
    is_active: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Admin Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    admin: AdminUser

class TokenData(BaseModel):
    email: Optional[str] = None

# Dashboard Stats
class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_products: int
    pending_orders: int
    completed_orders: int
    today_orders: int
    today_revenue: float

# Order Stats
class OrderStats(BaseModel):
    date: str
    orders: int
    revenue: float