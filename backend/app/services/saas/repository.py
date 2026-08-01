"""Tenant-aware repository base.

Every read/write against a tenant-scoped table goes through a
:class:`TenantRepository`. It

* auto-filters every query by the active tenant (from :mod:`context` or an
  explicit ``tenant_id``)
* stamps ``tenant_id`` on inserts
* guards fetch-by-id against cross-tenant access (returns ``None`` / raises
  rather than leaking another tenant's row).

Models are expected to expose a ``tenant_id`` column. This is the single
choke-point that makes cross-tenant access structurally hard rather than a
matter of remembering a ``WHERE`` clause in each route.
"""

from __future__ import annotations

from typing import Generic, Iterable, List, Optional, Type, TypeVar

from sqlalchemy.orm import Query, Session

from backend.app.services.saas.context import (
    TenantContextError,
    current_tenant_id,
)

T = TypeVar("T")


class CrossTenantAccessError(TenantContextError):
    """Raised when a caller tries to touch a row owned by another tenant."""


class TenantRepository(Generic[T]):
    def __init__(self, db: Session, model: Type[T], tenant_id: Optional[int] = None):
        self.db = db
        self.model = model
        # Explicit tenant wins; otherwise fall back to the ambient context.
        self._tenant_id = tenant_id if tenant_id is not None else current_tenant_id()

    # -- scope ----------------------------------------------------------
    @property
    def tenant_id(self) -> int:
        if self._tenant_id is None:
            raise TenantContextError(
                f"{self.model.__name__} access requires a tenant scope"
            )
        return self._tenant_id

    def query(self) -> Query:
        return self.db.query(self.model).filter(
            self.model.tenant_id == self.tenant_id
        )

    # -- reads ----------------------------------------------------------
    def all(self, order_by=None) -> List[T]:
        q = self.query()
        if order_by is not None:
            q = q.order_by(order_by)
        return q.all()

    def get(self, obj_id: int) -> Optional[T]:
        """Fetch by primary key, scoped to the tenant (None if not owned)."""
        return self.query().filter(self.model.id == obj_id).first()

    def get_or_403(self, obj_id: int) -> T:
        obj = self.get(obj_id)
        if obj is None:
            raise CrossTenantAccessError(
                f"{self.model.__name__} {obj_id} not found in tenant {self.tenant_id}"
            )
        return obj

    def filter_by(self, **kwargs) -> List[T]:
        return self.query().filter_by(**kwargs).all()

    def first_by(self, **kwargs) -> Optional[T]:
        return self.query().filter_by(**kwargs).first()

    def count(self) -> int:
        return self.query().count()

    # -- writes ---------------------------------------------------------
    def add(self, obj: T, *, flush: bool = True) -> T:
        # Stamp / verify tenant ownership on the way in.
        existing = getattr(obj, "tenant_id", None)
        if existing is None:
            setattr(obj, "tenant_id", self.tenant_id)
        elif existing != self.tenant_id:
            raise CrossTenantAccessError(
                f"Refusing to persist {self.model.__name__} for tenant "
                f"{existing} under active tenant {self.tenant_id}"
            )
        self.db.add(obj)
        if flush:
            self.db.flush()
        return obj

    def add_all(self, objs: Iterable[T]) -> List[T]:
        return [self.add(o, flush=False) for o in objs]

    def delete(self, obj: T) -> None:
        if getattr(obj, "tenant_id", None) != self.tenant_id:
            raise CrossTenantAccessError("Refusing cross-tenant delete")
        self.db.delete(obj)
