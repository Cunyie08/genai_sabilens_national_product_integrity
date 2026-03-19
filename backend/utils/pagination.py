"""Pagination utilities."""
from typing import Tuple


def parse_pagination(page: int = 1, limit: int = 20) -> Tuple[int, int]:
    """Parse and validate pagination parameters, returning (skip, limit)."""
    page = max(1, page)
    limit = min(max(1, limit), 100)
    skip = (page - 1) * limit
    return skip, limit


class Paginator:
    """Object-oriented pagination helper."""

    def __init__(self, page: int = 1, limit: int = 20):
        self.page = max(1, page)
        self.limit = min(max(1, limit), 100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
