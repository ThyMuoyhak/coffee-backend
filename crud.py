# crud.py
from sqlalchemy import func, select, update, delete, and_
from databases import Database
from models import CoffeeProduct, CartItem, Order, AdminUser
import schemas
import uuid
from datetime import datetime, date, timedelta
from fastapi import HTTPException, status
from typing import Optional, List
import hashlib
import jwt

# ========== PASSWORD HASHING ==========
SALT = "brewhaven-coffee-shop-salt"

def get_password_hash(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password by hashing and comparing"""
    return get_password_hash(plain_password) == hashed_password

# Secret key for JWT
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ========== ASYNC CRUD OPERATIONS ==========

# Admin CRUD
async def get_admin_by_email(db: Database, email: str) -> Optional[dict]:
    query = select(AdminUser).where(AdminUser.email == email)
    result = await db.fetch_one(query)
    return dict(result) if result else None

async def authenticate_admin(db: Database, email: str, password: str) -> Optional[dict]:
    """Authenticate admin user"""
    try:
        admin = await get_admin_by_email(db, email)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not admin.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account is inactive"
            )
        
        hashed_password = admin.get('hashed_password', '')
        if not hashed_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )
        
        if verify_password(password, hashed_password):
            admin_dict = dict(admin)
            admin_dict.pop('hashed_password', None)
            return admin_dict
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

async def create_admin_user(db: Database, admin: schemas.AdminCreate) -> dict:
    """Create admin user"""
    existing_admin = await get_admin_by_email(db, admin.email)
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin with this email already exists")
    
    try:
        hashed_password = get_password_hash(admin.password)
        
        query = AdminUser.__table__.insert().values(
            email=admin.email,
            hashed_password=hashed_password,
            full_name=admin.full_name,
            role=admin.role,
            is_active=True,
            created_at=datetime.utcnow()
        )
        admin_id = await db.execute(query)
        
        query = select(AdminUser).where(AdminUser.id == admin_id)
        result = await db.fetch_one(query)
        
        if result:
            admin_dict = dict(result)
            admin_dict.pop('hashed_password', None)
            return admin_dict
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create admin user: {str(e)}"
        )

async def get_admin_users(db: Database, skip: int = 0, limit: int = 100) -> List[dict]:
    query = select(AdminUser).offset(skip).limit(limit)
    results = await db.fetch_all(query)
    admin_list = []
    for admin in results:
        admin_dict = dict(admin)
        admin_dict.pop('hashed_password', None)
        admin_list.append(admin_dict)
    return admin_list

async def get_admin_user(db: Database, admin_id: int) -> Optional[dict]:
    query = select(AdminUser).where(AdminUser.id == admin_id)
    result = await db.fetch_one(query)
    if result:
        admin_dict = dict(result)
        admin_dict.pop('hashed_password', None)
        return admin_dict
    return None

async def update_admin_user(db: Database, admin_id: int, admin_update: schemas.AdminUserUpdate) -> Optional[dict]:
    admin = await get_admin_user(db, admin_id)
    if not admin:
        return None
    
    update_data = admin_update.dict(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    query = update(AdminUser).where(AdminUser.id == admin_id).values(**update_data)
    await db.execute(query)
    
    return await get_admin_user(db, admin_id)

async def delete_admin_user(db: Database, admin_id: int) -> bool:
    query = delete(AdminUser).where(AdminUser.id == admin_id)
    result = await db.execute(query)
    return result > 0

async def update_admin_last_login(db: Database, admin_id: int):
    query = update(AdminUser).where(AdminUser.id == admin_id).values(last_login=datetime.utcnow())
    await db.execute(query)

# ========== PRODUCT CRUD ==========
async def get_products(db: Database, skip: int = 0, limit: int = 100) -> List[dict]:
    query = select(CoffeeProduct).where(CoffeeProduct.is_available == True).offset(skip).limit(limit)
    results = await db.fetch_all(query)
    return [dict(product) for product in results]

async def get_product(db: Database, product_id: int) -> Optional[dict]:
    query = select(CoffeeProduct).where(CoffeeProduct.id == product_id)
    result = await db.fetch_one(query)
    return dict(result) if result else None

async def create_product(db: Database, product: schemas.CoffeeProductCreate) -> dict:
    query = CoffeeProduct.__table__.insert().values(**product.dict())
    product_id = await db.execute(query)
    
    query = select(CoffeeProduct).where(CoffeeProduct.id == product_id)
    result = await db.fetch_one(query)
    return dict(result) if result else None

async def update_product(db: Database, product_id: int, product_update: schemas.CoffeeProductUpdate) -> Optional[dict]:
    product = await get_product(db, product_id)
    if not product:
        return None
    
    update_data = product_update.dict(exclude_unset=True)
    query = update(CoffeeProduct).where(CoffeeProduct.id == product_id).values(**update_data)
    await db.execute(query)
    
    return await get_product(db, product_id)

async def delete_product(db: Database, product_id: int) -> bool:
    query = delete(CoffeeProduct).where(CoffeeProduct.id == product_id)
    result = await db.execute(query)
    return result > 0

# ========== CART CRUD ==========
async def get_cart_items(db: Database, skip: int = 0, limit: int = 100) -> List[dict]:
    query = select(CartItem).offset(skip).limit(limit)
    results = await db.fetch_all(query)
    return [dict(item) for item in results]

async def create_cart_item(db: Database, cart_item: schemas.CartItemCreate) -> dict:
    query = CartItem.__table__.insert().values(**cart_item.dict())
    cart_item_id = await db.execute(query)
    
    query = select(CartItem).where(CartItem.id == cart_item_id)
    result = await db.fetch_one(query)
    return dict(result) if result else None

async def delete_cart_item(db: Database, cart_item_id: int) -> bool:
    query = delete(CartItem).where(CartItem.id == cart_item_id)
    result = await db.execute(query)
    return result > 0

async def clear_cart(db: Database) -> bool:
    query = delete(CartItem)
    result = await db.execute(query)
    return result > 0

# ========== ORDER CRUD ==========
async def get_orders(db: Database, skip: int = 0, limit: int = 100) -> List[dict]:
    query = select(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit)
    results = await db.fetch_all(query)
    
    orders_list = []
    for order in results:
        order_dict = dict(order)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        orders_list.append(order_dict)
    
    return orders_list

async def get_order_by_number(db: Database, order_number: str) -> Optional[dict]:
    query = select(Order).where(Order.order_number == order_number)
    result = await db.fetch_one(query)
    if result:
        order_dict = dict(result)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        return order_dict
    return None

async def create_order(db: Database, order: schemas.OrderCreate) -> dict:
    order_number = f"BH{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    
    order_data = order.dict()
    order_data['order_number'] = order_number
    order_data['status'] = 'pending'
    order_data['payment_status'] = 'pending'
    order_data['khqr_md5'] = None
    order_data['admin_notes'] = None
    
    if not order_data.get('notes'):
        order_data['notes'] = ''
    
    query = Order.__table__.insert().values(**order_data)
    order_id = await db.execute(query)
    
    query = select(Order).where(Order.id == order_id)
    result = await db.fetch_one(query)
    
    if result:
        order_dict = dict(result)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        return order_dict
    
    return None

async def update_order(db: Database, order_id: int, order_update: schemas.OrderUpdate) -> Optional[dict]:
    order = await get_order_by_id(db, order_id)
    if not order:
        return None
    
    update_data = order_update.dict(exclude_unset=True)
    query = update(Order).where(Order.id == order_id).values(**update_data)
    await db.execute(query)
    
    return await get_order_by_id(db, order_id)

async def get_order_by_id(db: Database, order_id: int) -> Optional[dict]:
    query = select(Order).where(Order.id == order_id)
    result = await db.fetch_one(query)
    if result:
        order_dict = dict(result)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        return order_dict
    return None

async def update_order_payment_status(db: Database, order_number: str, payment_status: str, khqr_md5: str = None) -> Optional[dict]:
    order = await get_order_by_number(db, order_number)
    if not order:
        return None
    
    update_data = {"payment_status": payment_status}
    if khqr_md5:
        update_data["khqr_md5"] = khqr_md5
    
    query = update(Order).where(Order.order_number == order_number).values(**update_data)
    await db.execute(query)
    
    return await get_order_by_number(db, order_number)

async def search_orders(db: Database, query_str: str) -> List[dict]:
    query = select(Order).where(
        (Order.order_number.ilike(f"%{query_str}%")) |
        (Order.customer_name.ilike(f"%{query_str}%")) |
        (Order.phone_number.ilike(f"%{query_str}%"))
    ).order_by(Order.created_at.desc())
    results = await db.fetch_all(query)
    
    orders_list = []
    for order in results:
        order_dict = dict(order)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        orders_list.append(order_dict)
    
    return orders_list

async def get_orders_by_status(db: Database, status: str) -> List[dict]:
    query = select(Order).where(Order.status == status).order_by(Order.created_at.desc())
    results = await db.fetch_all(query)
    
    orders_list = []
    for order in results:
        order_dict = dict(order)
        order_dict['status'] = order_dict.get('status', status)
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        orders_list.append(order_dict)
    
    return orders_list

async def get_orders_by_date_range(db: Database, start_date: date, end_date: date) -> List[dict]:
    query = select(Order).where(
        and_(
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date
        )
    ).order_by(Order.created_at.desc())
    results = await db.fetch_all(query)
    
    orders_list = []
    for order in results:
        order_dict = dict(order)
        order_dict['status'] = order_dict.get('status', 'pending')
        order_dict['payment_status'] = order_dict.get('payment_status', 'pending')
        order_dict['khqr_md5'] = order_dict.get('khqr_md5')
        order_dict['admin_notes'] = order_dict.get('admin_notes')
        order_dict['notes'] = order_dict.get('notes', '')
        order_dict['updated_at'] = order_dict.get('updated_at')
        orders_list.append(order_dict)
    
    return orders_list

# ========== DASHBOARD STATS ==========
async def get_dashboard_stats(db: Database):
    total_orders_query = select(func.count()).select_from(Order)
    total_orders = await db.fetch_val(total_orders_query) or 0
    
    total_revenue_query = select(func.sum(Order.total_amount))
    total_revenue_result = await db.fetch_val(total_revenue_query)
    total_revenue = float(total_revenue_result) if total_revenue_result else 0.0
    
    total_products_query = select(func.count()).select_from(CoffeeProduct)
    total_products = await db.fetch_val(total_products_query) or 0
    
    pending_orders_query = select(func.count()).select_from(Order).where(
        Order.status.in_(["pending", "preparing"])
    )
    pending_orders = await db.fetch_val(pending_orders_query) or 0
    
    completed_orders_query = select(func.count()).select_from(Order).where(Order.status == "completed")
    completed_orders = await db.fetch_val(completed_orders_query) or 0
    
    today = date.today()
    today_orders_query = select(func.count()).select_from(Order).where(
        func.date(Order.created_at) == today
    )
    today_orders = await db.fetch_val(today_orders_query) or 0
    
    today_revenue_query = select(func.sum(Order.total_amount)).where(
        func.date(Order.created_at) == today
    )
    today_revenue_result = await db.fetch_val(today_revenue_query)
    today_revenue = float(today_revenue_result) if today_revenue_result else 0.0
    
    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_products": total_products,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "today_orders": today_orders,
        "today_revenue": today_revenue
    }

async def get_order_stats(db: Database, days: int = 7) -> List[dict]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    stats = []
    current_date = start_date
    
    while current_date <= end_date:
        day_orders_query = select(func.count()).select_from(Order).where(
            func.date(Order.created_at) == current_date
        )
        day_orders = await db.fetch_val(day_orders_query) or 0
        
        day_revenue_query = select(func.sum(Order.total_amount)).where(
            func.date(Order.created_at) == current_date
        )
        day_revenue_result = await db.fetch_val(day_revenue_query)
        day_revenue = float(day_revenue_result) if day_revenue_result else 0.0
        
        stats.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "orders": day_orders,
            "revenue": day_revenue
        })
        
        current_date += timedelta(days=1)
    
    return stats
