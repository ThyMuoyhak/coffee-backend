# admin_api.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import date
from dependencies import get_db, get_current_admin, get_current_super_admin
import crud
import schemas

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# ========== AUTH ENDPOINTS ==========
@router.post("/login", response_model=schemas.Token)
async def admin_login(
    admin_login: schemas.AdminUserLogin,
    db = Depends(get_db)
):
    try:
        admin = await crud.authenticate_admin(db, admin_login.email, admin_login.password)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login
        await crud.update_admin_last_login(db, admin["id"])
        
        # Create access token with email as subject
        access_token = crud.create_access_token(data={"sub": admin["email"]})
        
        # Return token and admin info
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "full_name": admin["full_name"],
                "role": admin["role"],
                "is_active": admin["is_active"],
                "last_login": admin["last_login"],
                "created_at": admin["created_at"],
                "updated_at": admin["updated_at"]
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/me", response_model=schemas.AdminUser)
async def read_admin_me(current_admin: schemas.AdminUser = Depends(get_current_admin)):
    return current_admin

# ========== DASHBOARD ENDPOINTS ==========
@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.get_dashboard_stats(db)

@router.get("/dashboard/order-stats")
async def get_order_stats(
    days: int = Query(7, ge=1, le=30),
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.get_order_stats(db, days)

# ========== ADMIN USER MANAGEMENT (Super Admin Only) ==========
@router.post("/users/", response_model=schemas.AdminUser)
async def create_admin_user(
    admin: schemas.AdminUserCreate,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_super_admin)
):
    return await crud.create_admin_user(db=db, admin=admin)

@router.get("/users/", response_model=List[schemas.AdminUser])
async def read_admin_users(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_super_admin)
):
    return await crud.get_admin_users(db, skip=skip, limit=limit)

@router.get("/users/{admin_id}", response_model=schemas.AdminUser)
async def read_admin_user(
    admin_id: int,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_super_admin)
):
    db_admin = await crud.get_admin_user(db, admin_id=admin_id)
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return db_admin

@router.put("/users/{admin_id}", response_model=schemas.AdminUser)
async def update_admin_user(
    admin_id: int,
    admin_update: schemas.AdminUserUpdate,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_super_admin)
):
    db_admin = await crud.update_admin_user(db, admin_id=admin_id, admin_update=admin_update)
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return db_admin

@router.delete("/users/{admin_id}")
async def delete_admin_user(
    admin_id: int,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_super_admin)
):
    # Prevent deleting self
    if current_admin.id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    success = await crud.delete_admin_user(db, admin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return {"message": "Admin user deleted successfully"}

# ========== PRODUCT MANAGEMENT ==========
@router.get("/products/", response_model=List[schemas.CoffeeProduct])
async def admin_read_products(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.get_products(db, skip=skip, limit=limit)

@router.get("/products/{product_id}", response_model=schemas.CoffeeProduct)
async def admin_read_product(
    product_id: int,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_product = await crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.post("/products/", response_model=schemas.CoffeeProduct)
async def admin_create_product(
    product: schemas.CoffeeProductCreate,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.create_product(db=db, product=product)

@router.put("/products/{product_id}", response_model=schemas.CoffeeProduct)
async def admin_update_product(
    product_id: int,
    product_update: schemas.CoffeeProductUpdate,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_product = await crud.update_product(db, product_id=product_id, product_update=product_update)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.delete("/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    success = await crud.delete_product(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

# ========== ORDER MANAGEMENT ==========
@router.get("/orders/", response_model=List[schemas.Order])
async def admin_read_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    if status:
        orders = await crud.get_orders_by_status(db, status)
        return orders[skip:skip+limit]
    
    return await crud.get_orders(db, skip=skip, limit=limit)

@router.get("/orders/search")
async def admin_search_orders(
    query: str,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.search_orders(db, query)

@router.get("/orders/{order_id}", response_model=schemas.Order)
async def admin_read_order(
    order_id: int,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_order = await crud.get_order_by_id(db, order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@router.put("/orders/{order_id}", response_model=schemas.Order)
async def admin_update_order(
    order_id: int,
    order_update: schemas.OrderUpdate,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_order = await crud.update_order(db, order_id=order_id, order_update=order_update)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@router.get("/orders/by-date-range")
async def admin_get_orders_by_date_range(
    start_date: date,
    end_date: date,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.get_orders_by_date_range(db, start_date, end_date)

# ========== CART MANAGEMENT ==========
@router.get("/cart/", response_model=List[schemas.CartItem])
async def admin_read_cart_items(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    return await crud.get_cart_items(db, skip=skip, limit=limit)

# ========== PAYMENT MANAGEMENT ==========
@router.post("/payments/{order_number}/mark-paid")
async def mark_order_as_paid(
    order_number: str,
    payment_method: str = "cash",
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_order = await crud.update_order_payment_status(db, order_number, "paid")
    if db_order:
        # Update payment method
        from sqlalchemy import update as sql_update
        query = sql_update(crud.Order.__table__).where(
            crud.Order.__table__.c.order_number == order_number
        ).values(payment_method=payment_method)
        await db.execute(query)
        
        return {"message": "Order marked as paid", "order_number": order_number}
    raise HTTPException(status_code=404, detail="Order not found")

@router.post("/payments/{order_number}/mark-refunded")
async def mark_order_as_refunded(
    order_number: str,
    db = Depends(get_db),
    current_admin: schemas.AdminUser = Depends(get_current_admin)
):
    db_order = await crud.update_order_payment_status(db, order_number, "refunded")
    if db_order:
        return {"message": "Order marked as refunded", "order_number": order_number}
    raise HTTPException(status_code=404, detail="Order not found")