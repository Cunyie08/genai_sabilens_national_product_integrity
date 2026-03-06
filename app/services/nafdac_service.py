"""NAFDAC enforcement service"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.models.nafdac import Case, EnforcementAction
from app.models.alert import Alert


class NAFDACService:
    """NAFDAC case and enforcement management"""
    
    @staticmethod
    async def create_case(db: AsyncSession, report_id: str, case_data: dict) -> Case:
        """Create investigation case"""
        case = Case(
            report_id=report_id,
            case_number=case_data.get("case_number"),
            status="open",
            severity=case_data.get("severity", "medium"),
            description=case_data.get("description"),
            assigned_officer_id=case_data.get("assigned_officer_id"),
            created_at=datetime.utcnow(),
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case
    
    
    @staticmethod
    async def record_enforcement(db: AsyncSession, case_id: str, action_data: dict) -> EnforcementAction:
        """Record enforcement action (raid, seizure, notice)"""
        action = EnforcementAction(
            case_id=case_id,
            action_type=action_data.get("type"),  # raid, seizure, warning_notice, fine
            location=action_data.get("location"),
            quantity_seized=action_data.get("quantity_seized"),
            value_seized=action_data.get("value_seized"),
            description=action_data.get("description"),
            officer_id=action_data.get("officer_id"),
            created_at=datetime.utcnow(),
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        return action
    
    
    @staticmethod
    async def get_case(db: AsyncSession, case_id: str) -> Optional[Case]:
        """Get case by ID"""
        return await db.get(Case, case_id)
    
    
    @staticmethod
    async def get_cases(db: AsyncSession, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> tuple[List[Case], int]:
        """Get cases with optional filter"""
        stmt = select(Case).order_by(desc(Case.created_at))
        
        if status:
            stmt = stmt.where(Case.status == status)
        
        stmt = stmt.limit(limit).offset(offset)
        result = await db.execute(stmt)
        cases = result.scalars().all()
        
        # Count total
        count_stmt = select(func.count()).select_from(Case)
        if status:
            count_stmt = count_stmt.where(Case.status == status)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        return cases, total
    
    
    @staticmethod
    async def close_case(db: AsyncSession, case_id: str, resolution: str) -> Case:
        """Close case with resolution"""
        case = await db.get(Case, case_id)
        if not case:
            raise ValueError("Case not found")
        
        case.status = "closed"
        case.resolution = resolution
        case.closed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(case)
        return case
    
    
    @staticmethod
    async def get_hotspot_cases(db: AsyncSession, latitude: float, longitude: float, radius_km: float = 5) -> List[Case]:
        """Get cases near location (for hotspot analysis)"""
        # Mock: In production, use PostGIS for proximity search
        stmt = select(Case).where(Case.status != "closed").order_by(desc(Case.created_at)).limit(100)
        result = await db.execute(stmt)
        return result.scalars().all()
