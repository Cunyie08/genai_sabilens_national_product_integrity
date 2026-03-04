"""Consumer routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.utils.response import success_response, paginated_response
from app.utils.dependencies import get_current_user
from app.schemas.consumer import ScanCreateRequest, ScanResponse
from app.services.scan_service import ScanService

router = APIRouter()


@router.get("/profile")
async def get_profile(current_user = Depends(get_current_user)):
    """Get user profile"""
    return success_response({
        "id": str(current_user.id),
        "email": current_user.email,
        "phone": current_user.phone,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value,
        "status": current_user.status.value,
    })


@router.put("/profile")
async def update_profile(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update user profile"""
    return success_response({"message": "Profile updated"})


@router.get("/scans")
async def get_scans(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get user scan history"""
    try:
        offset = (page - 1) * limit
        scans, total = await ScanService.get_user_scans(db, str(current_user.id), limit, offset)
        
        items = [ScanResponse.from_orm(scan).dict() for scan in scans]
        return paginated_response(items, total, page, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get scan details"""
    try:
        scan = await ScanService.get_scan(db, scan_id)
        if not scan or str(scan.user_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return success_response(ScanResponse.from_orm(scan).dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan")
async def submit_scan(req: ScanCreateRequest, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Submit new scan"""
    try:
        scan = await ScanService.create_scan(db, str(current_user.id), req)
        return success_response(ScanResponse.from_orm(scan).dict(), status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete scan"""
    try:
        scan = await ScanService.get_scan(db, scan_id)
        if not scan or str(scan.user_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Scan not found")
        
        await db.delete(scan)
        await db.commit()
        return success_response({"message": "Scan deleted"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan/analyze")
async def analyze_scan(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/scan/result/{scan_id}")
async def get_scan_result(scan_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/scan/confirm")
async def confirm_scan(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Reporting
@router.post("/reports")
async def submit_report(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/reports/upload")
async def upload_report_evidence(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/reports/{report_id}")
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/reports/{report_id}")
async def update_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/reports/history")
async def get_reports_history(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Notifications
@router.get("/notifications")
async def get_notifications(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.patch("/notifications/read")
async def mark_notifications_read(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/notifications/settings")
async def get_notification_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/notifications/settings")
async def update_notification_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Settings
@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/language")
async def update_language(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/location")
async def update_location(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/privacy")
async def update_privacy(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/settings/data")
async def get_user_data(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/settings/data")
async def delete_user_data(db: AsyncSession = Depends(get_db)):
    return success_response({})
