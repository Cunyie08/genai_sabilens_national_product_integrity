"""Authentication service"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import smtplib
from email.mime.text import MIMEText

from backend.models.user import User, Session, OTPVerification, UserRole, UserStatus
from backend.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from backend.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse, ProfileUpdateRequest
from backend.config import settings


class AuthService:
    """Authentication service"""
    
    @staticmethod
    async def register_user(db: AsyncSession, req: RegisterRequest) -> Tuple[UserResponse, TokenResponse]:
        """Register new user"""
        # super_admin accounts can only be created via the seed script or promoted
        # by an existing super_admin via PATCH /api/v1/admin/users/{id}/role.
        if req.role and str(req.role) in ("super_admin", "UserRole.SUPER_ADMIN"):
            raise ValueError("super_admin role cannot be self-registered")

        # Check if user exists — only check email uniqueness if email was provided.
        # When email is None, SQLAlchemy generates "email IS NULL" which would match
        # every user without an email, causing all registrations to fail.
        from sqlalchemy import or_
        conditions = [User.phone == req.phone]
        if req.email is not None:
            conditions.append(User.email == req.email)
        stmt = select(User).where(or_(*conditions))
        existing = await db.execute(stmt)
        if existing.scalars().first():
            raise ValueError("User already exists")
        
        # In local debug mode, auto-activate accounts to simplify testing.
        auto_activate = settings.AUTH_AUTO_ACTIVATE

        # Create user with new fields
        user = User(
            email=req.email,
            phone=req.phone,
            password_hash=hash_password(req.password),
            first_name=req.first_name,
            last_name=req.last_name,
            role=req.role,
            status=UserStatus.ACTIVE if auto_activate else UserStatus.PENDING,
            phone_verified=auto_activate,
            email_verified=auto_activate,
            # NEW: Save location fields
            state=getattr(req, 'state', None),
            city=getattr(req, 'city', None),
        )
        db.add(user)
        await db.flush()
        
        # Generate OTP
        otp_code = "".join(random.choices(string.digits, k=6))
        otp = OTPVerification(
            user_id=user.id,
            phone=req.phone,
            email=req.email,
            otp_code=otp_code,
            purpose="registration",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(otp)
        await db.commit()
        
        # Send OTP (mock for now)
        # await send_sms(req.phone, f"Your SabiLens OTP: {otp_code}")
        
        # Create tokens
        tokens = await AuthService.create_tokens(user)
        user_resp = UserResponse.model_validate(user)
        
        return user_resp, tokens
    
    
    @staticmethod
    async def login_user(db: AsyncSession, req: LoginRequest) -> Tuple[UserResponse, TokenResponse]:
        """Login user"""
        from sqlalchemy import or_
        conditions = []
        if req.phone:
            conditions.append(User.phone == req.phone)
        if req.email:
            conditions.append(User.email == req.email)
        stmt = select(User).where(or_(*conditions))
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user or not verify_password(req.password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        if user.status != UserStatus.ACTIVE:
            raise ValueError("User account is not active")
        
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        
        # Create tokens
        tokens = await AuthService.create_tokens(user)
        user_resp = UserResponse.model_validate(user)
        
        return user_resp, tokens
    
    
    @staticmethod
    async def update_profile(db: AsyncSession, user_id: str, req: ProfileUpdateRequest) -> UserResponse:
        """Update user profile"""
        user = await db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        
        # Update fields if provided
        if req.first_name is not None:
            user.first_name = req.first_name
        if req.last_name is not None:
            user.last_name = req.last_name
        if req.preferred_language is not None:
            user.preferred_language = req.preferred_language
        if req.state is not None:
            user.state = req.state
        if req.city is not None:
            user.city = req.city
        if req.email is not None:
            # Check if email is already taken by another user
            if req.email != user.email:
                stmt = select(User).where(User.email == req.email, User.id != user_id)
                result = await db.execute(stmt)
                if result.scalars().first():
                    raise ValueError("Email already in use")
                user.email = req.email
                user.email_verified = False  # Require re-verification for new email
        
        await db.commit()
        await db.refresh(user)
        
        return UserResponse.model_validate(user)
    
    
    @staticmethod
    async def create_tokens(user: User) -> TokenResponse:
        """Create access and refresh tokens"""
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        access_token = create_access_token({"sub": str(user.id), "role": role})
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    
    
    @staticmethod
    async def verify_otp(db: AsyncSession, phone: str, otp_code: str, purpose: str) -> bool:
        """Verify OTP"""
        stmt = select(OTPVerification).where(
            (OTPVerification.phone == phone) &
            (OTPVerification.otp_code == otp_code) &
            (OTPVerification.purpose == purpose) &
            (OTPVerification.verified_at.is_(None)) &
            (OTPVerification.expires_at > datetime.now(timezone.utc))
        )
        result = await db.execute(stmt)
        otp = result.scalars().first()
        
        if not otp:
            raise ValueError("Invalid or expired OTP")
        
        # Mark as verified
        otp.verified_at = datetime.now(timezone.utc)
        
        # Update user if registration
        if purpose == "registration":
            user = await db.get(User, otp.user_id)
            if user:
                user.phone_verified = True
                user.status = UserStatus.ACTIVE
        
        await db.commit()
        return True
    
    
    @staticmethod
    async def send_otp(db: AsyncSession, phone: str, email: Optional[str], purpose: str) -> str:
        """Send OTP"""
        otp_code = "".join(random.choices(string.digits, k=6))
        
        # Delete previous OTPs
        stmt = select(OTPVerification).where(
            (OTPVerification.phone == phone) |
            (OTPVerification.email == email)
        )
        result = await db.execute(stmt)
        old_otps = result.scalars().all()
        for old_otp in old_otps:
            await db.delete(old_otp)
        
        # Create new OTP
        otp = OTPVerification(
            phone=phone,
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(otp)
        await db.commit()
        
        # Send SMS/Email (mock)
        # await send_sms(phone, f"Your SabiLens OTP: {otp_code}")
        
        return otp_code
    
    
    @staticmethod
    async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Refresh access token"""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        
        user_id = payload.get("sub")
        user = await db.get(User, user_id)
        
        if not user or user.status != UserStatus.ACTIVE:
            raise ValueError("User not found or inactive")
        
        tokens = await AuthService.create_tokens(user)
        return tokens
    
    
    @staticmethod
    async def reset_password(db: AsyncSession, phone: str, otp_code: str, new_password: str) -> bool:
        """Reset password"""
        stmt = select(OTPVerification).where(
            (OTPVerification.phone == phone) &
            (OTPVerification.otp_code == otp_code) &
            (OTPVerification.purpose == "password_reset") &
            (OTPVerification.expires_at > datetime.now(timezone.utc))
        )
        result = await db.execute(stmt)
        otp = result.scalars().first()
        
        if not otp:
            raise ValueError("Invalid or expired OTP")
        
        # Update password
        stmt = select(User).where(User.phone == phone)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            raise ValueError("User not found")
        
        user.password_hash = hash_password(new_password)
        otp.verified_at = datetime.now(timezone.utc)
        await db.commit()
        
        return True
    
    
    @staticmethod
    async def logout(db: AsyncSession, user_id: str, all_devices: bool = False) -> bool:
        """Logout user"""
        if all_devices:
            # Delete all sessions
            stmt = select(Session).where(Session.user_id == user_id)
            result = await db.execute(stmt)
            sessions = result.scalars().all()
            for session in sessions:
                await db.delete(session)
        await db.commit()
        return True