# main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import database, engine, Base, get_db
import schemas
import crud
from admin_api import router as admin_router
import asyncio
import uuid
from datetime import datetime, timedelta
import json
import time
from typing import List, Optional
import traceback
import os
import jwt
import hashlib

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BrewHaven Coffee Shop API",
    description="A complete coffee shop backend with FastAPI and KHQR payment integration",
    version="1.0.0"
)

# CORS middleware - UPDATED for specific frontend URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "https://frontend-coffee-backendg2.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# IMPORTANT: Include admin router WITHOUT additional prefix since it already has /api/v1/admin
app.include_router(admin_router)

# KHQR Configuration - Simplified for deployment
KHQR_AVAILABLE = False
khqr = None
print("🔄 Running in DEMO mode - KHQR payments will be simulated")

# Store active payment checks (in production, use Redis or database)
active_payment_checks = {}

# ========== JWT AUTHENTICATION SETUP ==========
security = HTTPBearer()
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # Same as in crud.py
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
SALT = "brewhaven-coffee-shop-salt"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against SHA256 hash"""
    return hashlib.sha256(f"{plain_password}{SALT}".encode()).hexdigest() == hashed_password

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
        
        # Verify admin exists in database
        admin = await crud.get_admin_by_email(database, email)
        if admin is None:
            raise HTTPException(status_code=401, detail="Admin not found")
        
        # Check if admin is active
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

# Create sample data and default admin
async def create_sample_data():
    """Create sample data and ensure default admin exists"""
    print("\n🔄 Setting up sample data...")
    
    # ========== CREATE DEFAULT ADMIN ==========
    print("👤 Checking/creating default admin...")
    
    try:
        # First, check if admin exists with wrong hash (60 chars = bcrypt)
        check_query = "SELECT email, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = 'admin@gmail.com'"
        existing_admin = await database.fetch_one(check_query)
        
        if existing_admin:
            hash_len = existing_admin['hash_len']
            print(f"📊 Existing admin found with hash length: {hash_len}")
            
            if hash_len == 60:  # Old bcrypt hash
                print("⚠️ Found old bcrypt hash, deleting...")
                delete_query = "DELETE FROM admin_users WHERE email = 'admin@gmail.com'"
                await database.execute(delete_query)
                print("🧹 Old admin deleted")
                existing_admin = None
        
        # Create admin if doesn't exist or was deleted
        if not existing_admin:
            print("👤 Creating new admin with SHA256 hash...")
            
            # Hash the password manually with SHA256
            password = "11112222"
            hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
            
            print(f"🔑 Generated hash: {hashed_password[:50]}...")
            print(f"📏 Hash length: {len(hashed_password)} characters")
            
            # Insert admin directly
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
            print("✅ Admin already exists with correct hash")
            
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        import traceback
        traceback.print_exc()
    
    # ========== CREATE SAMPLE PRODUCTS ==========
    print("📦 Checking/creating sample products...")
    try:
        # Check if products already exist
        product_count = await database.fetch_val("SELECT COUNT(*) FROM coffee_products")
        if product_count == 0:
            sample_products = [
                {
                    "name": "Espresso",
                    "price": 3.50,
                    "image": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04",
                    "description": "Strong and concentrated coffee",
                    "category": "espresso",
                    "rating": 4.8,
                    "brew_time": "25s",
                    "is_available": True,
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
                    "is_available": True,
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
                    "is_available": True,
                    "stock": 90
                }
            ]
            
            for product in sample_products:
                await database.execute(
                    query="""
                    INSERT INTO coffee_products (name, price, image, description, category, rating, brew_time, is_available, stock, created_at)
                    VALUES (:name, :price, :image, :description, :category, :rating, :brew_time, :is_available, :stock, :created_at)
                    """,
                    values={**product, "created_at": datetime.utcnow()}
                )
            print(f"✅ Created {len(sample_products)} sample products")
        else:
            print(f"✅ {product_count} products already exist")
    except Exception as e:
        print(f"❌ Error creating sample products: {e}")
    
@app.get("/reset-admin")
async def reset_admin_endpoint():
    """Endpoint to reset admin password (for debugging)"""
    try:
        import hashlib
        
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
            "hash_length": len(hashed_password)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
# Background task to check payment status (demo version)
async def check_payment_status_demo(order_number: str):
    """Demo version that simulates payment confirmation"""
    print(f"⏳ Simulating payment processing for order {order_number}...")
    
    # Store the start time for this order
    active_payment_checks[order_number] = {
        'start_time': time.time(),
        'status': 'processing'
    }
    
    # Simulate payment processing time (5-15 seconds)
    processing_time = 10  # seconds
    await asyncio.sleep(processing_time)
    
    # Update order status to paid (for demo)
    db_order = await crud.update_order_payment_status(database, order_number, "paid", "demo_md5_hash")
    if db_order:
        active_payment_checks[order_number]['status'] = 'paid'
        print(f"✅ Demo payment confirmed for order {order_number}")
    else:
        active_payment_checks[order_number]['status'] = 'failed'
        print(f"❌ Failed to update payment status for order {order_number}")

# ========== AUTHENTICATION ENDPOINTS ==========
@app.post("/api/v1/auth/login")
async def admin_login(login_data: schemas.AdminLogin):
    """Admin login endpoint"""
    try:
        # Use crud's authenticate_admin function
        admin = await crud.authenticate_admin(database, login_data.email, login_data.password)
        
        if not admin:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Update last login
        await crud.update_admin_last_login(database, admin["id"])
        
        # Create access token
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
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/api/v1/auth/me")
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
    """Admin logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}


# ========== CART ENDPOINTS ==========
@app.get("/api/v1/cart/", response_model=List[schemas.CartItem])
async def read_cart_items(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    return await crud.get_cart_items(db, skip=skip, limit=limit)

@app.post("/api/v1/cart/", response_model=schemas.CartItem)
async def add_to_cart(cart_item: schemas.CartItemCreate, db = Depends(get_db)):
    return await crud.create_cart_item(db=db, cart_item=cart_item)

@app.delete("/api/v1/cart/{cart_item_id}")
async def remove_from_cart(cart_item_id: int, db = Depends(get_db)):
    success = await crud.delete_cart_item(db=db, cart_item_id=cart_item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Item removed from cart"}

@app.delete("/api/v1/cart/")
async def clear_cart(db = Depends(get_db)):
    success = await crud.clear_cart(db=db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear cart")
    return {"message": "Cart cleared successfully"}

# ========== PUBLIC ORDERS ENDPOINTS ==========
@app.get("/api/v1/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    return await crud.get_orders(db, skip=skip, limit=limit)

@app.post("/api/v1/orders/", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate, background_tasks: BackgroundTasks, db = Depends(get_db)):
    try:
        print(f"Creating order for: {order.customer_name}")
        print(f"Order items: {len(order.items)} items")
        print(f"Total amount: ${order.total_amount}")
        
        # Create the order
        db_order = await crud.create_order(db=db, order=order)
        
        if not db_order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        print(f"Order created successfully: {db_order.get('order_number')}")
        
        # Start background payment checking
        background_tasks.add_task(check_payment_status_demo, db_order['order_number'])
        
        return db_order
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.get("/api/v1/orders/{order_number}", response_model=schemas.Order)
async def read_order(order_number: str, db = Depends(get_db)):
    db_order = await crud.get_order_by_number(db, order_number=order_number)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

# ========== KHQR PAYMENT ENDPOINTS ==========
@app.post("/api/v1/khqr/generate", response_model=schemas.KHQRResponse)
async def generate_khqr_payment(khqr_request: schemas.KHQRRequest, background_tasks: BackgroundTasks):
    """Generate demo KHQR for deployment"""
    print(f"🔄 Generating DEMO KHQR for order: {khqr_request.order_number}")
    
    demo_md5 = f"demo_{khqr_request.order_number}_{int(datetime.now().timestamp())}"
    
    # Start demo payment processing
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
        
        print(f"Checking payment status for order: {order_number}")
        
        # Check if we have active payment checking for this order
        active_check = active_payment_checks.get(order_number)
        current_status = db_order.get('payment_status', 'pending')
        
        # If we have active checking, use that status
        if active_check:
            current_status = active_check['status']
            print(f"Active payment check status: {current_status}")
        
        # Return status
        transaction_data = {
            "order_number": order_number,
            "amount": db_order.get('total_amount', 0),
            "currency": db_order.get('currency', 'USD'),
            "timestamp": datetime.now().isoformat(),
            "demo": True,
            "mode": "demo"
        }
        
        response = schemas.PaymentStatusResponse(
            order_number=order_number,
            payment_status=current_status,
            transaction_data=transaction_data
        )
        
        print(f"✅ Payment status response: {current_status}")
        return response
        
    except Exception as e:
        print(f"❌ Payment status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment status check failed: {str(e)}")

# ========== PROTECTED PRODUCT ENDPOINTS (Admin Only) ==========
@app.put("/api/v1/admin/products/{product_id}", response_model=schemas.CoffeeProduct)
async def update_product(
    product_id: int, 
    product: schemas.CoffeeProductUpdate,
    current_admin = Depends(get_current_admin)
):
    """Update product (Admin only)"""
    db_product = await crud.update_product(database, product_id=product_id, product_update=product)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@app.delete("/api/v1/admin/products/{product_id}")
async def delete_product(
    product_id: int,
    current_admin = Depends(get_current_admin)
):
    """Delete product (Admin only)"""
    success = await crud.delete_product(database, product_id=product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

@app.post("/api/v1/admin/products/bulk", response_model=List[schemas.CoffeeProduct])
async def create_bulk_products(
    products: List[schemas.CoffeeProductCreate],
    current_admin = Depends(get_current_admin)
):
    """Create multiple products at once (Admin only)"""
    created_products = []
    for product in products:
        db_product = await crud.create_product(database, product=product)
        created_products.append(db_product)
    return created_products

# ========== PROTECTED ORDER ENDPOINTS (Admin Only) ==========
@app.get("/api/v1/admin/orders/", response_model=List[schemas.Order])
async def read_all_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_admin = Depends(get_current_admin)
):
    """Get all orders with filters (Admin only)"""
    if status:
        orders = await crud.get_orders_by_status(database, status)
        return orders[skip:skip+limit]
    
    return await crud.get_orders(database, skip=skip, limit=limit)

@app.patch("/api/v1/admin/orders/{order_number}/status")
async def update_order_status(
    order_number: str,
    status_update: schemas.OrderStatusUpdate,
    current_admin = Depends(get_current_admin)
):
    """Update order status (Admin only)"""
    try:
        # First get the order to ensure it exists
        db_order = await crud.get_order_by_number(database, order_number=order_number)
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Create an OrderUpdate object
        order_update = schemas.OrderUpdate(status=status_update.status)
        
        # Update the order
        updated_order = await crud.update_order(database, db_order["id"], order_update)
        
        if not updated_order:
            raise HTTPException(status_code=500, detail="Failed to update order")
        
        return updated_order
        
    except Exception as e:
        print(f"❌ Error updating order status: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/stats/dashboard")
async def get_order_dashboard_stats(
    current_admin = Depends(get_current_admin)
):
    """Get order statistics for admin dashboard"""
    try:
        # Use crud function for dashboard stats
        stats = await crud.get_dashboard_stats(database)
        return stats
        
    except Exception as e:
        print(f"❌ Dashboard stats error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/search/{query}")
async def search_orders(
    query: str,
    current_admin = Depends(get_current_admin)
):
    """Search orders (Admin only)"""
    try:
        results = await crud.search_orders(database, query)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/orders/status/{status}")
async def get_orders_by_status(
    status: str,
    current_admin = Depends(get_current_admin)
):
    """Get orders by status (Admin only)"""
    try:
        results = await crud.get_orders_by_status(database, status)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== PROTECTED ANALYTICS ENDPOINTS ==========
@app.get("/api/v1/admin/analytics/sales")
async def get_sales_analytics(
    days: Optional[int] = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_admin = Depends(get_current_admin)
):
    """Get sales analytics data (Admin only)"""
    try:
        if start_date and end_date:
            from datetime import date as date_type
            start = date_type.fromisoformat(start_date)
            end = date_type.fromisoformat(end_date)
            results = await crud.get_orders_by_date_range(database, start, end)
            return results
        else:
            # Use days parameter
            results = await crud.get_order_stats(database, days)
            return results
        
    except Exception as e:
        print(f"❌ Analytics error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/analytics/top-products")
async def get_top_products(
    limit: int = 10,
    current_admin = Depends(get_current_admin)
):
    """Get top selling products (Admin only)"""
    try:
        query = """
        SELECT 
            p.name,
            p.category,
            COUNT(oi.product_id) as sold_count,
            SUM(oi.quantity * p.price) as revenue
        FROM order_items oi
        JOIN coffee_products p ON oi.product_id = p.id
        GROUP BY p.id, p.name, p.category
        ORDER BY sold_count DESC
        LIMIT :limit
        """
        
        results = await database.fetch_all(query=query, values={"limit": limit})
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== SUPER ADMIN ONLY ENDPOINTS ==========
@app.get("/api/v1/admin/admins/", response_model=List[schemas.AdminResponse])
async def get_all_admins(
    current_admin = Depends(get_current_super_admin)
):
    """Get all admin users (Super Admin only)"""
    try:
        admins = await crud.get_admin_users(database)
        return admins
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/admins/", response_model=schemas.AdminResponse)
async def create_admin(
    admin_data: schemas.AdminCreate,
    current_admin = Depends(get_current_super_admin)
):
    """Create new admin user (Super Admin only)"""
    try:
        new_admin = await crud.create_admin_user(database, admin_data)
        if not new_admin:
            raise HTTPException(status_code=500, detail="Failed to create admin")
        return new_admin
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/admin/admins/{admin_id}/status")
async def update_admin_status(
    admin_id: int,
    status_data: schemas.AdminStatusUpdate,
    current_admin = Depends(get_current_super_admin)
):
    """Update admin active status (Super Admin only)"""
    try:
        # Cannot disable self
        if admin_id == current_admin["id"]:
            raise HTTPException(status_code=400, detail="Cannot change your own status")
        
        update_query = """
        UPDATE admin_users 
        SET is_active = :is_active,
            updated_at = :updated_at
        WHERE id = :id
        RETURNING *
        """
        
        updated_admin = await database.fetch_one(
            query=update_query,
            values={
                "id": admin_id,
                "is_active": status_data.is_active,
                "updated_at": datetime.utcnow()
            }
        )
        
        if not updated_admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # Remove password from response
        admin_dict = dict(updated_admin)
        admin_dict.pop('hashed_password', None)
        return admin_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/admins/{admin_id}", response_model=schemas.AdminResponse)
async def get_admin_by_id(
    admin_id: int,
    current_admin = Depends(get_current_super_admin)
):
    """Get admin by ID (Super Admin only)"""
    try:
        admin = await crud.get_admin_user(database, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        return admin
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== PAYMENT MANAGEMENT ENDPOINTS ==========
@app.post("/api/v1/payments/{order_number}/simulate-paid")
async def simulate_payment_paid(order_number: str):
    """Endpoint to simulate payment for testing"""
    try:
        db_order = await crud.update_order_payment_status(database, order_number, "paid", "simulated_md5")
        if db_order:
            # Update active check status
            if order_number in active_payment_checks:
                active_payment_checks[order_number]['status'] = 'paid'
            
            return {
                "message": "Payment simulated successfully",
                "order_number": order_number,
                "status": "paid"
            }
        else:
            raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate payment: {str(e)}")

@app.get("/api/v1/payments/active")
async def get_active_payments():
    """Get all active payment checks (for monitoring)"""
    return {
        "active_payments": active_payment_checks,
        "total_active": len(active_payment_checks)
    }

# ========== ROOT ENDPOINTS ==========
@app.get("/")
async def read_root():
    return {
        "message": "Welcome to BrewHaven Coffee Shop API",
        "version": "1.0.0",
        "khqr_available": KHQR_AVAILABLE,
        "mode": "DEMO",
        "active_payments": len(active_payment_checks),
        "frontend_urls": [
            "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
            "https://frontend-coffee-backendg2.vercel.app"
        ],
        "endpoints": {
            "docs": "/docs",
            "products": "/api/v1/products/",
            "cart": "/api/v1/cart/",
            "orders": "/api/v1/orders/",
            "khqr": "/api/v1/khqr/generate",
            "payments": "/api/v1/payments/active",
            "admin": "/api/v1/admin/",
            "admin_docs": "/api/v1/admin/docs",
            "auth_login": "/api/v1/auth/login",
            "auth_me": "/api/v1/auth/me",
            "protected_products": "/api/v1/admin/products/{id}",
            "protected_orders": "/api/v1/admin/orders/",
            "analytics": "/api/v1/admin/analytics/{type}",
            "admin_management": "/api/v1/admin/admins/ (super_admin only)"
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
        "khqr_available": KHQR_AVAILABLE,
        "mode": "DEMO",
        "active_payments": len(active_payment_checks),
        "timestamp": datetime.now().isoformat(),
        "allowed_origins": [
            "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
            "https://frontend-coffee-backendg2.vercel.app"
        ]
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
    uvicorn.run(app, host="0.0.0.0", port=8080)
