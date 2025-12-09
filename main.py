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
        "*"
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
    
    # Create default admin with DEBUGGING
    print("👤 Checking/creating default admin...")
    
    try:
        check_query = "SELECT id, email, hashed_password, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = 'admin@gmail.com'"
        existing_admin = await database.fetch_one(check_query)
        
        if not existing_admin:
            print("👤 Creating new admin with SHA256 hash...")
            
            password = "11112222"
            hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
            
            print(f"🔑 Generated hash length: {len(hashed_password)}")
            print(f"🔑 Hash sample: {hashed_password[:50]}...")
            
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
            print(f"   Hash length: {len(hashed_password)}")
        else:
            print(f"✅ Admin already exists in database")
            print(f"   Admin ID: {existing_admin['id']}")
            print(f"   Email: {existing_admin['email']}")
            print(f"   Stored hash length: {existing_admin['hash_len']}")
            print(f"   Hash sample: {existing_admin['hashed_password'][:50]}...")
            
            # Verify the hash matches expected
            password = "11112222"
            expected_hash = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
            print(f"   Expected hash length: {len(expected_hash)}")
            print(f"   Expected hash sample: {expected_hash[:50]}...")
            
            if existing_admin['hashed_password'] != expected_hash:
                print("⚠️ WARNING: Stored hash doesn't match expected hash!")
                print("   Deleting and recreating admin...")
                
                # Delete and recreate
                delete_query = "DELETE FROM admin_users WHERE email = 'admin@gmail.com'"
                await database.execute(delete_query)
                
                insert_query = """
                INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
                VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
                """
                
                await database.execute(
                    query=insert_query,
                    values={
                        "email": "admin@gmail.com",
                        "hashed_password": expected_hash,
                        "full_name": "System Administrator",
                        "role": "super_admin",
                        "is_active": True,
                        "created_at": datetime.utcnow()
                    }
                )
                print("✅ Admin recreated with correct hash!")
            
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

# Simple login function for debugging
def verify_admin_password(email: str, password: str) -> bool:
    """Direct password verification for debugging"""
    expected_hash = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
    
    # Check database directly
    import asyncio
    async def check_db():
        query = "SELECT hashed_password FROM admin_users WHERE email = :email"
        result = await database.fetch_one(query, {"email": email})
        if result:
            db_hash = result["hashed_password"]
            print(f"🔑 DB Hash: {db_hash[:50]}...")
            print(f"🔑 Expected: {expected_hash[:50]}...")
            print(f"🔑 Match: {db_hash == expected_hash}")
            return db_hash == expected_hash
        return False
    
    return asyncio.run(check_db())

# Endpoint for admin panel login
@app.post("/api/v1/admin/login", response_model=schemas.Token)
async def admin_login_admin_panel(login_data: schemas.AdminLogin):
    """Admin login endpoint for admin panel"""
    try:
        print(f"🔐 ADMIN LOGIN ATTEMPT:")
        print(f"   Email: {login_data.email}")
        print(f"   Password: {login_data.password}")
        print(f"   Password length: {len(login_data.password)}")
        
        # First check if admin exists
        check_query = "SELECT id, email, hashed_password, role, is_active FROM admin_users WHERE email = :email"
        admin_record = await database.fetch_one(check_query, {"email": login_data.email})
        
        if not admin_record:
            print(f"❌ Admin not found in database: {login_data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Admin found in database:")
        print(f"   ID: {admin_record['id']}")
        print(f"   Email: {admin_record['email']}")
        print(f"   Role: {admin_record['role']}")
        print(f"   Is Active: {admin_record['is_active']}")
        print(f"   Stored hash length: {len(admin_record['hashed_password'])}")
        print(f"   Stored hash sample: {admin_record['hashed_password'][:50]}...")
        
        # Check if admin is active
        if not admin_record['is_active']:
            print(f"❌ Admin account is disabled")
            raise HTTPException(status_code=403, detail="Admin account is disabled")
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(f"{login_data.password}{SALT}".encode()).hexdigest()
        print(f"🔑 Calculated expected hash:")
        print(f"   Length: {len(expected_hash)}")
        print(f"   Sample: {expected_hash[:50]}...")
        
        # Verify password
        if admin_record['hashed_password'] != expected_hash:
            print(f"❌ Password verification FAILED!")
            print(f"   Stored: {admin_record['hashed_password'][:50]}...")
            print(f"   Expected: {expected_hash[:50]}...")
            
            # Try common mistakes
            common_mistakes = [
                login_data.password,  # Original
                login_data.password.strip(),  # Trimmed
                "11112222",  # Default
                "11112222".strip(),
            ]
            
            for i, pwd in enumerate(common_mistakes):
                test_hash = hashlib.sha256(f"{pwd}{SALT}".encode()).hexdigest()
                if admin_record['hashed_password'] == test_hash:
                    print(f"⚠️ Found matching password: Attempt {i+1}")
            
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        print(f"✅ Password verification SUCCESS!")
        
        # Update last login
        update_query = "UPDATE admin_users SET last_login = :last_login WHERE id = :id"
        await database.execute(
            update_query,
            {"last_login": datetime.utcnow(), "id": admin_record["id"]}
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin_record["email"], "role": admin_record["role"]},
            expires_delta=access_token_expires
        )
        
        print(f"✅ Login successful for: {admin_record['email']}")
        print(f"   Token created successfully")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin_record["id"],
                "email": admin_record["email"],
                "full_name": admin_record.get("full_name", "Administrator"),
                "role": admin_record["role"]
            }
        }
        
    except HTTPException as e:
        print(f"❌ HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Original auth login endpoint
@app.post("/api/v1/auth/login", response_model=schemas.Token)
async def admin_login(login_data: schemas.AdminLogin):
    """Admin login endpoint (original)"""
    return await admin_login_admin_panel(login_data)

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
            "admin_login": "/api/v1/admin/login",
            "test_admin": "/test-admin",
            "reset_admin": "/reset-admin"
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

# Debug endpoint to check admin
@app.get("/test-admin")
async def test_admin():
    """Test endpoint to check admin credentials"""
    try:
        test_email = "admin@gmail.com"
        test_password = "11112222"
        
        print(f"🔐 Testing admin credentials for: {test_email}")
        
        # Check if admin exists
        query = "SELECT id, email, hashed_password, LENGTH(hashed_password) as hash_len FROM admin_users WHERE email = :email"
        admin = await database.fetch_one(query, {"email": test_email})
        
        if not admin:
            return {
                "success": False,
                "message": "Admin not found in database",
                "email": test_email,
                "action": "Try /reset-admin to create admin"
            }
        
        db_hash = admin["hashed_password"]
        hash_len = admin["hash_len"]
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(f"{test_password}{SALT}".encode()).hexdigest()
        
        # Try different password variations
        test_variations = [
            ("Original", test_password),
            ("Trimmed", test_password.strip()),
            ("Default", "11112222"),
            ("Default trimmed", "11112222".strip()),
        ]
        
        variations_result = []
        for name, pwd in test_variations:
            test_hash = hashlib.sha256(f"{pwd}{SALT}".encode()).hexdigest()
            variations_result.append({
                "name": name,
                "password": pwd,
                "matches": db_hash == test_hash,
                "hash_sample": test_hash[:20] + "..."
            })
        
        return {
            "success": True,
            "admin_exists": True,
            "admin_id": admin["id"],
            "email": test_email,
            "db_hash_length": hash_len,
            "db_hash_sample": db_hash[:50] + "..." if db_hash else "None",
            "expected_hash_sample": expected_hash[:50] + "...",
            "hashes_match": db_hash == expected_hash,
            "password_variations": variations_result,
            "salt_used": SALT,
            "action": "If hashes don't match, use /reset-admin"
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
        delete_count = await database.execute("DELETE FROM admin_users WHERE email = 'admin@gmail.com'")
        print(f"🧹 Deleted {delete_count} admin users")
        
        # Create new admin with SHA256
        password = "11112222"
        hashed_password = hashlib.sha256(f"{password}{SALT}".encode()).hexdigest()
        
        insert_query = """
        INSERT INTO admin_users (email, hashed_password, full_name, role, is_active, created_at)
        VALUES (:email, :hashed_password, :full_name, :role, :is_active, :created_at)
        """
        
        admin_id = await database.execute(
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
            "admin_id": admin_id,
            "email": "admin@gmail.com",
            "password": "11112222",
            "hash_length": len(hashed_password),
            "hash_sample": hashed_password[:50] + "...",
            "login_endpoint": "/api/v1/admin/login",
            "test_endpoint": "/test-admin"
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
