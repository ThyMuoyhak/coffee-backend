# main.py
import warnings
warnings.filterwarnings("ignore")

import os
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import List, Optional
import traceback
import jwt
import hashlib
import asyncio
import uuid
import time

# Import database
from database import database

# Environment variable to control docs
SHOW_DOCS = os.getenv("SHOW_DOCS", "false").lower() == "true"

if SHOW_DOCS:
    app = FastAPI(
        title="BrewHaven Coffee Shop API",
        description="A complete coffee shop backend with FastAPI",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
else:
    app = FastAPI(
        title="BrewHaven Coffee Shop API",
        description="A complete coffee shop backend with FastAPI",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("🔄 BrewHaven Coffee Shop API starting...")

# Store active payment checks
active_payment_checks = {}

# ========== JWT AUTHENTICATION SETUP ==========
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
SALT = "brewhaven-coffee-shop-salt"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Startup event
@app.on_event("startup")
async def startup():
    await database.connect()
    await create_sample_data()

# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

async def create_sample_data():
    """Create sample data and ensure default admin exists"""
    print("\n🔄 Setting up sample data...")
    
    # Create tables if they don't exist
    try:
        # Admin users table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                is_active BOOLEAN DEFAULT 1,
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Coffee products table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS coffee_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                image TEXT,
                description TEXT,
                category TEXT,
                rating REAL DEFAULT 0.0,
                brew_time TEXT,
                is_available BOOLEAN DEFAULT 1,
                stock INTEGER DEFAULT 100,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Orders table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                delivery_address TEXT,
                items TEXT,
                total_amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending',
                payment_method TEXT DEFAULT 'khqr',
                khqr_md5 TEXT,
                notes TEXT,
                admin_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cart items table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT,
                quantity INTEGER,
                price REAL,
                sugar_level TEXT DEFAULT 'regular',
                image TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✅ Database tables created/verified")
        
        # Check if admin exists
        check_query = "SELECT email FROM admin_users WHERE email = 'admin@gmail.com'"
        existing_admin = await database.fetch_one(check_query)
        
        if not existing_admin:
            print("👤 Creating new admin...")
            
            password = "11112222"
            hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
            
            await database.execute("""
                INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
                VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
            """, {
                "email": "admin@gmail.com",
                "hashed_password": hashed_password,
                "full_name": "System Administrator",
                "role": "super_admin",
                "is_active": 1,
                "created_at": datetime.utcnow()
            })
            
            print("✅ Default admin created!")
            print(f"   Email: admin@gmail.com")
            print(f"   Password: 11112222")
        else:
            print("✅ Admin already exists")
            
        # Check if products exist
        product_count = await database.fetch_one("SELECT COUNT(*) as count FROM coffee_products")
        if product_count['count'] == 0:
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
                }
            ]
            
            for product in sample_products:
                await database.execute("""
                    INSERT INTO coffee_products (name, price, image, description, category, rating, brew_time, is_available, stock, created_at)
                    VALUES (:name, :price, :image, :description, :category, :rating, :brew_time, :is_available, :stock, :created_at)
                """, {**product, "created_at": datetime.utcnow()})
            
            print(f"✅ Created {len(sample_products)} sample products")
            
    except Exception as e:
        print(f"❌ Error setting up data: {e}")
        traceback.print_exc()

# Background task for demo payments
async def check_payment_status_demo(order_number: str):
    """Demo version that simulates payment confirmation"""
    print(f"⏳ Simulating payment processing for order {order_number}...")
    
    active_payment_checks[order_number] = {
        'start_time': time.time(),
        'status': 'processing'
    }
    
    await asyncio.sleep(3)
    
    # Update order payment status
    try:
        await database.execute(
            "UPDATE orders SET payment_status = 'paid', khqr_md5 = :md5 WHERE order_number = :order_number",
            {"md5": "demo_md5_hash", "order_number": order_number}
        )
        active_payment_checks[order_number]['status'] = 'paid'
        print(f"✅ Demo payment confirmed for order {order_number}")
    except:
        active_payment_checks[order_number]['status'] = 'failed'
        print(f"❌ Failed to update payment status for order {order_number}")

# ========== AUTHENTICATION ENDPOINTS ==========

class AdminLoginRequest:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

@app.post("/api/v1/admin/login")
async def admin_login(request: dict):
    """Admin login endpoint"""
    try:
        email = request.get("email")
        password = request.get("password")
        
        print(f"🔐 ADMIN LOGIN ATTEMPT:")
        print(f"   Email: {email}")
        print(f"   Password: {'*' * len(password) if password else 'None'}")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        # Check if admin exists
        query = "SELECT id, email, hashed_password, role, full_name FROM admin_users WHERE email = :email"
        admin_record = await database.fetch_one(query, {"email": email})
        
        if not admin_record:
            print(f"❌ Admin not found: {email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        admin = dict(admin_record)
        print(f"✅ Admin found: {admin['email']}")
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
        print(f"🔑 Hash comparison:")
        print(f"   Stored:   {admin['hashed_password'][:20]}...")
        print(f"   Expected: {expected_hash[:20]}...")
        
        # Verify password
        if admin["hashed_password"] != expected_hash:
            print(f"❌ Password verification FAILED!")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Password verification SUCCESS!")
        
        # Update last login
        await database.execute(
            "UPDATE admin_users SET last_login = :now WHERE id = :id",
            {"now": datetime.utcnow(), "id": admin["id"]}
        )
        
        # Create token
        access_token = create_access_token(
            data={"sub": admin["email"], "role": admin["role"]}
        )
        
        print(f"✅ Login successful for: {admin['email']}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "full_name": admin.get("full_name", "Administrator"),
                "role": admin["role"],
                "is_active": True
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# ========== PUBLIC PRODUCT ENDPOINTS ==========

@app.get("/api/v1/products/")
async def read_products(skip: int = 0, limit: int = 100):
    try:
        query = "SELECT * FROM coffee_products WHERE is_available = 1 LIMIT :limit OFFSET :skip"
        products = await database.fetch_all(query, {"skip": skip, "limit": limit})
        print(f"✅ Returning {len(products)} products")
        return [dict(product) for product in products]
    except Exception as e:
        print(f"❌ Error getting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products/{product_id}")
async def read_product(product_id: int):
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

# ========== ORDER ENDPOINTS ==========

class OrderItem:
    def __init__(self, product_id: int, product_name: str, quantity: int, price: float, sugar_level: str = "regular"):
        self.product_id = product_id
        self.product_name = product_name
        self.quantity = quantity
        self.price = price
        self.sugar_level = sugar_level

class OrderCreateRequest:
    def __init__(self, customer_name: str, phone_number: str, items: List[dict], 
                 total_amount: float, delivery_address: str = None, notes: str = None):
        self.customer_name = customer_name
        self.phone_number = phone_number
        self.items = items
        self.total_amount = total_amount
        self.delivery_address = delivery_address
        self.notes = notes

@app.post("/api/v1/orders/")
async def create_order(request: dict, background_tasks: BackgroundTasks):
    try:
        print(f"📦 Creating order for: {request.get('customer_name')}")
        
        # Generate order number
        order_number = f"BH{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        
        # Create order data
        order_data = {
            "order_number": order_number,
            "customer_name": request.get("customer_name"),
            "phone_number": request.get("phone_number"),
            "delivery_address": request.get("delivery_address"),
            "items": json.dumps(request.get("items", [])),
            "total_amount": request.get("total_amount", 0),
            "currency": "USD",
            "status": "pending",
            "payment_status": "pending",
            "payment_method": "khqr",
            "khqr_md5": None,
            "notes": request.get("notes", ""),
            "admin_notes": None,
            "created_at": datetime.utcnow()
        }
        
        # Insert order
        query = """
            INSERT INTO orders (order_number, customer_name, phone_number, delivery_address, 
                               items, total_amount, currency, status, payment_status, 
                               payment_method, khqr_md5, notes, admin_notes, created_at)
            VALUES (:order_number, :customer_name, :phone_number, :delivery_address, 
                    :items, :total_amount, :currency, :status, :payment_status, 
                    :payment_method, :khqr_md5, :notes, :admin_notes, :created_at)
        """
        
        await database.execute(query, order_data)
        
        # Get the created order
        order_query = "SELECT * FROM orders WHERE order_number = :order_number"
        db_order = await database.fetch_one(order_query, {"order_number": order_number})
        
        if not db_order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        order_dict = dict(db_order)
        
        # Parse items from JSON
        if isinstance(order_dict.get('items'), str):
            try:
                order_dict['items'] = json.loads(order_dict['items'])
            except:
                order_dict['items'] = []
        
        print(f"✅ Order created: {order_number}")
        
        # Start background payment simulation
        background_tasks.add_task(check_payment_status_demo, order_number)
        
        return order_dict
        
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.get("/api/v1/orders/{order_number}")
async def read_order(order_number: str):
    try:
        query = "SELECT * FROM orders WHERE order_number = :order_number"
        db_order = await database.fetch_one(query, {"order_number": order_number})
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order_dict = dict(db_order)
        
        # Parse items from JSON
        if isinstance(order_dict.get('items'), str):
            try:
                order_dict['items'] = json.loads(order_dict['items'])
            except:
                order_dict['items'] = []
        
        return order_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== ADMIN DASHBOARD ENDPOINTS ==========

@app.get("/api/v1/admin/dashboard/stats")
async def get_dashboard_stats():
    try:
        # Get total orders
        total_orders_result = await database.fetch_one("SELECT COUNT(*) as count FROM orders")
        total_orders = total_orders_result['count'] if total_orders_result else 0
        
        # Get total revenue
        total_revenue_result = await database.fetch_one("SELECT SUM(total_amount) as total FROM orders")
        total_revenue = float(total_revenue_result['total']) if total_revenue_result and total_revenue_result['total'] else 0.0
        
        # Get total products
        total_products_result = await database.fetch_one("SELECT COUNT(*) as count FROM coffee_products")
        total_products = total_products_result['count'] if total_products_result else 0
        
        # Get pending orders
        pending_orders_result = await database.fetch_one(
            "SELECT COUNT(*) as count FROM orders WHERE status IN ('pending', 'preparing')"
        )
        pending_orders = pending_orders_result['count'] if pending_orders_result else 0
        
        # Get completed orders
        completed_orders_result = await database.fetch_one(
            "SELECT COUNT(*) as count FROM orders WHERE status = 'completed'"
        )
        completed_orders = completed_orders_result['count'] if completed_orders_result else 0
        
        # Get today's orders
        today = datetime.now().date()
        today_orders_result = await database.fetch_one(
            "SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = :today",
            {"today": today}
        )
        today_orders = today_orders_result['count'] if today_orders_result else 0
        
        # Get today's revenue
        today_revenue_result = await database.fetch_one(
            "SELECT SUM(total_amount) as total FROM orders WHERE DATE(created_at) = :today",
            {"today": today}
        )
        today_revenue = float(today_revenue_result['total']) if today_revenue_result and today_revenue_result['total'] else 0.0
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/")
async def get_admin_orders(skip: int = 0, limit: int = 100, status: str = None):
    try:
        if status:
            query = "SELECT * FROM orders WHERE status = :status ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
            orders = await database.fetch_all(query, {"status": status, "skip": skip, "limit": limit})
        else:
            query = "SELECT * FROM orders ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
            orders = await database.fetch_all(query, {"skip": skip, "limit": limit})
        
        # Parse items from JSON for each order
        orders_list = []
        for order in orders:
            order_dict = dict(order)
            if isinstance(order_dict.get('items'), str):
                try:
                    order_dict['items'] = json.loads(order_dict['items'])
                except:
                    order_dict['items'] = []
            orders_list.append(order_dict)
        
        return orders_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== DEBUG & HEALTH ENDPOINTS ==========

@app.get("/test-admin")
async def test_admin():
    """Test endpoint to check admin credentials"""
    try:
        test_email = "admin@gmail.com"
        test_password = "11112222"
        
        print(f"\n🔐 TESTING ADMIN CREDENTIALS:")
        print(f"  Email: {test_email}")
        print(f"  Password: {test_password}")
        
        # Check if admin exists
        query = "SELECT id, email, hashed_password, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = :email"
        admin_record = await database.fetch_one(query, {"email": test_email})
        
        if not admin_record:
            return {
                "success": False,
                "message": "❌ Admin not found in database",
                "email": test_email,
                "action": "Try /reset-admin to create admin"
            }
        
        admin = dict(admin_record)
        db_hash = admin["hashed_password"]
        hash_len = admin["hash_len"]
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(f"{test_password}{SALT}".encode()).hexdigest()
        
        print(f"\n🔑 HASH COMPARISON:")
        print(f"  Database hash ({hash_len} chars): {db_hash[:50]}...")
        print(f"  Expected hash ({len(expected_hash)} chars): {expected_hash[:50]}...")
        print(f"  Hashes match: {db_hash == expected_hash}")
        
        return {
            "success": True,
            "admin_exists": True,
            "admin_id": admin["id"],
            "email": test_email,
            "db_hash_length": hash_len,
            "db_hash_sample": db_hash[:50] + "..." if db_hash else "None",
            "expected_hash_sample": expected_hash[:50] + "...",
            "hashes_match": db_hash == expected_hash,
            "login_endpoint": "POST /api/v1/admin/login",
            "test_password_used": test_password,
            "note": "If hashes don't match, use /reset-admin endpoint"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/reset-admin")
async def reset_admin_endpoint():
    """Endpoint to reset admin password"""
    try:
        # Delete existing admin
        delete_count = await database.execute("DELETE FROM admin_users WHERE email = 'admin@gmail.com'")
        print(f"🧹 Deleted {delete_count} admin users")
        
        # Create new admin
        password = "11112222"
        hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
        
        print(f"\n🔑 CREATING NEW ADMIN:")
        print(f"  Email: admin@gmail.com")
        print(f"  Password: {password}")
        print(f"  Hash ({len(hashed_password)} chars): {hashed_password[:50]}...")
        
        await database.execute("""
            INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
            VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
        """, {
            "email": "admin@gmail.com",
            "hashed_password": hashed_password,
            "full_name": "System Administrator",
            "role": "super_admin",
            "is_active": 1,
            "created_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "✅ Admin reset successfully",
            "email": "admin@gmail.com",
            "password": "11112222",
            "hash_length": len(hashed_password),
            "hash_sample": hashed_password[:50] + "...",
            "login_endpoint": "POST /api/v1/admin/login",
            "test_endpoint": "/test-admin"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    try:
        await database.execute("SELECT 1")
        db_status = "connected"
    except:
        db_status = "disconnected"
        
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
        "endpoints_available": True,
        "version": "1.0.0"
    }

@app.get("/")
async def read_root():
    return {
        "message": "Welcome to BrewHaven Coffee Shop API",
        "version": "1.0.0",
        "status": "running",
        "docs": "Documentation is disabled in production",
        "endpoints": {
            "health": "/health",
            "products": "/api/v1/products/",
            "admin_login": "POST /api/v1/admin/login",
            "create_order": "POST /api/v1/orders/",
            "admin_dashboard": "/api/v1/admin/dashboard/stats",
            "admin_orders": "/api/v1/admin/orders/",
            "test_admin": "/test-admin",
            "reset_admin": "/reset-admin"
        },
        "note": "Use /test-admin to check admin credentials, /reset-admin to reset if needed"
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global error: {exc}")
    traceback.print_exc()
    
    if isinstance(exc, HTTPException):
        raise exc
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting BrewHaven Coffee Shop API...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
