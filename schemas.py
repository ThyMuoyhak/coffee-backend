# schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, date

# ========== AUTHENTICATION SCHEMAS ==========
class AdminLogin(BaseModel):
    email: str
    password: str

class AdminUserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    admin: Optional[Dict[str, Any]] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# ========== ADMIN MANAGEMENT SCHEMAS ==========
class AdminBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "admin"

# Both are the same, for compatibility
class AdminUserCreate(AdminBase):
    password: str

class AdminCreate(AdminBase):
    password: str

class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class AdminStatusUpdate(BaseModel):
    is_active: bool

class AdminResponse(AdminBase):
    id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminUser(AdminResponse):
    pass

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

class OrderStatusUpdate(BaseModel):
    status: str

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
        from_attributes = True

# ========== DASHBOARD SCHEMAS ==========
class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_products: int
    pending_orders: int
    completed_orders: int
    today_orders: int
    today_revenue: float

class OrderStats(BaseModel):
    date: str
    orders: int
    revenue: float

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

# ========== ANALYTICS SCHEMAS ==========
class SalesAnalytics(BaseModel):
    period: str
    date: Optional[str] = None
    week: Optional[str] = None
    month: Optional[str] = None
    order_count: int
    total_revenue: float

class TopProduct(BaseModel):
    name: str
    category: str
    sold_count: int
    revenue: float
