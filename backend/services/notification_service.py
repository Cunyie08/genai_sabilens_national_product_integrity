"""
Notification Service — Barrister Femi
Handles notification creation, dispatch, and preference management.
Used by NAFDAC broadcast, alert generation, and system events.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.alert import Alert, Notification, NotificationPreference
from backend.models.user import User


class NotificationService:
    """
    All methods are static async — they accept a db session and operate on it.
    Callers are responsible for committing the session.
    """

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[dict] = None
    ) -> Notification:
        """Create a single notification for a user."""
        notif = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data
        )
        db.add(notif)
        await db.flush()
        return notif

    @staticmethod
    async def broadcast_to_all_companies(
        db: AsyncSession,
        title: str,
        message: str,
        severity: Optional[str] = None
    ) -> int:
        """
        Send a notification to all company_admin users.
        Returns count of notifications created.
        """
        stmt = select(User).where(
            and_(
                User.role == "company_admin",
                User.status == "active",
                User.deleted_at.is_(None)
            )
        )
        result = await db.execute(stmt)
        admins = result.scalars().all()

        count = 0
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                notification_type="system",
                title=title,
                message=message,
                data={"severity": severity} if severity else None
            )
            db.add(notif)
            count += 1

        await db.flush()
        return count

    @staticmethod
    async def send_to_company(
        db: AsyncSession,
        company_id: uuid.UUID,
        title: str,
        message: str
    ) -> int:
        """Send notification to all admins of a specific company."""
        stmt = select(User).where(
            and_(
                User.company_id == company_id,
                User.role == "company_admin",
                User.status == "active",
                User.deleted_at.is_(None)
            )
        )
        result = await db.execute(stmt)
        admins = result.scalars().all()

        count = 0
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                notification_type="alert",
                title=title,
                message=message,
                data={"company_id": str(company_id)}
            )
            db.add(notif)
            count += 1

        await db.flush()
        return count

    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False
    ) -> tuple:
        """Return (notifications_list, total_count)."""
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read == False)

        count_stmt = select(func.count(Notification.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        notifications = result.scalars().all()

        return notifications, total

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Mark notifications as read. If no IDs provided, mark all for user."""
        conditions = [Notification.user_id == user_id]
        if notification_ids:
            conditions.append(Notification.id.in_(notification_ids))

        stmt = (
            update(Notification)
            .where(and_(*conditions))
            .values(is_read=True, read_at=datetime.utcnow())
        )
        result = await db.execute(stmt)
        return result.rowcount

    @staticmethod
    async def get_preferences(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[NotificationPreference]:
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_preference(
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_type: str,
        channel: str,
        enabled: bool
    ) -> NotificationPreference:
        """Upsert a notification preference."""
        stmt = select(NotificationPreference).where(
            and_(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
                NotificationPreference.channel == channel
            )
        )
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref:
            pref.enabled = enabled
            pref.updated_at = datetime.utcnow()
        else:
            pref = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
                channel=channel,
                enabled=enabled
            )
            db.add(pref)

        await db.flush()
        return pref

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        company_id: Optional[uuid.UUID],
        report_id: Optional[uuid.UUID],
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metadata: Optional[dict] = None
    ) -> Alert:
        """Create an alert record (used by scan pipeline and report system)."""
        alert = Alert(
            company_id=company_id,
            report_id=report_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            metadata_=metadata
        )
        db.add(alert)
        await db.flush()
        return alert
