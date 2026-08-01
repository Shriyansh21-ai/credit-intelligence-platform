"""Pagination + streaming helpers.

Standardises list-endpoint pagination and large-result streaming without
changing any existing endpoint

* :func:`paginate` — bounded **offset** pagination returning a typed
  :class:`Page` (with total + navigation metadata).
* :func:`keyset_paginate` — **keyset / seek** pagination for deep, stable paging
  over large tables (avoids the O(N) cost of large OFFSETs).
* :func:`stream_ndjson` — memory-bounded NDJSON streaming for large exports.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from fastapi.responses import StreamingResponse

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def clamp_page_size(
    size: int | None, *, default: int = DEFAULT_PAGE_SIZE, maximum: int = MAX_PAGE_SIZE
) -> int:
    if not size or size < 1:
        return default
    return min(size, maximum)


@dataclass
class Page[T]:
    """A single page of results plus navigation metadata."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "pagination": {
                "total": self.total,
                "page": self.page,
                "page_size": self.page_size,
                "pages": self.pages,
                "has_next": self.has_next,
                "has_prev": self.has_prev,
            },
        }


def paginate(query: Any, *, page: int = 1, page_size: int | None = None) -> Page:
    """Offset-paginate a SQLAlchemy ``Query`` into a :class:`Page`.

    Issues one ``count()`` and one windowed ``all()``. Prefer
    :func:`keyset_paginate` for very deep paging.
    """
    size = clamp_page_size(page_size)
    page = max(1, page)
    total = query.order_by(None).count()
    items = query.limit(size).offset((page - 1) * size).all()
    return Page(items=items, total=total, page=page, page_size=size)


@dataclass
class KeysetPage[T]:
    items: list[T]
    next_cursor: Any | None
    page_size: int
    has_next: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "pagination": {
                "next_cursor": self.next_cursor,
                "page_size": self.page_size,
                "has_next": self.has_next,
            },
        }


def keyset_paginate(
    query: Any,
    *,
    order_column: Any,
    page_size: int | None = None,
    after: Any | None = None,
    descending: bool = False,
) -> KeysetPage:
    """Seek-paginate using a monotonic ``order_column`` (e.g. an id / created_at).

    ``after`` is the last cursor value from the previous page. One extra row is
    fetched to compute ``has_next`` cheaply.
    """
    size = clamp_page_size(page_size)
    q = query
    if after is not None:
        q = q.filter(order_column < after) if descending else q.filter(order_column > after)
    q = q.order_by(order_column.desc() if descending else order_column.asc())
    rows = q.limit(size + 1).all()
    has_next = len(rows) > size
    rows = rows[:size]
    next_cursor = None
    if has_next and rows:
        last = rows[-1]
        # Resolve the cursor value from the ORM entity attribute.
        col_name = getattr(order_column, "key", None) or getattr(order_column, "name", None)
        next_cursor = getattr(last, col_name, None) if col_name else None
    return KeysetPage(items=rows, next_cursor=next_cursor, page_size=size, has_next=has_next)


def stream_ndjson(rows: Iterable[Any], *, serialize: Any = None) -> StreamingResponse:
    """Stream an iterable as newline-delimited JSON (one object per line).

    Memory-bounded: rows are serialized and yielded lazily, so a million-row
    export never materialises in memory.
    """
    serialize = serialize or (lambda r: r)

    def _gen() -> Iterator[bytes]:
        for row in rows:
            yield (json.dumps(serialize(row), default=str) + "\n").encode("utf-8")

    return StreamingResponse(_gen(), media_type="application/x-ndjson")


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "KeysetPage",
    "Page",
    "clamp_page_size",
    "keyset_paginate",
    "paginate",
    "stream_ndjson",
]
