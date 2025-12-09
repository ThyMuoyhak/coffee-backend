# main.py - COMPLETE WORKING VERSION
import os
import json
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import database, engine, Base
import schemas
import asyncio
import uuid
from datetime import datetime, timedelta
import time
from typing import List, Optional, Dict, Any
import traceback
import jwt
import hashlib
import bcrypt

# Simple FastAPI app with docs disabled
app = FastAPI(
    title="BrewHaven Coffee Shop API",
    description="A complete coffee shop backend with FastAPI and KHQR payment integration",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "https://frontend-coffee-backendg2.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

print("🔄 BrewHaven Coffee Shop API starting...")

# ========== CONFIGURATION ==========
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
SALT = "brewhaven-coffee-shop-salt"
security = HTTPBearer()

# Store active payment checks
active_payment_checks = {}

# ========== PASSWORD HANDLING ==========
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against either bcrypt or SHA256 hash"""
    # Check if it's a bcrypt hash (starts with $2b$)
    if hashed_password.startswith("$2b$"):
        try:
            # Convert to bytes if needed
            if isinstance(hashed_password, str):
                hashed_password = hashed_password.encode('utf-8')
            if isinstance(plain_password, str):
                plain_password = plain_password.encode('utf-8')
            
            return bcrypt.checkpw(plain_password, hashed_password)
        except Exception as e:
            print(f"❌ Bcrypt verification error: {e}")
            return False
    else:
        # Assume SHA256 with salt
        expected_hash = hashlib.sha256(f"{plain_password}{SALT}".encode()).hexdigest()
        return hashed_password == expected_hash

def hash_password(password: str) -> str:
    """Hash password using bcrypt (for new passwords)"""
    # Use bcrypt for new passwords
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def create_access_token(data: dict):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Get current admin from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Get admin and convert to dict
        query = "SELECT * FROM admin_users WHERE email = :email"
        admin_record = await database.fetch_one(query, {"email": email})
        if admin_record is None:
            raise HTTPException(status_code=401, detail="Admin not found")
        
        admin = dict(admin_record)
        
        # Convert is_active to boolean
        admin["is_active"] = bool(admin.get("is_active", 1))
        
        if not admin["is_active"]:
            raise HTTPException(status_code=403, detail="Admin account is disabled")
        
        return admin
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"❌ Token error: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))

async def get_current_super_admin(current_admin = Depends(get_current_admin)):
    """Ensure the admin is a super admin"""
    if current_admin["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_admin

# ========== DATABASE SETUP ==========
@app.on_event("startup")
async def startup():
    await database.connect()
    await ensure_default_admin()
    await create_sample_products()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

async def ensure_default_admin():
    """Ensure default admin exists with bcrypt password"""
    print("👤 Ensuring default admin exists...")
    
    # Check if admin exists
    check_query = "SELECT email, hashed_password FROM admin_users WHERE email = 'admin@gmail.com'"
    existing_admin = await database.fetch_one(check_query)
    
    if not existing_admin:
        print("👤 Creating default admin with bcrypt...")
        password = "11112222"
        hashed_password = hash_password(password)
        
        insert_query = """
        INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
        VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
        """
        
        await database.execute(
            query=insert_query,
            values={
                "email": "admin@gmail.com",
                "hashed_password": hashed_password,
                "full_name": "System Administrator",
                "role": "super_admin",
                "is_active": 1,
                "created_at": datetime.utcnow()
            }
        )
        print("✅ Default admin created with bcrypt hash")
        print(f"🔑 Hash: {hashed_password[:30]}...")
    else:
        admin = dict(existing_admin)
        print(f"✅ Admin already exists")
        print(f"🔑 Stored hash type: {'bcrypt' if admin['hashed_password'].startswith('$2b$') else 'SHA256'}")
        print(f"🔑 Hash sample: {admin['hashed_password'][:30]}...")
        
        # If it's not bcrypt, convert it
        if not admin['hashed_password'].startswith("$2b$"):
            print("🔄 Converting SHA256 hash to bcrypt...")
            password = "11112222"
            hashed_password = hash_password(password)
            
            update_query = """
            UPDATE admin_users 
            SET hashed_password = :hashed_password 
            WHERE email = 'admin@gmail.com'
            """
            await database.execute(update_query, {"hashed_password": hashed_password})
            print("✅ Converted to bcrypt hash")

async def create_sample_products():
    """Create sample products if none exist"""
    try:
        count_query = "SELECT COUNT(*) as count FROM coffee_products"
        result = await database.fetch_one(count_query)
        count = result["count"] if result else 0
        
        if count == 0:
            print("📦 Creating sample products...")
            
            sample_products = [
                {
                    "name": "Espresso",
                    "price": 3.50,
                    "image": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04",
                    "description": "Strong and concentrated coffee",
                    "category": "espresso",
                    "rating": 4.8,
                    "brew_time": "25s",
                    "is_available": 1,
                    "stock": 100
                },
                {
                    "name": "Cappuccino",
                    "price": 4.50,
                    "image": "https://images.unsplash.com/photo-1534778101976-62847782c213",
                    "description": "Espresso with steamed milk foam",
                    "category": "milk",
                    "rating": 4.7,
                    "brew_time": "3m",
                    "is_available": 1,
                    "stock": 80
                },
                {
                    "name": "Latte",
                    "price": 5.00,
                    "image": "https://images.unsplash.com/photo-1561047029-3000c68339ca",
                    "description": "Smooth espresso with steamed milk",
                    "category": "milk",
                    "rating": 4.9,
                    "brew_time": "4m",
                    "is_available": 1,
                    "stock": 90
                }
            ]
            
            for product in sample_products:
                insert_query = """
                INSERT INTO coffee_products (name, price, image, description, category, rating, brew_time, is_available, stock, created_at)
                VALUES (:name, :price, :image, :description, :category, :rating, :brew_time, :is_available, :stock, :created_at)
                """
                await database.execute(
                    query=insert_query,
                    values={**product, "created_at": datetime.utcnow()}
                )
            
            print(f"✅ Created {len(sample_products)} sample products")
        else:
            print(f"✅ {count} products already exist")
            
    except Exception as e:
        print(f"❌ Error creating sample products: {e}")

# Background task for demo payments
async def check_payment_status_demo(order_number: str):
    """Demo version that simulates payment confirmation"""
    print(f"⏳ Simulating payment processing for order {order_number}...")
    
    active_payment_checks[order_number] = {
        'start_time': time.time(),
        'status': 'processing'
    }
    
    await asyncio.sleep(3)
    
    # Update payment status in database
    try:
        update_query = """
        UPDATE orders 
        SET payment_status = 'paid', khqr_md5 = :khqr_md5 
        WHERE order_number = :order_number
        """
        await database.execute(
            query=update_query,
            values={"order_number": order_number, "khqr_md5": "demo_md5_hash"}
        )
        active_payment_checks[order_number]['status'] = 'paid'
        print(f"✅ Demo payment confirmed for order {order_number}")
    except Exception as e:
        active_payment_checks[order_number]['status'] = 'failed'
        print(f"❌ Failed to update payment status for order {order_number}: {e}")

# ========== HELPER FUNCTIONS ==========
def parse_order_items(items_data: Any) -> List[Dict[str, Any]]:
    """Parse order items from JSON string or list"""
    if isinstance(items_data, str):
        try:
            items = json.loads(items_data)
            if isinstance(items, list):
                return items
            elif isinstance(items, dict):
                return [items]
        except:
            return []
    elif isinstance(items_data, list):
        return items_data
    return []

def format_order_for_response(order_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Format order dictionary for API response"""
    # Parse items from JSON string
    items = parse_order_items(order_dict.get('items', '[]'))
    
    # Ensure items have required fields
    formatted_items = []
    for item in items:
        formatted_item = {
            "product_id": item.get("product_id", item.get("id", 0)),
            "product_name": item.get("product_name", item.get("name", "")),
            "quantity": item.get("quantity", 1),
            "price": float(item.get("price", 0.0)),
            "sugar_level": item.get("sugar_level", item.get("sugarLevel", "regular"))
        }
        formatted_items.append(formatted_item)
    
    # Return formatted order
    return {
        "id": order_dict.get("id", 0),
        "order_number": order_dict.get("order_number", ""),
        "customer_name": order_dict.get("customer_name", ""),
        "phone_number": order_dict.get("phone_number", ""),
        "delivery_address": order_dict.get("delivery_address", ""),
        "items": formatted_items,
        "total_amount": float(order_dict.get("total_amount", 0.0)),
        "currency": order_dict.get("currency", "USD"),
        "status": order_dict.get("status", "pending"),
        "payment_status": order_dict.get("payment_status", "pending"),
        "payment_method": order_dict.get("payment_method", "khqr"),
        "khqr_md5": order_dict.get("khqr_md5"),
        "notes": order_dict.get("notes", ""),
        "admin_notes": order_dict.get("admin_notes", ""),
        "created_at": order_dict.get("created_at"),
        "updated_at": order_dict.get("updated_at")
    }

# ========== AUTHENTICATION ENDPOINTS ==========
@app.post("/api/v1/admin/login", response_model=schemas.Token)
async def admin_login(login_data: schemas.AdminLogin):
    """Admin login endpoint - SUPPORTS BCRYPT"""
    try:
        print(f"🔐 Login attempt for: {login_data.email}")
        
        # Direct database query
        query = "SELECT id, email, hashed_password, role, is_active, full_name FROM admin_users WHERE email = :email"
        admin_record = await database.fetch_one(query, {"email": login_data.email})
        
        if not admin_record:
            print(f"❌ Admin not found: {login_data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        admin = dict(admin_record)
        print(f"✅ Admin found: {admin['email']}")
        print(f"🔑 Hash type: {'bcrypt' if admin['hashed_password'].startswith('$2b$') else 'SHA256'}")
        
        # Verify password with bcrypt support
        if not verify_password(login_data.password, admin["hashed_password"]):
            print(f"❌ Password verification failed!")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Password verified!")
        
        # Update last login
        await database.execute(
            "UPDATE admin_users SET last_login = :now WHERE id = :id",
            {"now": datetime.utcnow(), "id": admin["id"]}
        )
        
        # Create token
        access_token = create_access_token(
            data={"sub": admin["email"], "role": admin["role"]}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "full_name": admin.get("full_name", "Administrator"),
                "role": admin["role"],
                "is_active": bool(admin.get("is_active", 1))
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/api/v1/auth/login", response_model=schemas.Token)
async def auth_login(login_data: schemas.AdminLogin):
    """Alternative auth login endpoint"""
    return await admin_login(login_data)

@app.get("/api/v1/auth/me", response_model=schemas.AdminUser)
async def get_current_admin_info(current_admin = Depends(get_current_admin)):
    """Get current admin information"""
    return {
        "id": current_admin["id"],
        "email": current_admin["email"],
        "full_name": current_admin["full_name"],
        "role": current_admin["role"],
        "is_active": current_admin["is_active"],
        "created_at": current_admin["created_at"]
    }

# ========== PUBLIC PRODUCT ENDPOINTS ==========
@app.get("/api/v1/products/", response_model=List[schemas.CoffeeProduct])
async def read_products(skip: int = 0, limit: int = 100):
    """Get all products"""
    try:
        query = "SELECT * FROM coffee_products WHERE is_available = 1 ORDER BY id LIMIT :limit OFFSET :skip"
        products = await database.fetch_all(query, {"limit": limit, "skip": skip})
        return [dict(product) for product in products]
    except Exception as e:
        print(f"❌ Error getting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products/{product_id}", response_model=schemas.CoffeeProduct)
async def read_product(product_id: int):
    """Get single product by ID"""
    try:
        query = "SELECT * FROM coffee_products WHERE id = :id"
        product = await database.fetch_one(query, {"id": product_id})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return dict(product)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/categories/")
async def get_categories():
    """Get all product categories"""
    try:
        query = "SELECT DISTINCT category FROM coffee_products WHERE category IS NOT NULL AND category != ''"
        results = await database.fetch_all(query)
        categories = [row["category"] for row in results]
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products/category/{category}")
async def get_products_by_category(category: str):
    """Get products by category"""
    try:
        query = "SELECT * FROM coffee_products WHERE category = :category AND is_available = 1"
        products = await database.fetch_all(query, {"category": category})
        return [dict(product) for product in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== ADMIN PRODUCT MANAGEMENT ==========
@app.get("/api/v1/admin/products/", response_model=List[schemas.CoffeeProduct])
async def admin_read_products(
    skip: int = 0,
    limit: int = 100,
    current_admin = Depends(get_current_admin)
):
    """Get all products (Admin only)"""
    try:
        query = "SELECT * FROM coffee_products ORDER BY id LIMIT :limit OFFSET :skip"
        products = await database.fetch_all(query, {"limit": limit, "skip": skip})
        return [dict(product) for product in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/products/", response_model=schemas.CoffeeProduct)
async def admin_create_product(
    product: schemas.CoffeeProductCreate,
    current_admin = Depends(get_current_admin)
):
    """Create product (Admin only)"""
    try:
        query = """
        INSERT INTO coffee_products (name, price, image, description, category, rating, brew_time, is_available, stock, created_at)
        VALUES (:name, :price, :image, :description, :category, :rating, :brew_time, :is_available, :stock, :created_at)
        """
        product_id = await database.execute(
            query=query,
            values={
                **product.dict(),
                "is_available": 1 if product.is_available else 0,
                "created_at": datetime.utcnow()
            }
        )
        
        # Return created product
        query = "SELECT * FROM coffee_products WHERE id = :id"
        created_product = await database.fetch_one(query, {"id": product_id})
        return dict(created_product)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/admin/products/{product_id}", response_model=schemas.CoffeeProduct)
async def admin_update_product(
    product_id: int,
    product_update: schemas.CoffeeProductUpdate,
    current_admin = Depends(get_current_admin)
):
    """Update product (Admin only)"""
    try:
        # Check if product exists
        check_query = "SELECT id FROM coffee_products WHERE id = :id"
        existing = await database.fetch_one(check_query, {"id": product_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Build update query
        update_data = product_update.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        # Convert boolean to integer for SQLite
        if "is_available" in update_data:
            update_data["is_available"] = 1 if update_data["is_available"] else 0
        
        set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
        query = f"UPDATE coffee_products SET {set_clause} WHERE id = :id"
        
        await database.execute(query=query, values={"id": product_id, **update_data})
        
        # Return updated product
        query = "SELECT * FROM coffee_products WHERE id = :id"
        updated_product = await database.fetch_one(query, {"id": product_id})
        return dict(updated_product)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/admin/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    current_admin = Depends(get_current_admin)
):
    """Delete product (Admin only)"""
    try:
        query = "DELETE FROM coffee_products WHERE id = :id"
        result = await database.execute(query, {"id": product_id})
        if result == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== ADMIN ORDER MANAGEMENT ==========
@app.get("/api/v1/admin/orders", response_model=List[schemas.Order])
async def get_admin_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_admin = Depends(get_current_admin)
):
    """Get all orders (Admin only)"""
    try:
        if status:
            query = "SELECT * FROM orders WHERE status = :status ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
            params = {"status": status, "limit": limit, "skip": skip}
        else:
            query = "SELECT * FROM orders ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
            params = {"limit": limit, "skip": skip}
        
        orders = await database.fetch_all(query, params)
        
        # Format orders for response
        formatted_orders = []
        for order in orders:
            formatted_order = format_order_for_response(dict(order))
            formatted_orders.append(formatted_order)
        
        return formatted_orders
    except Exception as e:
        print(f"❌ Error getting orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/{order_id}", response_model=schemas.Order)
async def get_admin_order_by_id(
    order_id: int,
    current_admin = Depends(get_current_admin)
):
    """Get specific order by ID (Admin only)"""
    try:
        query = "SELECT * FROM orders WHERE id = :order_id"
        order = await database.fetch_one(query, {"order_id": order_id})
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        formatted_order = format_order_for_response(dict(order))
        return formatted_order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/admin/orders/{order_number}/status")
async def update_order_status_admin(
    order_number: str,
    status_update: schemas.OrderStatusUpdate,
    current_admin = Depends(get_current_admin)
):
    """Update order status (Admin only)"""
    try:
        # Check if order exists
        check_query = "SELECT id FROM orders WHERE order_number = :order_number"
        order = await database.fetch_one(check_query, {"order_number": order_number})
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Update status
        update_query = "UPDATE orders SET status = :status, updated_at = :updated_at WHERE order_number = :order_number"
        await database.execute(
            query=update_query,
            values={
                "status": status_update.status,
                "updated_at": datetime.utcnow(),
                "order_number": order_number
            }
        )
        
        # Return updated order
        query = "SELECT * FROM orders WHERE order_number = :order_number"
        updated_order = await database.fetch_one(query, {"order_number": order_number})
        formatted_order = format_order_for_response(dict(updated_order))
        return formatted_order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== ADMIN DASHBOARD ==========
@app.get("/api/v1/admin/dashboard/stats")
async def get_admin_dashboard_stats(current_admin = Depends(get_current_admin)):
    """Get dashboard stats for admin panel"""
    try:
        # Total orders
        total_orders_query = "SELECT COUNT(*) as count FROM orders"
        total_orders_result = await database.fetch_one(total_orders_query)
        total_orders = total_orders_result["count"] if total_orders_result else 0
        
        # Total revenue
        total_revenue_query = "SELECT SUM(total_amount) as total FROM orders WHERE payment_status = 'paid'"
        total_revenue_result = await database.fetch_one(total_revenue_query)
        total_revenue = float(total_revenue_result["total"]) if total_revenue_result and total_revenue_result["total"] else 0.0
        
        # Total products
        total_products_query = "SELECT COUNT(*) as count FROM coffee_products"
        total_products_result = await database.fetch_one(total_products_query)
        total_products = total_products_result["count"] if total_products_result else 0
        
        # Pending orders
        pending_orders_query = "SELECT COUNT(*) as count FROM orders WHERE status IN ('pending', 'preparing')"
        pending_orders_result = await database.fetch_one(pending_orders_query)
        pending_orders = pending_orders_result["count"] if pending_orders_result else 0
        
        # Completed orders
        completed_orders_query = "SELECT COUNT(*) as count FROM orders WHERE status = 'completed'"
        completed_orders_result = await database.fetch_one(completed_orders_query)
        completed_orders = completed_orders_result["count"] if completed_orders_result else 0
        
        # Today's orders
        today = datetime.now().date()
        today_orders_query = "SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = :today"
        today_orders_result = await database.fetch_one(today_orders_query, {"today": today})
        today_orders = today_orders_result["count"] if today_orders_result else 0
        
        # Today's revenue
        today_revenue_query = "SELECT SUM(total_amount) as total FROM orders WHERE DATE(created_at) = :today AND payment_status = 'paid'"
        today_revenue_result = await database.fetch_one(today_revenue_query, {"today": today})
        today_revenue = float(today_revenue_result["total"]) if today_revenue_result and today_revenue_result["total"] else 0.0
        
        return {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_products": total_products,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "today_orders": today_orders,
            "today_revenue": today_revenue
        }
    except Exception as e:
        print(f"❌ Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/me", response_model=schemas.AdminUser)
async def get_admin_me(current_admin = Depends(get_current_admin)):
    """Get current admin info for admin panel"""
    return current_admin

# ========== PUBLIC ORDERS ENDPOINTS ==========
@app.get("/api/v1/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100):
    """Get all orders (public)"""
    try:
        query = "SELECT * FROM orders ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
        orders = await database.fetch_all(query, {"limit": limit, "skip": skip})
        
        formatted_orders = []
        for order in orders:
            formatted_order = format_order_for_response(dict(order))
            formatted_orders.append(formatted_order)
        return formatted_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/orders/", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks):
    """Create new order"""
    try:
        print(f"📦 Creating order for: {order.customer_name}")
        
        # Generate order number
        order_number = f"BH{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        
        # Convert items to JSON string
        items_json = json.dumps([item.dict() for item in order.items])
        
        # Insert order
        query = """
        INSERT INTO orders (
            order_number, customer_name, phone_number, delivery_address, items,
            total_amount, currency, status, payment_status, payment_method,
            notes, created_at
        ) VALUES (
            :order_number, :customer_name, :phone_number, :delivery_address, :items,
            :total_amount, :currency, :status, :payment_status, :payment_method,
            :notes, :created_at
        )
        """
        
        order_id = await database.execute(
            query=query,
            values={
                "order_number": order_number,
                "customer_name": order.customer_name,
                "phone_number": order.phone_number,
                "delivery_address": order.delivery_address or "",
                "items": items_json,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "status": "pending",
                "payment_status": "pending",
                "payment_method": "khqr",
                "notes": order.notes or "",
                "created_at": datetime.utcnow()
            }
        )
        
        # Get created order
        query = "SELECT * FROM orders WHERE id = :id"
        db_order = await database.fetch_one(query, {"id": order_id})
        
        print(f"✅ Order created: {order_number}")
        
        # Start background payment check
        background_tasks.add_task(check_payment_status_demo, order_number)
        
        formatted_order = format_order_for_response(dict(db_order))
        return formatted_order
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.get("/api/v1/orders/{order_number}", response_model=schemas.Order)
async def read_order(order_number: str):
    """Get order by order number"""
    try:
        query = "SELECT * FROM orders WHERE order_number = :order_number"
        db_order = await database.fetch_one(query, {"order_number": order_number})
        if db_order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        
        formatted_order = format_order_for_response(dict(db_order))
        return formatted_order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== KHQR PAYMENT ENDPOINTS ==========
@app.post("/api/v1/khqr/generate", response_model=schemas.KHQRResponse)
async def generate_khqr_payment(khqr_request: schemas.KHQRRequest, background_tasks: BackgroundTasks):
    """Generate demo KHQR for deployment"""
    print(f"🔄 Generating DEMO KHQR for order: {khqr_request.order_number}")
    
    demo_md5 = f"demo_{khqr_request.order_number}_{int(datetime.now().timestamp())}"
    
    background_tasks.add_task(check_payment_status_demo, khqr_request.order_number)
    
    return schemas.KHQRResponse(
        qr_data=f"DEMO_QR_FOR_ORDER_{khqr_request.order_number}",
        md5_hash=demo_md5,
        deeplink=f"https://example.com/demo/{khqr_request.order_number}",
        qr_image=None
    )

@app.get("/api/v1/khqr/status/{order_number}", response_model=schemas.PaymentStatusResponse)
async def get_payment_status(order_number: str):
    """Get payment status for order"""
    try:
        query = "SELECT * FROM orders WHERE order_number = :order_number"
        db_order = await database.fetch_one(query, {"order_number": order_number})
        if db_order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order_dict = dict(db_order)
        current_status = order_dict.get('payment_status', 'pending')
        
        active_check = active_payment_checks.get(order_number)
        if active_check:
            current_status = active_check['status']
        
        transaction_data = {
            "order_number": order_number,
            "amount": order_dict.get('total_amount', 0),
            "currency": order_dict.get('currency', 'USD'),
            "timestamp": datetime.now().isoformat(),
            "demo": True,
            "mode": "demo"
        }
        
        return schemas.PaymentStatusResponse(
            order_number=order_number,
            payment_status=current_status,
            transaction_data=transaction_data
        )
        
    except Exception as e:
        print(f"❌ Payment status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment status check failed: {str(e)}")

# ========== ROOT & HEALTH ENDPOINTS ==========
@app.get("/")
async def read_root():
    return {
        "message": "Welcome to BrewHaven Coffee Shop API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "products": "/api/v1/products/",
            "orders": "/api/v1/orders/",
            "khqr": "/api/v1/khqr/generate",
            "admin_login": "/api/v1/admin/login",
            "admin_dashboard": "/api/v1/admin/dashboard/stats",
            "admin_orders": "/api/v1/admin/orders",
            "admin_products": "/api/v1/admin/products/"
        }
    }

@app.get("/health")
async def health_check():
    try:
        await database.execute("SELECT 1")
        db_status = "connected"
    except:
        db_status = "disconnected"
        
    return {
        "status": "healthy", 
        "database": db_status, 
        "timestamp": datetime.now().isoformat(),
        "endpoints_available": True
    }

# ========== DEBUG & MAINTENANCE ENDPOINTS ==========
@app.get("/fix-admin")
async def fix_admin():
    """Fix admin password with bcrypt"""
    try:
        password = "11112222"
        hashed_password = hash_password(password)
        
        # Delete existing
        await database.execute("DELETE FROM admin_users WHERE email = 'admin@gmail.com'")
        
        # Create new with bcrypt
        insert_query = """
        INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
        VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
        """
        
        await database.execute(
            query=insert_query,
            values={
                "email": "admin@gmail.com",
                "hashed_password": hashed_password,
                "full_name": "System Administrator",
                "role": "super_admin",
                "is_active": 1,
                "created_at": datetime.utcnow()
            }
        )
        
        return {
            "success": True,
            "message": "Admin fixed with bcrypt",
            "email": "admin@gmail.com",
            "password": "11112222",
            "hash_type": "bcrypt",
            "hash_sample": hashed_password[:50] + "..."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/check-hash")
async def check_hash():
    """Check current hash type"""
    try:
        query = "SELECT email, hashed_password, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = 'admin@gmail.com'"
        admin = await database.fetch_one(query)
        
        if not admin:
            return {"exists": False}
        
        admin_dict = dict(admin)
        password = "11112222"
        
        # Test both hash types
        bcrypt_result = verify_password(password, admin_dict["hashed_password"])
        sha256_hash = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
        sha256_result = admin_dict["hashed_password"] == sha256_hash
        
        return {
            "exists": True,
            "email": admin_dict["email"],
            "stored_hash": admin_dict["hashed_password"][:50] + "...",
            "hash_length": admin_dict["hash_len"],
            "hash_type": "bcrypt" if admin_dict["hashed_password"].startswith("$2b$") else "unknown",
            "bcrypt_matches": bcrypt_result,
            "sha256_matches": sha256_result,
            "test_password": password
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global error: {exc}")
    traceback.print_exc()
    
    if isinstance(exc, HTTPException):
        raise exc
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error occurred: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting BrewHaven Coffee Shop API with bcrypt support...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
