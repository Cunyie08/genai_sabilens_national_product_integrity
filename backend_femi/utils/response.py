"""
Response utilities — owned by tunjipaul.
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data, "message": message}
    )


def error_response(message: str, code: str = "ERROR", status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "message": message, "code": code}
    )


def paginated_response(
    data: Any,
    page: int,
    limit: int,
    total: int,
    message: str = "Success",
    status_code: int = 200
) -> JSONResponse:
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return JSONResponse(
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
                "has_prev": page > 1
            }
        }
    )
