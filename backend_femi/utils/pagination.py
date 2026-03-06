"""
Pagination utilities — owned by tunjipaul.
"""


class Paginator:
    def __init__(self, page: int = 1, limit: int = 20):
        self.page = max(1, page)
        self.limit = min(max(1, limit), 100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
