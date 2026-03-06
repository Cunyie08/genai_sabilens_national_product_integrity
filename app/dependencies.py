"""Dependencies and guards"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import decode_token
from app.models.user import UserRole


async def get_current_user(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get current authenticated user"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    return {"user_id": user_id, "payload": payload}


def require_role(*roles: UserRole):
    """Dependency to check user role"""
    async def check_role(current_user: dict = Depends(get_current_user)):
        user_role = current_user["payload"].get("role")
        if user_role not in [role.value for role in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    
    return check_role
