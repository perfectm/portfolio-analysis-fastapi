"""
Authentication middleware for protecting routes
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from auth_service import get_current_user_from_token
from models import User

# Security scheme
security = HTTPBearer()

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Dependency to get current authenticated user.
    Use this dependency to protect any route that requires authentication.
    """
    user = await get_current_user_from_token(credentials.credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

# Optional dependency - returns None if no valid token
async def get_current_user_optional(
    db: Annotated[Session, Depends(get_db)],
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> User | None:
    """
    Optional authentication dependency.
    Returns user if authenticated, None otherwise.
    Use this for routes that can work with or without authentication.
    """
    if not credentials:
        return None
        
    user = await get_current_user_from_token(credentials.credentials, db)
    if user and user.is_active:
        return user
    
    return None