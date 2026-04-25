"""Response utilities."""
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi.responses import JSONResponse


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles types stdlib json cannot serialize."""
    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _dumps(content: Any) -> bytes:
    return json.dumps(content, cls=_SafeEncoder, separators=(",", ":")).encode("utf-8")


class _SafeJSONResponse(JSONResponse):
    """JSONResponse that uses _SafeEncoder for serialization."""
    def render(self, content: Any) -> bytes:
        return _dumps(content)


def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> JSONResponse:
    """Standard success response."""
    return _SafeJSONResponse(
        status_code=status_code,
        content={"success": True, "data": data, "message": message},
    )


def error_response(
    message: str,
    code: str = "ERROR",
    status_code: int = 400,
    details: Optional[dict] = None,
) -> JSONResponse:
    """Standard error response."""
    return _SafeJSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "code": code,
            "details": details or {},
        },
    )


def paginated_response(
    data: Any,
    page: int,
    limit: int,
    total: int,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    """Paginated response."""
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return _SafeJSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "message": message,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
    )
