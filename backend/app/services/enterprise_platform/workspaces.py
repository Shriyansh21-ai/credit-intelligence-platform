"""M2 — Enterprise Workspace Platform.

Personal / team / department / organization / shared workspaces, each holding
pinned dashboards, saved reports, shared views, collections, bookmarks and
templates, plus members and per-workspace analytics. Deterministic and multi-
tenant. Backed by ``ent_workspaces``, ``ent_workspace_members`` and
``ent_workspace_items``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import (
    EntWorkspace, EntWorkspaceItem, EntWorkspaceMember,
)
from .common import iso, slugify, utcnow

WORKSPACE_TYPES = ["personal", "team", "department", "organization", "shared"]
ITEM_TYPES = ["pinned_dashboard", "saved_report", "shared_view", "collection",
              "bookmark", "template"]
MEMBER_ROLES = ["owner", "admin", "member", "viewer"]


def create_workspace(db: Session, *, name: str, workspace_type: str = "personal",
                     description: Optional[str] = None, owner_ref: Optional[str] = None,
                     settings: Optional[dict] = None, key: Optional[str] = None,
                     tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    if workspace_type not in WORKSPACE_TYPES:
        raise ValueError(f"unknown workspace_type '{workspace_type}'")
    key = key or slugify(name)
    if db.query(EntWorkspace).filter(EntWorkspace.tenant_id == tenant_id,
                                     EntWorkspace.key == key).first():
        raise ValueError(f"workspace '{key}' already exists")
    row = EntWorkspace(tenant_id=tenant_id, key=key, name=name, workspace_type=workspace_type,
                       description=description, owner_ref=owner_ref or created_by,
                       settings=settings or {}, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    # Owner is a member by default.
    if row.owner_ref:
        db.add(EntWorkspaceMember(workspace_id=row.id, user_ref=row.owner_ref, role="owner"))
        db.commit()
    return {"workspace_id": row.id, "key": row.key, "name": row.name,
            "workspace_type": row.workspace_type}


def list_workspaces(db: Session, *, workspace_type: Optional[str] = None,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntWorkspace)
    if tenant_id is not None:
        q = q.filter(EntWorkspace.tenant_id == tenant_id)
    if workspace_type:
        q = q.filter(EntWorkspace.workspace_type == workspace_type)
    return [{"workspace_id": w.id, "key": w.key, "name": w.name,
             "workspace_type": w.workspace_type, "owner_ref": w.owner_ref,
             "created_at": iso(w.created_at)}
            for w in q.order_by(EntWorkspace.id.desc()).all()]


def get_workspace(db: Session, workspace_id: int) -> Optional[Dict[str, Any]]:
    w = db.query(EntWorkspace).filter(EntWorkspace.id == workspace_id).first()
    if not w:
        return None
    members = db.query(EntWorkspaceMember).filter(EntWorkspaceMember.workspace_id == w.id).all()
    items = db.query(EntWorkspaceItem).filter(EntWorkspaceItem.workspace_id == w.id).all()
    return {"workspace_id": w.id, "key": w.key, "name": w.name, "workspace_type": w.workspace_type,
            "description": w.description, "owner_ref": w.owner_ref, "settings": w.settings,
            "members": [{"user_ref": m.user_ref, "role": m.role} for m in members],
            "items": [{"item_id": i.id, "item_type": i.item_type, "title": i.title, "ref": i.ref}
                      for i in items]}


def add_member(db: Session, *, workspace_id: int, user_ref: str, role: str = "member") -> Dict[str, Any]:
    if role not in MEMBER_ROLES:
        raise ValueError(f"unknown role '{role}'")
    if not db.query(EntWorkspace).filter(EntWorkspace.id == workspace_id).first():
        raise ValueError("workspace not found")
    existing = (db.query(EntWorkspaceMember)
                .filter(EntWorkspaceMember.workspace_id == workspace_id,
                        EntWorkspaceMember.user_ref == user_ref).first())
    if existing:
        existing.role = role
        db.commit()
        return {"workspace_id": workspace_id, "user_ref": user_ref, "role": role, "updated": True}
    db.add(EntWorkspaceMember(workspace_id=workspace_id, user_ref=user_ref, role=role))
    db.commit()
    return {"workspace_id": workspace_id, "user_ref": user_ref, "role": role, "updated": False}


def add_item(db: Session, *, workspace_id: int, item_type: str, title: str, ref: Optional[str] = None,
             payload: Optional[dict] = None, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None) -> Dict[str, Any]:
    if item_type not in ITEM_TYPES:
        raise ValueError(f"unknown item_type '{item_type}'")
    if not db.query(EntWorkspace).filter(EntWorkspace.id == workspace_id).first():
        raise ValueError("workspace not found")
    row = EntWorkspaceItem(tenant_id=tenant_id, workspace_id=workspace_id, item_type=item_type,
                           title=title, ref=ref, payload=payload or {}, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"item_id": row.id, "workspace_id": workspace_id, "item_type": item_type, "title": title}


def list_items(db: Session, *, workspace_id: int, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
    q = db.query(EntWorkspaceItem).filter(EntWorkspaceItem.workspace_id == workspace_id)
    if item_type:
        q = q.filter(EntWorkspaceItem.item_type == item_type)
    return [{"item_id": i.id, "item_type": i.item_type, "title": i.title, "ref": i.ref,
             "payload": i.payload, "created_at": iso(i.created_at)}
            for i in q.order_by(EntWorkspaceItem.id.desc()).all()]


def analytics(db: Session, *, workspace_id: int) -> Dict[str, Any]:
    """Per-workspace analytics: member and item counts by type."""
    if not db.query(EntWorkspace).filter(EntWorkspace.id == workspace_id).first():
        raise ValueError("workspace not found")
    members = db.query(EntWorkspaceMember).filter(EntWorkspaceMember.workspace_id == workspace_id).count()
    items = db.query(EntWorkspaceItem).filter(EntWorkspaceItem.workspace_id == workspace_id).all()
    by_type: Dict[str, int] = {}
    for i in items:
        by_type[i.item_type] = by_type.get(i.item_type, 0) + 1
    return {"workspace_id": workspace_id, "member_count": members, "item_count": len(items),
            "items_by_type": by_type, "generated_at": iso(utcnow())}
