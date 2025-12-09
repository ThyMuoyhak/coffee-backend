# main.py
import warnings
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")

import os
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import database, engine, Base
import schemas
import crud
import asyncio
import uuid
from datetime import datetime, timedelta
import time
from typing import List, Optional
import traceback
import jwt
import hashlib

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
    allow_origins=[
        "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "https://frontend-coffee-backendg2.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"  # Allow all for testing
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

print("🔄 BrewHaven Coffee Shop API starting...")

# Store active payment checks
active_payment_checks = {}

# ========== JWT AUTHENTICATION SETUP ==========
security = HTTPBearer()
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

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Get current admin from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        admin = await crud.get_admin_by_email(database, email)
        if admin is None:
            raise HTTPException(status_code=401, detail="Admin not found")
        
        if not admin.get("is_active", True):
            raise HTTPException(status_code=403, detail="Admin account is disabled")
        
        return admin
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

async def get_current_super_admin(current_admin = Depends(get_current_admin)):
    """Ensure the admin is a super admin"""
    if current_admin["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_admin

# Startup event
@app.on_event("startup")
async def startup():
    await database.connect()
    await create_sample_data()

# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Create sample data
async def create_sample_data():
    """Create sample data and ensure default admin exists"""
    print("\n🔄 Setting up sample data...")
    
    # Create default admin
    print("👤 Checking/creating default admin...")
    
    try:
        check_query = "SELECT email, hashed_password FROM admin_users WHERE email = 'admin@gmail.com'"
        existing_admin = await database.fetch_one(check_query)
        
        if not existing_admin:
            print("👤 Creating new admin with SHA256 hash...")
            
            password = "11112222"
            hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
            
            print(f"🔑 Generated hash: {hashed_password[:50]}...")
            
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
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            
            print("✅ Default admin created successfully!")
            print(f"   Email: admin@gmail.com")
            print(f"   Password: 11112222")
        else:
            print(f"✅ Admin already exists")
            print(f"   Hash stored: {existing_admin['hashed_password'][:50]}...")
            
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
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
    
    db_order = await crud.update_order_payment_status(database, order_number, "paid", "demo_md5_hash")
    if db_order:
        active_payment_checks[order_number]['status'] = 'paid'
        print(f"✅ Demo payment confirmed for order {order_number}")
    else:
        active_payment_checks[order_number]['status'] = 'failed'
        print(f"❌ Failed to update payment status for order {order_number}")

# ========== FIXED AUTHENTICATION ENDPOINTS ==========

# Endpoint 1: /api/v1/admin/login (for admin panel)
@app.post("/api/v1/admin/login", response_model=schemas.Token)
async def admin_login_admin_panel(login_data: schemas.AdminLogin):
    """Admin login endpoint for admin panel"""
    try:
        print(f"🔐 Admin panel login attempt for: {login_data.email}")
        
        admin = await crud.authenticate_admin(database, login_data.email, login_data.password)
        
        if not admin:
            print(f"❌ Authentication failed for: {login_data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Admin authenticated: {admin['email']}")
        
        await crud.update_admin_last_login(database, admin["id"])
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin["email"], "role": admin["role"]},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "full_name": admin["full_name"],
                "role": admin["role"]
            }
        }
        
    except HTTPException as e:
        print(f"❌ HTTP Exception during login: {e.detail}")
        raise e
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Endpoint 2: /api/v1/auth/login (original endpoint)
@app.post("/api/v1/auth/login", response_model=schemas.Token)
async def admin_login(login_data: schemas.AdminLogin):
    """Admin login endpoint (original)"""
    try:
        print(f"🔐 Auth login attempt for: {login_data.email}")
        
        admin = await crud.authenticate_admin(database, login_data.email, login_data.password)
        
        if not admin:
            print(f"❌ Authentication failed for: {login_data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Admin authenticated: {admin['email']}")
        
        await crud.update_admin_last_login(database, admin["id"])
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin["email"], "role": admin["role"]},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "full_name": admin["full_name"],
                "role": admin["role"]
            }
        }
        
    except HTTPException as e:
        print(f"❌ HTTP Exception during login: {e.detail}")
        raise e
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

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

@app.post("/api/v1/auth/logout")
async def admin_logout(current_admin = Depends(get_current_admin)):
    """Admin logout endpoint"""
    return {"message": "Successfully logged out"}

# ========== PUBLIC PRODUCT ENDPOINTS ==========
@app.get("/api/v1/products/", response_model=List[schemas.CoffeeProduct])
async def read_products(skip: int = 0, limit: int = 100):
    try:
        products = await crud.get_products(database, skip=skip, limit=limit)
        print(f"✅ Returning {len(products)} products")
        return products
    except Exception as e:
        print(f"❌ Error getting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products/{product_id}", response_model=schemas.CoffeeProduct)
async def read_product(product_id: int):
    db_product = await crud.get_product(database, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@app.post("/api/v1/products/", response_model=schemas.CoffeeProduct)
async def create_product(product: schemas.CoffeeProductCreate):
    return await crud.create_product(database, product=product)

@app.get("/api/v1/categories/")
async def get_categories():
    products = await crud.get_products(database)
    categories = list(set(product.get("category", "") for product in products if product.get("category")))
    categories = [cat for cat in categories if cat]  # Remove empty strings
    return {"categories": categories}

@app.get("/api/v1/products/category/{category}")
async def get_products_by_category(category: str):
    products = await crud.get_products(database)
    filtered_products = [product for product in products if product.get("category") == category]
    return filtered_products

# ========== CART ENDPOINTS ==========
@app.get("/api/v1/cart/", response_model=List[schemas.CartItem])
async def read_cart_items(skip: int = 0, limit: int = 100):
    return await crud.get_cart_items(database, skip=skip, limit=limit)

@app.post("/api/v1/cart/", response_model=schemas.CartItem)
async def add_to_cart(cart_item: schemas.CartItemCreate):
    return await crud.create_cart_item(database, cart_item=cart_item)

@app.delete("/api/v1/cart/{cart_item_id}")
async def remove_from_cart(cart_item_id: int):
    success = await crud.delete_cart_item(database, cart_item_id=cart_item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Item removed from cart"}

@app.delete("/api/v1/cart/")
async def clear_cart():
    success = await crud.clear_cart(database)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear cart")
    return {"message": "Cart cleared successfully"}

# ========== PUBLIC ORDERS ENDPOINTS ==========
@app.get("/api/v1/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100):
    return await crud.get_orders(database, skip=skip, limit=limit)

@app.post("/api/v1/orders/", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks):
    try:
        print(f"📦 Creating order for: {order.customer_name}")
        
        db_order = await crud.create_order(database, order=order)
        
        if not db_order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        print(f"✅ Order created: {db_order.get('order_number')}")
        
        background_tasks.add_task(check_payment_status_demo, db_order['order_number'])
        
        return db_order
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.get("/api/v1/orders/{order_number}", response_model=schemas.Order)
async def read_order(order_number: str):
    db_order = await crud.get_order_by_number(database, order_number=order_number)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

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
    try:
        db_order = await crud.get_order_by_number(database, order_number=order_number)
        if db_order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        
        current_status = db_order.get('payment_status', 'pending')
        
        active_check = active_payment_checks.get(order_number)
        if active_check:
            current_status = active_check['status']
        
        transaction_data = {
            "order_number": order_number,
            "amount": db_order.get('total_amount', 0),
            "currency": db_order.get('currency', 'USD'),
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

# ========== ADMIN MANAGEMENT ENDPOINTS ==========
@app.get("/api/v1/admin/me", response_model=schemas.AdminUser)
async def get_admin_me(current_admin = Depends(get_current_admin)):
    """Get current admin info for admin panel"""
    return current_admin

@app.get("/api/v1/admin/dashboard/stats")
async def get_admin_dashboard_stats(current_admin = Depends(get_current_admin)):
    """Get dashboard stats for admin panel"""
    try:
        stats = await crud.get_dashboard_stats(database)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/", response_model=List[schemas.Order])
async def get_admin_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_admin = Depends(get_current_admin)
):
    """Get all orders (Admin only)"""
    if status:
        orders = await crud.get_orders_by_status(database, status)
        return orders[skip:skip+limit]
    
    return await crud.get_orders(database, skip=skip, limit=limit)

# ========== ROOT ENDPOINTS ==========
@app.get("/")
async def read_root():
    return {
        "message": "Welcome to BrewHaven Coffee Shop API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "products": "/api/v1/products/",
            "cart": "/api/v1/cart/",
            "orders": "/api/v1/orders/",
            "khqr": "/api/v1/khqr/generate",
            "auth_login": "/api/v1/auth/login",
            "admin_login": "/api/v1/admin/login",
            "admin_me": "/api/v1/admin/me",
            "admin_dashboard": "/api/v1/admin/dashboard/stats"
        }
    }

@app.get("/health")
async def health_check():
    db_status = "connected"
    try:
        await database.execute("SELECT 1")
    except:
        db_status = "disconnected"
        
    return {
        "status": "healthy", 
        "database": db_status, 
        "timestamp": datetime.now().isoformat(),
        "endpoints_available": True
    }

# Test endpoint to verify admin credentials
@app.get("/test-admin")
async def test_admin():
    """Test endpoint to check admin credentials"""
    try:
        # Test the default admin credentials
        test_email = "admin@gmail.com"
        test_password = "11112222"
        
        print(f"🔐 Testing admin credentials for: {test_email}")
        
        # Manually check the hash
        expected_hash = hashlib.sha256(f"{test_password}{SALT}".encode()).hexdigest()
        print(f"🔑 Expected hash: {expected_hash[:50]}...")
        
        # Check database
        query = "SELECT email, hashed_password, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = :email"
        admin = await database.fetch_one(query, {"email": test_email})
        
        if not admin:
            return {
                "success": False,
                "message": "Admin not found in database",
                "email": test_email
            }
        
        db_hash = admin["hashed_password"]
        hash_len = admin["hash_len"]
        
        return {
            "success": True,
            "email": test_email,
            "db_hash_length": hash_len,
            "db_hash_sample": db_hash[:50] + "..." if db_hash else "None",
            "expected_hash_sample": expected_hash[:50] + "...",
            "hashes_match": db_hash == expected_hash
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Debug endpoint to reset admin
@app.get("/reset-admin")
async def reset_admin_endpoint():
    """Endpoint to reset admin password (for debugging)"""
    try:
        # Delete existing admin
        await database.execute("DELETE FROM admin_users WHERE email = 'admin@gmail.com'")
        
        # Create new admin with SHA256
        password = "11112222"
        hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
        
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
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        )
        
        return {
            "success": True,
            "message": "Admin reset successfully",
            "email": "admin@gmail.com",
            "password": "11112222",
            "hash_length": len(hashed_password),
            "hash_sample": hashed_password[:50] + "..."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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
        content={"detail": f"Internal server error occurred: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting BrewHaven Coffee Shop API...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
