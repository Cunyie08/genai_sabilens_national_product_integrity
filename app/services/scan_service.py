"""Scan service"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.models.scan import Scan, ScanAnalysis
from app.models.user import User
from app.schemas.consumer import ScanCreateRequest, ScanResponse
from app.models.product import Product


class ScanService:
    """Scan management service"""
    
    @staticmethod
    async def create_scan(db: AsyncSession, user_id: str, req: ScanCreateRequest) -> Scan:
        """Create new scan"""
        scan = Scan(
            user_id=user_id,
            product_id=req.product_id,
            image_url=req.image_url,
            barcode=req.barcode,
            latitude=req.latitude,
            longitude=req.longitude,
            location_text=req.location_text,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        return scan
    
    
    @staticmethod
    async def get_scan(db: AsyncSession, scan_id: str) -> Optional[Scan]:
        """Get scan by ID"""
        return await db.get(Scan, scan_id)
    
    
    @staticmethod
    @staticmethod
    async def get_user_scans(db: AsyncSession, user_id: str, limit: int = 20, offset: int = 0) -> tuple[List[Scan], int]:
        """Get user's scan history"""
        stmt = select(Scan).where(Scan.user_id == user_id).order_by(desc(Scan.created_at)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        scans = result.scalars().all()
        
        # Count total
        count_stmt = select(func.count()).select_from(Scan).where(Scan.user_id == user_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        return scans, total
    
    
    @staticmethod
    async def update_scan_status(db: AsyncSession, scan_id: str, status: str) -> Scan:
        """Update scan status (pending -> analyzing -> authentic/caution/fake)"""
        scan = await db.get(Scan, scan_id)
        if not scan:
            raise ValueError("Scan not found")
        
        scan.status = status
        scan.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(scan)
        return scan
    
    
    @staticmethod
    async def record_analysis(db: AsyncSession, scan_id: str, analysis_data: dict) -> ScanAnalysis:
        """Record AI analysis results"""
        analysis = ScanAnalysis(
            scan_id=scan_id,
            confidence_score=analysis_data.get("confidence_score", 0.0),
            visual_analysis=analysis_data.get("visual_analysis"),
            ocr_analysis=analysis_data.get("ocr_analysis"),
            regulatory_check=analysis_data.get("regulatory_check"),
            fusion_result=analysis_data.get("fusion_result"),
            risk_level=analysis_data.get("risk_level"),
            recommendation=analysis_data.get("recommendation"),
            created_at=datetime.utcnow(),
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis
