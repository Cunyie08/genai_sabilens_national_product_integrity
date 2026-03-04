"""Report service"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.scan import Report, ReportEvidence
from app.models.alert import Alert


class ReportService:
    """Counterfeit report management"""
    
    @staticmethod
    async def create_report(db: AsyncSession, user_id: str, scan_id: str, description: str) -> Report:
        """Create counterfeit report"""
        report = Report(
            user_id=user_id,
            scan_id=scan_id,
            description=description,
            status="open",
            severity="high",
            created_at=datetime.utcnow(),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        
        # Create alert for NAFDAC
        alert = Alert(
            report_id=report.id,
            alert_type="counterfeit_detected",
            severity="high",
            message=f"Counterfeit product reported: {description}",
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        await db.commit()
        
        return report
    
    
    @staticmethod
    async def add_evidence(db: AsyncSession, report_id: str, evidence_data: dict) -> ReportEvidence:
        """Add evidence to report (photos, videos, documents)"""
        evidence = ReportEvidence(
            report_id=report_id,
            evidence_type=evidence_data.get("type"),  # photo, video, document
            file_url=evidence_data.get("file_url"),
            description=evidence_data.get("description"),
            created_at=datetime.utcnow(),
        )
        db.add(evidence)
        await db.commit()
        await db.refresh(evidence)
        return evidence
    
    
    @staticmethod
    async def get_report(db: AsyncSession, report_id: str) -> Optional[Report]:
        """Get report by ID"""
        return await db.get(Report, report_id)
    
    
    @staticmethod
    async def get_user_reports(db: AsyncSession, user_id: str, limit: int = 20, offset: int = 0) -> tuple[List[Report], int]:
        """Get user's reports"""
        from sqlalchemy import func
        
        stmt = select(Report).where(Report.user_id == user_id).order_by(desc(Report.created_at)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        reports = result.scalars().all()
        
        # Count total
        count_stmt = select(func.count()).select_from(Report).where(Report.user_id == user_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        return reports, total
    
    
    @staticmethod
    async def update_report_status(db: AsyncSession, report_id: str, status: str) -> Report:
        """Update report status (open -> investigating -> resolved -> closed)"""
        report = await db.get(Report, report_id)
        if not report:
            raise ValueError("Report not found")
        
        report.status = status
        report.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(report)
        return report
    
    
    @staticmethod
    async def get_hotspot_reports(db: AsyncSession, latitude: float, longitude: float, radius_km: float = 5) -> List[Report]:
        """Get reports near a location (for hotspot analysis)"""
        from sqlalchemy.sql import func as sql_func
        from geoalchemy2 import functions as geo_func
        
        # Mock: In production, use PostGIS for proximity search
        stmt = select(Report).order_by(desc(Report.created_at)).limit(50)
        result = await db.execute(stmt)
        return result.scalars().all()
