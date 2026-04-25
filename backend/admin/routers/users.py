"""
Admin — User management.

Endpoints:
  GET   /api/v1/admin/users                    List all users (super_admin only)
  PATCH /api/v1/admin/users/{user_id}/role     Promote / change a user's role (super_admin only)

Only super_admin can assign the super_admin role.
All other role changes (e.g. promoting to nafdac_admin) are also super_admin only.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import require_role
from backend.models.user import User, UserRole
from backend.utils.response import success_response

logger = logging.getLogger("admin.users")

router = APIRouter()

_SUPER_ADMIN_ONLY = Depends(require_role("super_admin"))


# ---------------------------------------------------------------------------
# Schemas (inline — no separate file needed for two simple models)
# ---------------------------------------------------------------------------

class RoleUpdateRequest(BaseModel):
    role: UserRole


class UserSummaryResponse(BaseModel):
    id: str
    email: Optional[str]
    phone: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: UserRole
    status: str
    company_id: Optional[str]
    created_at: str

model_config = ConfigDict()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users", dependencies=[_SUPER_ADMIN_ONLY])
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated list of all users. Super admin only."""
    offset = (page - 1) * limit
    stmt = select(User).where(User.deleted_at.is_(None))
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)

    count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    if role:
        count_stmt = count_stmt.where(User.role == role)

    results, total = await db.execute(stmt), await db.execute(count_stmt)
    users = results.scalars().all()
    total_count = total.scalar_one()

    return success_response({
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "phone": u.phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "status": u.status,
                "company_id": str(u.company_id) if u.company_id else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total_count,
        "page": page,
        "limit": limit,
    })


@router.patch("/users/{user_id}/role", dependencies=[_SUPER_ADMIN_ONLY])
async def update_user_role(
    user_id: UUID,
    body: RoleUpdateRequest,
    current_user: User = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Change a user's role. Super admin only.

    Rules:
    - A super_admin cannot change their own role (prevents accidental self-demotion).
    - Only super_admin can assign the super_admin role.
    - super_admin role cannot be removed from the last remaining super_admin
      (prevents total lockout — there must always be at least one super_admin).
    """
    # Prevent self-role-change
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    target: User | None = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_role = str(body.role.value if hasattr(body.role, "value") else body.role)

    # If we're demoting an existing super_admin, ensure at least one remains
    if target.role == "super_admin" and new_role != "super_admin":
        count_result = await db.execute(
            select(func.count()).select_from(User).where(
                User.role == "super_admin",
                User.deleted_at.is_(None),
                User.status == "active",
            )
        )
        if count_result.scalar_one() <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot demote the last active super_admin. "
                    "Promote another user first."
                ),
            )

    old_role = target.role
    target.role = new_role
    await db.commit()
    await db.refresh(target)

    logger.info(
        "Role changed: user=%s  %s → %s  by super_admin=%s",
        user_id, old_role, new_role, current_user.id,
    )

    return success_response({
        "id": str(target.id),
        "email": target.email,
        "role": target.role,
        "message": f"Role updated from {old_role} to {new_role}",
    })
