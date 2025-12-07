# main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
from typing import List, Optional, Dict, Any
import traceback
import os

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BrewHaven Coffee Shop API",
    description="A complete coffee shop backend with FastAPI and KHQR payment integration",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware - ALLOW BOTH FRONTEND AND ADMIN DASHBOARD
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # User frontend domains
        "https://frontend-coffee-backendg2.vercel.app",
        "http://frontend-coffee-backendg2.vercel.app",
        
        # Admin dashboard domains
        "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "http://frontend-admin-coffee-backendg2-ce1.vercel.app",
        
        # Local development
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        
        # Vercel preview URLs (wildcard patterns)
        "https://frontend-coffee-backendg2-*.vercel.app",
        "https://frontend-admin-coffee-backendg2-*.vercel.app",
        "http://frontend-coffee-backendg2-*.vercel.app",
        "http://frontend-admin-coffee-backendg2-*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Include admin router
app.include_router(admin_router, prefix="/api/v1/admin")

# KHQR Configuration - Simplified for deployment
KHQR_AVAILABLE = False
khqr = None
print("🔄 Running in DEMO mode - KHQR payments will be simulated")

# Store active payment checks (in production, use Redis or database)
active_payment_checks = {}

# Store session cart (in production, use Redis or database)
user_carts = {}

# Store admin sessions
admin_sessions = {}

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
    
    # Check if demo user exists
    demo_user = await crud.get_admin_by_email(database, "demo@gmail.com")
    if not demo_user:
        # Create demo admin
        demo_data = schemas.AdminUserCreate(
            email="demo@gmail.com",
            password="demo1234",
            full_name="Demo Manager",
            role="manager"
        )
        await crud.create_admin_user(database, demo_data)
        print("✅ Demo admin created: demo@gmail.com / demo1234")
    
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
                "stock": 100,
                "popularity_score": 95
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
                "stock": 85,
                "popularity_score": 92
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
                "stock": 120,
                "popularity_score": 88
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
                "stock": 90,
                "popularity_score": 90
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
                "stock": 75,
                "popularity_score": 85
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
                "stock": 110,
                "popularity_score": 94
            },
            {
                "name": "Royal Cambodian Blend",
                "price": 6.50,
                "image": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Premium blend with hints of caramel and nuts",
                "category": "Specialty",
                "rating": 4.9,
                "brew_time": "5-6 min",
                "is_available": True,
                "stock": 50,
                "popularity_score": 96
            },
            {
                "name": "Mekong Delta Latte",
                "price": 5.75,
                "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80",
                "description": "Smooth latte with Mekong region coffee beans",
                "category": "Milk Coffee",
                "rating": 4.7,
                "brew_time": "4-5 min",
                "is_available": True,
                "stock": 65,
                "popularity_score": 87
            }
        ]
        
        for product in sample_products:
            query = CoffeeProduct.__table__.insert().values(**product)
            await database.execute(query)
        
        print(f"✅ Created {len(sample_products)} sample coffee products!")
    
    # Create some sample orders for admin dashboard
    total_orders = await database.fetch_val("SELECT COUNT(*) FROM orders")
    if total_orders == 0:
        sample_orders = [
            {
                "order_number": f"ORD-{int(time.time())}-001",
                "customer_name": "John Smith",
                "customer_email": "john.smith@example.com",
                "customer_phone": "+855123456789",
                "delivery_address": "123 Street, Phnom Penh",
                "total_amount": 15.50,
                "currency": "USD",
                "items": json.dumps([
                    {"product_id": 1, "name": "Mondulkiri Arabica", "quantity": 2, "price": 4.50},
                    {"product_id": 5, "name": "Tonle Sap Cappuccino", "quantity": 1, "price": 4.25}
                ]),
                "payment_method": "khqr",
                "payment_status": "paid",
                "order_status": "completed",
                "notes": "Extra sugar please"
            },
            {
                "order_number": f"ORD-{int(time.time())}-002",
                "customer_name": "Sophia Chen",
                "customer_email": "sophia.chen@example.com",
                "customer_phone": "+855987654321",
                "delivery_address": "456 Road, Siem Reap",
                "total_amount": 9.75,
                "currency": "USD",
                "items": json.dumps([
                    {"product_id": 2, "name": "Phnom Penh Cold Brew", "quantity": 1, "price": 5.25},
                    {"product_id": 6, "name": "Kampot Iced Coffee", "quantity": 1, "price": 4.50}
                ]),
                "payment_method": "cash",
                "payment_status": "paid",
                "order_status": "preparing",
                "notes": "No ice in cold brew"
            }
        ]
        
        for order in sample_orders:
            query = Order.__table__.insert().values(**order)
            await database.execute(query)
        
        print("✅ Created sample orders for admin dashboard!")

# Background task to check payment status (demo version)
async def check_payment_status_demo(order_number: str):
    """Demo version that simulates payment confirmation"""
    print(f"⏳ Simulating payment processing for order {order_number}...")
    
    # Store the start time for this order
    active_payment_checks[order_number] = {
        'start_time': time.time(),
        'status': 'processing',
        'last_update': datetime.now().isoformat(),
        'progress': 0
    }
    
    # Simulate payment processing with progress updates
    for i in range(1, 11):
        await asyncio.sleep(1)  # 1 second intervals
        progress = i * 10
        active_payment_checks[order_number]['progress'] = progress
        active_payment_checks[order_number]['last_update'] = datetime.now().isoformat()
        
        if progress >= 70:
            # Simulate payment confirmation at 70%
            active_payment_checks[order_number]['status'] = 'verifying'
    
    # Update order status to paid (for demo)
    db_order = await crud.update_order_payment_status(database, order_number, "paid", "demo_md5_hash")
    if db_order:
        active_payment_checks[order_number]['status'] = 'paid'
        active_payment_checks[order_number]['progress'] = 100
        active_payment_checks[order_number]['last_update'] = datetime.now().isoformat()
        print(f"✅ Demo payment confirmed for order {order_number}")
        
        # Also update order status to preparing
        await crud.update_order_status(database, order_number, "preparing")
    else:
        active_payment_checks[order_number]['status'] = 'failed'
        active_payment_checks[order_number]['progress'] = 100
        active_payment_checks[order_number]['last_update'] = datetime.now().isoformat()
        print(f"❌ Failed to update payment status for order {order_number}")

# ========== PUBLIC ENDPOINTS (For User Frontend) ==========
@app.get("/", tags=["Home"])
async def read_root():
    return RedirectResponse(url="/api/docs")

@app.get("/api/v1/", tags=["API Info"])
async def api_info():
    return {
        "api": "BrewHaven Coffee Shop API",
        "version": "2.0.0",
        "description": "Complete coffee shop backend with KHQR payments",
        "frontend_url": "https://frontend-coffee-backendg2.vercel.app",
        "admin_url": "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "endpoints": {
            "products": "/api/v1/products",
            "categories": "/api/v1/categories",
            "cart": "/api/v1/cart/session/{session_id}",
            "orders": "/api/v1/orders",
            "khqr_payment": "/api/v1/khqr/generate",
            "admin": "/api/v1/admin",
            "health": "/api/v1/health"
        }
    }

# ========== PRODUCT ENDPOINTS ==========
@app.get("/api/v1/products/", response_model=List[schemas.CoffeeProduct], tags=["Products"])
async def read_products(
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = None,
    available_only: bool = False,
    db = Depends(get_db)
):
    """Get all products with optional filtering"""
    products = await crud.get_products(db, skip=skip, limit=limit)
    
    if category:
        products = [p for p in products if p.category == category]
    
    if available_only:
        products = [p for p in products if p.is_available]
    
    return products

@app.get("/api/v1/products/{product_id}", response_model=schemas.CoffeeProduct, tags=["Products"])
async def read_product(product_id: int, db = Depends(get_db)):
    db_product = await crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@app.get("/api/v1/products/search/{query}", tags=["Products"])
async def search_products(query: str, db = Depends(get_db)):
    """Search products by name or description"""
    products = await crud.get_products(db)
    query_lower = query.lower()
    
    results = []
    for product in products:
        if (query_lower in product.name.lower() or 
            query_lower in product.description.lower() or
            query_lower in product.category.lower()):
            results.append(product)
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }

@app.get("/api/v1/categories/", tags=["Products"])
async def get_categories(db = Depends(get_db)):
    """Get all product categories"""
    products = await crud.get_products(db)
    categories = list(set(product.category for product in products if product.category))
    
    # Get category stats
    category_stats = []
    for category in categories:
        category_products = [p for p in products if p.category == category]
        category_stats.append({
            "name": category,
            "count": len(category_products),
            "available_count": len([p for p in category_products if p.is_available])
        })
    
    return {
        "categories": categories,
        "stats": category_stats,
        "total_categories": len(categories)
    }

@app.get("/api/v1/products/category/{category}", tags=["Products"])
async def get_products_by_category(category: str, db = Depends(get_db)):
    products = await crud.get_products(db)
    filtered_products = [product for product in products if product.category == category]
    
    return {
        "category": category,
        "products": filtered_products,
        "count": len(filtered_products)
    }

@app.get("/api/v1/products/popular", tags=["Products"])
async def get_popular_products(limit: int = 6, db = Depends(get_db)):
    """Get popular products (based on rating and stock)"""
    products = await crud.get_products(db)
    
    # Sort by rating and popularity score
    sorted_products = sorted(
        products, 
        key=lambda x: (x.rating, getattr(x, 'popularity_score', 0)), 
        reverse=True
    )
    
    return sorted_products[:limit]

# ========== SESSION CART ENDPOINTS (For User Frontend) ==========
@app.get("/api/v1/cart/session/{session_id}", tags=["Cart"])
async def get_session_cart(session_id: str):
    """Get cart items for a specific session (frontend user)"""
    if session_id in user_carts:
        cart_items = user_carts[session_id]
        total_price = sum(item.get('price', 0) * item.get('quantity', 1) for item in cart_items)
        
        return {
            "session_id": session_id,
            "items": cart_items,
            "total_items": len(cart_items),
            "total_quantity": sum(item.get('quantity', 1) for item in cart_items),
            "total_price": round(total_price, 2),
            "currency": "USD",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "session_id": session_id,
        "items": [],
        "total_items": 0,
        "total_quantity": 0,
        "total_price": 0,
        "currency": "USD",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/cart/session/{session_id}/add", tags=["Cart"])
async def add_to_session_cart(session_id: str, item: dict):
    """Add item to session cart"""
    if session_id not in user_carts:
        user_carts[session_id] = []
    
    # Validate required fields
    if not item.get('product_id') or not item.get('name') or not item.get('price'):
        raise HTTPException(
            status_code=400, 
            detail="Product ID, name, and price are required"
        )
    
    # Check if item already exists in cart
    for cart_item in user_carts[session_id]:
        if cart_item.get('product_id') == item.get('product_id'):
            cart_item['quantity'] = cart_item.get('quantity', 1) + item.get('quantity', 1)
            cart_item['updated_at'] = datetime.now().isoformat()
            
            # Calculate total price for this item
            cart_item['item_total'] = cart_item['quantity'] * cart_item['price']
            
            return {
                "session_id": session_id,
                "action": "quantity_updated",
                "item_id": cart_item['id'],
                "quantity": cart_item['quantity'],
                "total_items": len(user_carts[session_id])
            }
    
    # Add new item
    new_item = {
        'id': len(user_carts[session_id]) + 1,
        'product_id': item.get('product_id'),
        'name': item.get('name'),
        'price': item.get('price'),
        'image': item.get('image'),
        'category': item.get('category'),
        'quantity': item.get('quantity', 1),
        'item_total': item.get('price', 0) * item.get('quantity', 1),
        'added_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    user_carts[session_id].append(new_item)
    
    return {
        "session_id": session_id,
        "action": "item_added",
        "item_id": new_item['id'],
        "total_items": len(user_carts[session_id])
    }

@app.put("/api/v1/cart/session/{session_id}/item/{item_id}", tags=["Cart"])
async def update_cart_item_quantity(session_id: str, item_id: int, update_data: dict):
    """Update cart item quantity"""
    if session_id not in user_carts:
        raise HTTPException(status_code=404, detail="Session not found")
    
    for item in user_carts[session_id]:
        if item['id'] == item_id:
            quantity = update_data.get('quantity', 1)
            if quantity <= 0:
                # Remove item if quantity is 0 or negative
                user_carts[session_id] = [i for i in user_carts[session_id] if i['id'] != item_id]
                return {
                    "session_id": session_id,
                    "action": "item_removed",
                    "item_id": item_id
                }
            
            item['quantity'] = quantity
            item['item_total'] = item['price'] * quantity
            item['updated_at'] = datetime.now().isoformat()
            
            return {
                "session_id": session_id,
                "action": "quantity_updated",
                "item_id": item_id,
                "quantity": quantity,
                "item_total": item['item_total']
            }
    
    raise HTTPException(status_code=404, detail="Item not found in cart")

@app.delete("/api/v1/cart/session/{session_id}/item/{item_id}", tags=["Cart"])
async def remove_from_session_cart(session_id: str, item_id: int):
    """Remove item from session cart"""
    if session_id in user_carts:
        initial_count = len(user_carts[session_id])
        user_carts[session_id] = [item for item in user_carts[session_id] if item.get('id') != item_id]
        
        if len(user_carts[session_id]) < initial_count:
            return {
                "session_id": session_id,
                "action": "item_removed",
                "item_id": item_id,
                "total_items": len(user_carts[session_id])
            }
    
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/api/v1/cart/session/{session_id}/clear", tags=["Cart"])
async def clear_session_cart(session_id: str):
    """Clear session cart"""
    if session_id in user_carts:
        user_carts[session_id] = []
        return {
            "session_id": session_id,
            "action": "cart_cleared",
            "total_items": 0
        }
    
    raise HTTPException(status_code=404, detail="Session not found")

@app.post("/api/v1/cart/session/{session_id}/sync", tags=["Cart"])
async def sync_session_cart(session_id: str, items: List[dict]):
    """Sync cart from frontend (replace all items)"""
    user_carts[session_id] = []
    
    for idx, item in enumerate(items):
        if item.get('product_id') and item.get('name') and item.get('price'):
            new_item = {
                'id': idx + 1,
                'product_id': item.get('product_id'),
                'name': item.get('name'),
                'price': item.get('price'),
                'image': item.get('image'),
                'category': item.get('category'),
                'quantity': item.get('quantity', 1),
                'item_total': item.get('price', 0) * item.get('quantity', 1),
                'added_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            user_carts[session_id].append(new_item)
    
    return {
        "session_id": session_id,
        "action": "cart_synced",
        "total_items": len(user_carts[session_id])
    }

# ========== ORDER ENDPOINTS ==========
@app.get("/api/v1/orders/", response_model=List[schemas.Order], tags=["Orders"])
async def read_orders(
    skip: int = 0, 
    limit: int = 100,
    status: Optional[str] = None,
    db = Depends(get_db)
):
    orders = await crud.get_orders(db, skip=skip, limit=limit)
    
    if status:
        orders = [order for order in orders if order.order_status == status]
    
    return orders

@app.post("/api/v1/orders/", response_model=schemas.Order, tags=["Orders"])
async def create_order(
    order: schemas.OrderCreate, 
    background_tasks: BackgroundTasks, 
    request: Request,
    db = Depends(get_db)
):
    try:
        print(f"📦 Creating order for: {order.customer_name}")
        print(f"📞 Contact: {order.customer_phone} | {order.customer_email}")
        print(f"💰 Total amount: ${order.total_amount}")
        print(f"📦 Items: {len(order.items)}")
        
        # Get session ID from headers or generate one
        session_id = request.headers.get('X-Session-ID', str(uuid.uuid4()))
        
        # Create the order
        db_order = await crud.create_order(db=db, order=order)
        
        if not db_order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        print(f"✅ Order created successfully: {db_order.get('order_number')}")
        
        # Clear the session cart if it exists
        if session_id in user_carts:
            del user_carts[session_id]
            print(f"🛒 Cleared cart for session: {session_id}")
        
        # Start background payment checking
        background_tasks.add_task(check_payment_status_demo, db_order['order_number'])
        
        return db_order
    except Exception as e:
        print(f"❌ Error creating order: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

@app.get("/api/v1/orders/{order_number}", response_model=schemas.Order, tags=["Orders"])
async def read_order(order_number: str, db = Depends(get_db)):
    db_order = await crud.get_order_by_number(db, order_number=order_number)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@app.get("/api/v1/orders/customer/{customer_email}", tags=["Orders"])
async def get_customer_orders(customer_email: str, db = Depends(get_db)):
    """Get orders by customer email"""
    orders = await crud.get_orders(db)
    customer_orders = [order for order in orders if order.customer_email == customer_email]
    
    return {
        "customer_email": customer_email,
        "orders": customer_orders,
        "total_orders": len(customer_orders),
        "total_spent": sum(order.total_amount for order in customer_orders)
    }

# ========== KHQR PAYMENT ENDPOINTS ==========
@app.post("/api/v1/khqr/generate", response_model=schemas.KHQRResponse, tags=["Payment"])
async def generate_khqr_payment(
    khqr_request: schemas.KHQRRequest, 
    background_tasks: BackgroundTasks
):
    """Generate demo KHQR for deployment"""
    print(f"🔄 Generating DEMO KHQR for order: {khqr_request.order_number}")
    print(f"💰 Amount: {khqr_request.amount} {khqr_request.currency}")
    
    # Generate demo QR data
    timestamp = int(datetime.now().timestamp())
    demo_md5 = f"demo_{khqr_request.order_number}_{timestamp}"
    
    # Create demo QR data structure
    qr_data = {
        "version": "KHQR1.0",
        "mode": "DEMO",
        "merchant": "BrewHaven Coffee Shop",
        "merchant_id": "DEMO123456",
        "terminal_id": "TERM001",
        "order_number": khqr_request.order_number,
        "amount": khqr_request.amount,
        "currency": khqr_request.currency,
        "timestamp": timestamp,
        "checksum": demo_md5
    }
    
    qr_data_string = json.dumps(qr_data)
    
    # Start demo payment processing
    background_tasks.add_task(check_payment_status_demo, khqr_request.order_number)
    
    return schemas.KHQRResponse(
        qr_data=qr_data_string,
        md5_hash=demo_md5,
        deeplink=f"https://example.com/khqr/pay?order={khqr_request.order_number}&amount={khqr_request.amount}",
        qr_image=None,
        demo_mode=True,
        message="This is a demo payment. In production, real KHQR will be generated."
    )

@app.get("/api/v1/khqr/status/{order_number}", response_model=schemas.PaymentStatusResponse, tags=["Payment"])
async def get_payment_status(order_number: str):
    """Get payment status for an order"""
    try:
        db_order = await crud.get_order_by_number(database, order_number=order_number)
        if db_order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        
        print(f"🔍 Checking payment status for order: {order_number}")
        
        # Check if we have active payment checking for this order
        active_check = active_payment_checks.get(order_number)
        current_status = db_order.get('payment_status', 'pending')
        
        # If we have active checking, use that status
        if active_check:
            current_status = active_check['status']
            progress = active_check.get('progress', 0)
            print(f"📊 Active payment check: {current_status} ({progress}%)")
        else:
            progress = 100 if current_status == 'paid' else 0
        
        # Return status with detailed information
        transaction_data = {
            "order_number": order_number,
            "amount": db_order.get('total_amount', 0),
            "currency": db_order.get('currency', 'USD'),
            "timestamp": datetime.now().isoformat(),
            "payment_method": db_order.get('payment_method', 'khqr'),
            "demo": True,
            "mode": "demo",
            "progress": progress,
            "estimated_time": "10 seconds" if progress < 100 else "completed",
            "order_status": db_order.get('order_status', 'pending')
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Payment status check failed: {str(e)}")

# ========== PAYMENT MANAGEMENT ENDPOINTS ==========
@app.post("/api/v1/payments/{order_number}/simulate-paid", tags=["Payment"])
async def simulate_payment_paid(order_number: str):
    """Endpoint to simulate payment for testing"""
    try:
        db_order = await crud.update_order_payment_status(database, order_number, "paid", "simulated_md5")
        if db_order:
            # Update active check status
            if order_number in active_payment_checks:
                active_payment_checks[order_number]['status'] = 'paid'
                active_payment_checks[order_number]['progress'] = 100
            
            # Also update order status
            await crud.update_order_status(database, order_number, "preparing")
            
            return {
                "message": "Payment simulated successfully",
                "order_number": order_number,
                "status": "paid",
                "order_status": "preparing",
                "demo": True
            }
        else:
            raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate payment: {str(e)}")

@app.post("/api/v1/payments/{order_number}/simulate-failed", tags=["Payment"])
async def simulate_payment_failed(order_number: str):
    """Endpoint to simulate payment failure for testing"""
    try:
        db_order = await crud.update_order_payment_status(database, order_number, "failed", None)
        if db_order:
            # Update active check status
            if order_number in active_payment_checks:
                active_payment_checks[order_number]['status'] = 'failed'
                active_payment_checks[order_number]['progress'] = 100
            
            return {
                "message": "Payment failure simulated successfully",
                "order_number": order_number,
                "status": "failed",
                "demo": True
            }
        else:
            raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate payment failure: {str(e)}")

@app.get("/api/v1/payments/active", tags=["Payment"])
async def get_active_payments():
    """Get all active payment checks (for monitoring)"""
    return {
        "active_payments": active_payment_checks,
        "total_active": len(active_payment_checks),
        "timestamp": datetime.now().isoformat()
    }

# ========== FRONTEND UTILITY ENDPOINTS ==========
@app.get("/api/v1/frontend/config", tags=["Frontend"])
async def get_frontend_config():
    """Get frontend configuration"""
    return {
        "api_url": "https://your-backend-url.vercel.app",  # Update this with your actual backend URL
        "frontend_url": "https://frontend-coffee-backendg2.vercel.app",
        "admin_url": "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
        "features": {
            "khqr_payments": True,
            "cart_session": True,
            "order_tracking": True,
            "admin_panel": True,
            "categories": True,
            "search": True,
            "customer_orders": True
        },
        "demo_mode": True,
        "demo_accounts": {
            "admin": "admin@gmail.com / 11112222",
            "manager": "demo@gmail.com / demo1234"
        },
        "version": "2.0.0",
        "support": {
            "email": "support@brewhaven.com",
            "phone": "+855 1234 5678"
        }
    }

@app.post("/api/v1/frontend/checkout", tags=["Frontend"])
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
                "redirect_url": f"/order/{db_order['order_number']}",
                "payment_url": f"/payment/{db_order['order_number']}",
                "data": {
                    "order": db_order,
                    "estimated_time": "10-15 minutes",
                    "payment_instructions": "Scan the KHQR code to complete payment"
                }
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

# ========== ADMIN UTILITY ENDPOINTS ==========
@app.get("/api/v1/admin/dashboard/stats", tags=["Admin"])
async def get_dashboard_stats():
    """Get dashboard statistics for admin panel"""
    try:
        # Get total products
        total_products = await database.fetch_val("SELECT COUNT(*) FROM coffee_products")
        available_products = await database.fetch_val("SELECT COUNT(*) FROM coffee_products WHERE is_available = true")
        
        # Get total orders
        total_orders = await database.fetch_val("SELECT COUNT(*) FROM orders")
        today = datetime.now().date()
        today_orders = await database.fetch_val(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = :today",
            {"today": today}
        )
        
        # Get revenue
        total_revenue = await database.fetch_val("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = 'paid'")
        today_revenue = await database.fetch_val(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = 'paid' AND DATE(created_at) = :today",
            {"today": today}
        )
        
        # Get order status counts
        order_status_counts = {}
        statuses = await database.fetch_all("SELECT order_status, COUNT(*) as count FROM orders GROUP BY order_status")
        for status in statuses:
            order_status_counts[status['order_status']] = status['count']
        
        # Get recent orders
        recent_orders = await database.fetch_all(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT 5"
        )
        
        # Get low stock products
        low_stock_products = await database.fetch_all(
            "SELECT * FROM coffee_products WHERE stock < 20 ORDER BY stock ASC LIMIT 5"
        )
        
        return {
            "stats": {
                "products": {
                    "total": total_products,
                    "available": available_products,
                    "out_of_stock": total_products - available_products
                },
                "orders": {
                    "total": total_orders,
                    "today": today_orders,
                    "pending": order_status_counts.get('pending', 0),
                    "preparing": order_status_counts.get('preparing', 0),
                    "completed": order_status_counts.get('completed', 0),
                    "cancelled": order_status_counts.get('cancelled', 0)
                },
                "revenue": {
                    "total": float(total_revenue),
                    "today": float(today_revenue),
                    "currency": "USD"
                }
            },
            "recent_orders": recent_orders,
            "low_stock_products": low_stock_products,
            "active_payments": len(active_payment_checks),
            "active_sessions": len(user_carts),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")

# ========== HEALTH & STATUS ENDPOINTS ==========
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    db_status = "connected"
    try:
        await database.execute("SELECT 1")
    except:
        db_status = "disconnected"
    
    # Get system info
    import sys
    import platform
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": db_status,
            "khqr_payments": "demo_mode",
            "session_store": "memory"
        },
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "active_sessions": len(user_carts),
            "active_payments": len(active_payment_checks),
            "uptime": "N/A"  # In production, you'd calculate this
        },
        "cors": {
            "allowed_origins": [
                "https://frontend-coffee-backendg2.vercel.app",
                "https://frontend-admin-coffee-backendg2-ce1.vercel.app"
            ]
        }
    }

@app.get("/api/v1/status", tags=["System"])
async def system_status():
    """Get detailed system status"""
    return {
        "system": "BrewHaven Coffee Shop API",
        "version": "2.0.0",
        "mode": "DEMO",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {"status": "connected", "type": "sqlite"},
            "khqr_payments": {"status": "demo_mode", "available": False},
            "session_management": {"status": "active", "sessions": len(user_carts)},
            "order_processing": {"status": "active", "queued": len(active_payment_checks)}
        },
        "urls": {
            "user_frontend": "https://frontend-coffee-backendg2.vercel.app",
            "admin_dashboard": "https://frontend-admin-coffee-backendg2-ce1.vercel.app",
            "api_documentation": "/api/docs",
            "admin_documentation": "/api/v1/admin/docs"
        }
    }

# ========== ERROR HANDLING ==========
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.status_code,
            "message": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    print(f"Global error: {exc}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": 500,
            "message": "Internal server error occurred",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

# ========== OPTIONS HANDLER FOR CORS ==========
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={"message": "CORS preflight"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# ========== MAIN ENTRY POINT ==========
if __name__ == "__main__":
    import uvicorn
    
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 10000))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    print("=" * 50)
    print("🚀 BrewHaven Coffee Shop API Starting...")
    print(f"📡 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🔄 Reload: {reload}")
    print("=" * 50)
    print("🌐 Frontend URL: https://frontend-coffee-backendg2.vercel.app")
    print("👨‍💼 Admin URL: https://frontend-admin-coffee-backendg2-ce1.vercel.app")
    print("📚 API Docs: http://localhost:10000/api/docs")
    print("📚 Admin Docs: http://localhost:10000/api/v1/admin/docs")
    print("=" * 50)
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        reload=reload
    )