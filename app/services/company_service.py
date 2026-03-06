"""Company service"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.models.company import Company, CompanyAPIKey
from app.models.product import Product, ProductCategory


class CompanyService:
    """Company and product management"""
    
    @staticmethod
    async def create_company(db: AsyncSession, company_data: dict) -> Company:
        """Register company"""
        company = Company(
            name=company_data.get("name"),
            registration_number=company_data.get("registration_number"),
            email=company_data.get("email"),
            phone=company_data.get("phone"),
            address=company_data.get("address"),
            status="pending",  # Needs NAFDAC verification
            created_at=datetime.utcnow(),
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company
    
    
    @staticmethod
    async def get_company(db: AsyncSession, company_id: str) -> Optional[Company]:
        """Get company by ID"""
        return await db.get(Company, company_id)
    
    
    @staticmethod
    async def create_product(db: AsyncSession, company_id: str, product_data: dict) -> Product:
        """Register product in NAFDAC registry"""
        product = Product(
            company_id=company_id,
            nafdac_number=product_data.get("nafdac_number"),
            name=product_data.get("name"),
            manufacturer=product_data.get("manufacturer"),
            description=product_data.get("description"),
            is_approved=product_data.get("is_approved", False),
            created_at=datetime.utcnow(),
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    
    
    @staticmethod
    async def get_products(db: AsyncSession, company_id: str, limit: int = 50, offset: int = 0) -> tuple[List[Product], int]:
        """Get company products"""
        stmt = select(Product).where(Product.company_id == company_id).order_by(desc(Product.created_at)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        products = result.scalars().all()
        
        # Count
        count_stmt = select(func.count()).select_from(Product).where(Product.company_id == company_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        return products, total
    
    
    @staticmethod
    async def generate_api_key(db: AsyncSession, company_id: str, key_name: str) -> CompanyAPIKey:
        """Generate API key for server-to-server integration"""
        import secrets
        
        api_key = CompanyAPIKey(
            company_id=company_id,
            key_name=key_name,
            api_key=f"key_{secrets.token_urlsafe(32)}",
            created_at=datetime.utcnow(),
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key
    
    
    @staticmethod
    async def verify_api_key(db: AsyncSession, api_key: str) -> Optional[str]:
        """Verify API key and return company ID"""
        stmt = select(CompanyAPIKey).where(CompanyAPIKey.api_key == api_key)
        result = await db.execute(stmt)
        key_record = result.scalars().first()
        
        if key_record:
            return str(key_record.company_id)
        return None
