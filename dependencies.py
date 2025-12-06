# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from database import database, get_db
import crud
import schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/login")

async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db = Depends(get_db)
) -> schemas.AdminUser:
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
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    admin = await crud.get_admin_by_email(db, email=token_data.email)
    if admin is None:
        raise credentials_exception
    if not admin.is_active:
        raise HTTPException(status_code=400, detail="Admin account is inactive")
    
    return admin

async def get_current_super_admin(
    current_admin: schemas.AdminUser = Depends(get_current_admin)
) -> schemas.AdminUser:
    if current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_admin