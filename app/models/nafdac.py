"""NAFDAC case and enforcement models"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, TEXT, Integer, Index, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class CaseStatus(str, enum.Enum):
    PENDING = "pending"
    INVESTIGATING = "investigating"
    UNDER_REVIEW = "under_review"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Priority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EnforcementActionType(str, enum.Enum):
    RAID = "raid"
    SEIZURE = "seizure"
    NOTICE = "notice"
    SUSPENSION = "suspension"
    PROSECUTION = "prosecution"
    OTHER = "other"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Case(Base):
    """NAFDAC Cases (investigation records)"""
    __tablename__ = "cases"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_number = Column(String(100), unique=True, nullable=False)
    report_id = Column(String(36))  # FK to reports
    assigned_to = Column(String(36))  # FK to users
    case_status = Column(SQLEnum(CaseStatus), default=CaseStatus.PENDING, nullable=False)
    priority = Column(SQLEnum(Priority), default=Priority.MEDIUM)
    description = Column(TEXT)
    officer_notes = Column(TEXT)
    location = Column(String)  # GEOGRAPHY(POINT)
    location_name = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime)
    
    __table_args__ = (
        Index("idx_cases_status", "case_status"),
        Index("idx_cases_assigned_to", "assigned_to"),
        Index("idx_cases_report", "report_id"),
        Index("idx_cases_created", "created_at"),
    )


class EnforcementAction(Base):
    """Enforcement actions (raids, seizures, notices)"""
    __tablename__ = "enforcement_actions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id = Column(String(36), nullable=False)  # FK to cases
    action_type = Column(SQLEnum(EnforcementActionType), nullable=False)
    description = Column(TEXT)
    location = Column(String)  # GEOGRAPHY(POINT)
    location_name = Column(String(255))
    executed_by = Column(String(36))  # FK to users
    execution_date = Column(DateTime)
    quantity_seized = Column(Integer)
    seized_items_description = Column(TEXT)
    evidence_files = Column(String)  # Array
    action_status = Column(SQLEnum(ActionStatus), default=ActionStatus.PENDING)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index("idx_enforcement_case", "case_id"),
        Index("idx_enforcement_type", "action_type"),
        Index("idx_enforcement_status", "action_status"),
    )
