# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import crud
from database import database

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/login")

async def get_db():
    return database

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, crud.SECRET_KEY, algorithms=[crud.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get admin from database
    admin = await crud.get_admin_by_email(database, email=email)
    if admin is None:
        raise credentials_exception
    
    # Check if admin is active
    if not admin.get("is_active", True):
        raise HTTPException(status_code=400, detail="Admin account is inactive")
    
    return admin

async def get_current_super_admin(current_admin = Depends(get_current_admin)):
    # Check if admin has super_admin role
    if current_admin.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_admin