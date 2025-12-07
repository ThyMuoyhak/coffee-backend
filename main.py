# main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import database, engine, Base, get_db
from models import CoffeeProduct, CartItem, Order, AdminUser
import schemas
import crud
from admin_api import router as admin_router
import asyncio
import uuid
from datetime import datetime, timedelta
import json
import time
from typing import List
import traceback
import os

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
            import hashlib
            salt = "brewhaven-coffee-shop-salt"
            password = "11112222"
            hashed_password = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
            
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
    # ... rest of your product creation code ...
    
@app.get("/reset-admin")
async def reset_admin_endpoint():
    """Endpoint to reset admin password (for debugging)"""
    try:
        import hashlib
        
        # Delete existing admin
        await database.execute("DELETE FROM admin_users WHERE email = 'admin@gmail.com'")
        
        # Create new admin with SHA256
        salt = "brewhaven-coffee-shop-salt"
        password = "11112222"
        hashed_password = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        
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

# ========== PUBLIC ENDPOINTS ==========
@app.get("/api/v1/products/", response_model=List[schemas.CoffeeProduct])
async def read_products(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    return await crud.get_products(db, skip=skip, limit=limit)

@app.get("/api/v1/products/{product_id}", response_model=schemas.CoffeeProduct)
async def read_product(product_id: int, db = Depends(get_db)):
    db_product = await crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@app.post("/api/v1/products/", response_model=schemas.CoffeeProduct)
async def create_product(product: schemas.CoffeeProductCreate, db = Depends(get_db)):
    return await crud.create_product(db=db, product=product)

@app.get("/api/v1/categories/")
async def get_categories(db = Depends(get_db)):
    products = await crud.get_products(db)
    categories = list(set(product.category for product in products if product.category))
    return {"categories": categories}

@app.get("/api/v1/products/category/{category}")
async def get_products_by_category(category: str, db = Depends(get_db)):
    products = await crud.get_products(db)
    filtered_products = [product for product in products if product.category == category]
    return filtered_products

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
            "admin_docs": "/api/v1/admin/docs"
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