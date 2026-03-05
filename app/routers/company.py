"""Company routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.utils.response import success_response, paginated_response
from app.utils.dependencies import get_current_user
from app.services.company_service import CompanyService
from app.schemas.company import CompanyRegistrationRequest, ProductCreateRequest

router = APIRouter()


@router.post("/register", status_code=201)
async def register_company(req: CompanyRegistrationRequest, db: AsyncSession = Depends(get_db)):
    """Register new company"""
    try:
        company = await CompanyService.create_company(db, req.dict())
        return success_response({"id": str(company.id), "name": company.name, "status": company.status}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/profile")
async def get_company_profile(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get company profile"""
    try:
        company = await CompanyService.get_company(db, str(current_user.company_id or current_user.id))
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return success_response({
            "id": str(company.id),
            "name": company.name,
            "email": company.email,
            "phone": company.phone,
            "status": company.status,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Products
@router.post("/products", status_code=201)
async def register_product(
    req: ProductCreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register product"""
    try:
        product = await CompanyService.create_product(db, str(current_user.company_id or current_user.id), req.dict())
        return success_response({"id": str(product.id), "name": product.name, "nafdac_number": product.nafdac_number}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products")
async def get_products(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get company products"""
    try:
        offset = (page - 1) * limit
        products, total = await CompanyService.get_products(db, str(current_user.company_id or current_user.id), limit, offset)
        items = [{"id": str(p.id), "name": p.name, "nafdac_number": p.nafdac_number, "is_approved": p.is_approved} for p in products]
        return paginated_response(items, total, page, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# API Keys
@router.post("/api-keys")
async def generate_api_key(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    key_name: str = Query("default")
):
    """Generate API key for integration"""
    try:
        api_key = await CompanyService.generate_api_key(db, str(current_user.company_id or current_user.id), key_name)
        return success_response({"api_key": api_key.api_key, "created_at": api_key.created_at})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard")
async def get_dashboard(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get company dashboard"""
    return success_response({
        "total_scans": 1250,
        "authentic_count": 1150,
        "caution_count": 75,
        "counterfeit_count": 25,
        "this_week_scans": 180,
    })


# Team & Billing
@router.get("/team")
async def get_team_members(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/team")
async def invite_team_member(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/team/{user_id}")
async def update_team_member(user_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/team/{user_id}")
async def remove_team_member(user_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/billing")
async def get_billing(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/billing")
async def update_billing(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/subscription")
async def get_subscription(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/subscription")
async def update_subscription(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Dashboard
@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/dashboard/kpi")
async def get_kpi_cards(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/dashboard/trends")
async def get_trends(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/dashboard/states")
async def get_top_states(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/dashboard/recent-alerts")
async def get_recent_alerts(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/dashboard/quick-stats")
async def get_quick_stats(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Products
@router.get("/products")
async def get_products(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/products/{product_id}")
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/products")
async def create_product(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/products/{product_id}")
async def update_product(product_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/products/upload")
async def upload_product_image(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/products/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/products/stats")
async def get_product_stats(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Reports & Alerts
@router.get("/reports")
async def get_reports(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/reports/{report_id}")
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/reports/filter")
async def filter_reports(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/reports/stats")
async def get_reports_stats(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.patch("/reports/{report_id}/status")
async def update_report_status(report_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/reports/export")
async def export_reports(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.patch("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.patch("/alerts/read-all")
async def mark_all_alerts_read(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Evidence Vault
@router.get("/evidence")
async def get_evidence(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/evidence/{case_id}")
async def get_evidence_case(case_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/evidence/{case_id}/files")
async def get_evidence_files(case_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/evidence/{case_id}/download")
async def download_evidence(case_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/evidence/{case_id}/zip")
async def create_evidence_zip(case_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/evidence/stats")
async def get_evidence_stats(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Heatmap
@router.get("/heatmap")
async def get_heatmap(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/heatmap/regions")
async def get_heatmap_regions(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/heatmap/coordinates")
async def get_heatmap_coordinates(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/heatmap/filter")
async def filter_heatmap(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/heatmap/export")
async def export_heatmap(db: AsyncSession = Depends(get_db)):
    return success_response({})


# Settings
@router.get("/settings")
async def get_company_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/notifications")
async def update_notification_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/security")
async def update_security_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/api")
async def update_api_settings(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.get("/settings/api-keys")
async def get_api_keys(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/settings/api-keys")
async def create_api_key(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/settings/api-keys/{key_id}")
async def revoke_api_key(key_id: str, db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.put("/settings/webhooks")
async def update_webhooks(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.post("/settings/test-webhook")
async def test_webhook(db: AsyncSession = Depends(get_db)):
    return success_response({})


@router.delete("/settings/account")
async def delete_company_account(db: AsyncSession = Depends(get_db)):
    return success_response({})
