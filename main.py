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

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BrewHaven Coffee Shop API",
    description="A complete coffee shop backend with FastAPI and KHQR payment integration",
    version="1.0.0"
)

# CORS middleware - SPECIFICALLY ALLOW YOUR FRONTEND DOMAIN
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-coffee-backendg2.vercel.app",
        "https://frontend-admin-coffee-backendg2-ce1.vercel.app",  # For local development
        "http://127.0.0.1:3000",  # For local development
        "https://frontend-coffee-backendg2-git-main-username.vercel.app",  # Vercel preview URLs
        "https://frontend-coffee-backendg2-*.vercel.app"  # All preview deployments
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include admin router
app.include_router(admin_router)

# KHQR Configuration - Simplified for deployment
KHQR_AVAILABLE = False
khqr = None
print("🔄 Running in DEMO mode - KHQR payments will be simulated")

# Store active payment checks (in production, use Redis or database)
active_payment_checks = {}

# Store session cart (in production, use Redis or database)
user_carts = {}

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
    # Check if default admin exists
    default_admin = await crud.get_admin_by_email(database, "admin@gmail.com")
    if not default_admin:
        # Create default admin
        admin_data = schemas.AdminUserCreate(
            email="admin@gmail.com",
            password="11112222",
            full_name="System Administrator",
            role="super_admin"
        )
        await crud.create_admin_user(database, admin_data)
        print("✅ Default admin created: admin@gmail.com / 11112222")
    
    # Check if products already exist
    total_products = await database.fetch_val("SELECT COUNT(*) FROM coffee_products")
    if total_products == 0:
        sample_products = [
            {
                "name": "Mondulkiri Arabica",
                "price": 4.50,
                "image": "https://images.unsplash.com/photo-1587734195503-904fca47e0e9?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Single origin from Cambodian highlands with rich flavor notes",
                "category": "Hot Coffee",
                "rating": 4.8,
                "brew_time": "4-5 min",
                "is_available": True,
                "stock": 100
            },
            {
                "name": "Phnom Penh Cold Brew",
                "price": 5.25,
                "image": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Smooth 12-hour cold extraction with chocolate undertones",
                "category": "Cold Brew",
                "rating": 4.9,
                "brew_time": "12 hours",
                "is_available": True,
                "stock": 85
            },
            {
                "name": "Siem Reap Robusta",
                "price": 3.75,
                "image": "https://images.unsplash.com/photo-1572442388796-11668a67e53d?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Strong and bold traditional Cambodian blend",
                "category": "Hot Coffee",
                "rating": 4.6,
                "brew_time": "3-4 min",
                "is_available": True,
                "stock": 120
            },
            {
                "name": "Angkor Wat Espresso",
                "price": 3.50,
                "image": "https://images.unsplash.com/photo-1510707577719-ae7c9b788690?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Intense and aromatic espresso shot",
                "category": "Espresso",
                "rating": 4.7,
                "brew_time": "30 sec",
                "is_available": True,
                "stock": 90
            },
            {
                "name": "Tonle Sap Cappuccino",
                "price": 4.25,
                "image": "https://images.unsplash.com/photo-1561047029-3000c68339ca?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Creamy cappuccino with a perfect foam layer",
                "category": "Milk Coffee",
                "rating": 4.8,
                "brew_time": "5-6 min",
                "is_available": True,
                "stock": 75
            },
            {
                "name": "Kampot Iced Coffee",
                "price": 4.00,
                "image": "https://images.unsplash.com/photo-1466637574441-749b8f19452f?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Refreshing iced coffee with sweet condensed milk",
                "category": "Iced Coffee",
                "rating": 4.9,
                "brew_time": "3-4 min",
                "is_available": True,
                "stock": 110
            }
        ]
        
        for product in sample_products:
            query = CoffeeProduct.__table__.insert().values(**product)
            await database.execute(query)
        
        print("✅ Sample coffee products created!")

# Background task to check payment status (demo version)
async def check_payment_status_demo(order_number: str):
    """Demo version that simulates payment confirmation"""
    print(f"⏳ Simulating payment processing for order {order_number}...")
    
    # Store the start time for this order
    active_payment_checks[order_number] = {
        'start_time': time.time(),
        'status': 'processing',
        'last_update': datetime.now().isoformat()
    }
    
    # Simulate payment processing time (5-15 seconds)
    processing_time = 10  # seconds
    await asyncio.sleep(processing_time)
    
    # Update order status to paid (for demo)
    db_order = await crud.update_order_payment_status(database, order_number, "paid", "demo_md5_hash")
    if db_order:
        active_payment_checks[order_number]['status'] = 'paid'
        active_payment_checks[order_number]['last_update'] = datetime.now().isoformat()
        print(f"✅ Demo payment confirmed for order {order_number}")
    else:
        active_payment_checks[order_number]['status'] = 'failed'
        active_payment_checks[order_number]['last_update'] = datetime.now().isoformat()
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

# ========== SESSION CART ENDPOINTS (For Frontend) ==========
@app.get("/api/v1/cart/session/{session_id}")
async def get_session_cart(session_id: str):
    """Get cart items for a specific session (frontend user)"""
    if session_id in user_carts:
        return {
            "session_id": session_id,
            "items": user_carts[session_id],
            "total_items": len(user_carts[session_id]),
            "timestamp": datetime.now().isoformat()
        }
    return {
        "session_id": session_id,
        "items": [],
        "total_items": 0,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/cart/session/{session_id}/add")
async def add_to_session_cart(session_id: str, item: dict):
    """Add item to session cart"""
    if session_id not in user_carts:
        user_carts[session_id] = []
    
    # Check if item already exists in cart
    for cart_item in user_carts[session_id]:
        if cart_item.get('product_id') == item.get('product_id'):
            cart_item['quantity'] += item.get('quantity', 1)
            return {
                "session_id": session_id,
                "message": "Item quantity updated",
                "total_items": len(user_carts[session_id])
            }
    
    # Add new item
    item['id'] = len(user_carts[session_id]) + 1
    item['added_at'] = datetime.now().isoformat()
    user_carts[session_id].append(item)
    
    return {
        "session_id": session_id,
        "message": "Item added to cart",
        "total_items": len(user_carts[session_id])
    }

@app.delete("/api/v1/cart/session/{session_id}/item/{item_id}")
async def remove_from_session_cart(session_id: str, item_id: int):
    """Remove item from session cart"""
    if session_id in user_carts:
        user_carts[session_id] = [item for item in user_carts[session_id] if item.get('id') != item_id]
        return {
            "session_id": session_id,
            "message": "Item removed from cart",
            "total_items": len(user_carts[session_id])
        }
    return {"message": "Session not found"}

@app.delete("/api/v1/cart/session/{session_id}/clear")
async def clear_session_cart(session_id: str):
    """Clear session cart"""
    if session_id in user_carts:
        user_carts[session_id] = []
        return {
            "session_id": session_id,
            "message": "Cart cleared",
            "total_items": 0
        }
    return {"message": "Session not found"}

# ========== DATABASE CART ENDPOINTS ==========
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

# ========== FRONTEND UTILITY ENDPOINTS ==========
@app.get("/api/v1/frontend/config")
async def get_frontend_config():
    """Get frontend configuration"""
    return {
        "api_url": "https://your-backend-url.vercel.app",  # Update this with your actual backend URL
        "frontend_url": "https://frontend-coffee-backendg2.vercel.app",
        "features": {
            "khqr_payments": True,
            "cart_session": True,
            "order_tracking": True,
            "admin_panel": True
        },
        "demo_mode": True,
        "version": "1.0.0"
    }

@app.post("/api/v1/frontend/checkout")
async def frontend_checkout(checkout_data: dict):
    """Simplified checkout for frontend"""
    try:
        # Generate order number
        order_number = f"ORD-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        
        # Create order data
        order_data = schemas.OrderCreate(
            customer_name=checkout_data.get('customer_name', 'Guest'),
            customer_phone=checkout_data.get('customer_phone', ''),
            customer_email=checkout_data.get('customer_email', ''),
            delivery_address=checkout_data.get('delivery_address', ''),
            total_amount=checkout_data.get('total_amount', 0),
            currency=checkout_data.get('currency', 'USD'),
            items=checkout_data.get('items', []),
            payment_method=checkout_data.get('payment_method', 'khqr'),
            notes=checkout_data.get('notes', '')
        )
        
        # Create order
        db_order = await crud.create_order(database, order_data)
        
        if db_order:
            return {
                "success": True,
                "order_number": db_order['order_number'],
                "message": "Order created successfully",
                "redirect_url": f"/order/{db_order['order_number']}"
            }
        
        return {
            "success": False,
            "message": "Failed to create order"
        }
        
    except Exception as e:
        print(f"Checkout error: {str(e)}")
        return {
            "success": False,
            "message": f"Checkout failed: {str(e)}"
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
        "frontend_url": "https://frontend-coffee-backendg2.vercel.app",
        "cors_enabled": True,
        "endpoints": {
            "docs": "/docs",
            "products": "/api/v1/products/",
            "categories": "/api/v1/categories/",
            "session_cart": "/api/v1/cart/session/{session_id}",
            "orders": "/api/v1/orders/",
            "khqr": "/api/v1/khqr/generate",
            "payments": "/api/v1/payments/",
            "admin": "/api/v1/admin/",
            "admin_docs": "/api/v1/admin/docs",
            "frontend_config": "/api/v1/frontend/config",
            "health": "/health"
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
        "active_sessions": len(user_carts),
        "cors": {
            "allowed_origins": [
                "https://frontend-coffee-backendg2.vercel.app",
                "https://frontend-admin-coffee-backendg2-ce1.vercel.app"
            ]
        },
        "timestamp": datetime.now().isoformat()
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
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=10000,
        reload=True  # Auto-reload for development
    )