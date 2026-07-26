"""M4 — Loan Committee Workspace.

Collaborative committee review: standing committees with members and a quorum,
convened meetings with attendance and agendas, one decision item per application,
weighted voting with tamper-evident digital signatures, auto-generated minutes
and committee analytics. Deterministic tallying — the decision follows the
weighted vote against the committee's quorum, never an opaque model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import (
    AgendaItem, Committee, CommitteeMeeting, CommitteeVote,
)
from .common import signature

VOTE_KINDS = ["approve", "reject", "abstain", "defer"]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Committees
# ---------------------------------------------------------------------------
def create_committee(db: Session, *, name: str, description: Optional[str] = None,
                     quorum: int = 1, members: Optional[list] = None,
                     tenant_id: Optional[int] = None) -> Committee:
    c = Committee(tenant_id=tenant_id, name=name, description=description,
                  quorum=max(1, int(quorum)), members=members or [])
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_committees(db: Session, *, tenant_id: Optional[int] = None) -> List[Committee]:
    return (db.query(Committee).filter(Committee.tenant_id == tenant_id)
            .order_by(Committee.name).all())


def get_committee(db: Session, committee_id: int) -> Optional[Committee]:
    return db.query(Committee).filter(Committee.id == committee_id).first()


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------
def create_meeting(db: Session, *, committee_id: int, title: str,
                   scheduled_at: Optional[str] = None, location: Optional[str] = None,
                   chair: Optional[str] = None, tenant_id: Optional[int] = None) -> CommitteeMeeting:
    committee = get_committee(db, committee_id)
    if committee is None:
        raise ValueError("committee not found")
    m = CommitteeMeeting(tenant_id=tenant_id, committee_id=committee_id, title=title,
                         scheduled_at=_parse_dt(scheduled_at), location=location, chair=chair,
                         status="scheduled", attendees=[])
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def get_meeting(db: Session, meeting_id: int) -> Optional[CommitteeMeeting]:
    return db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()


def list_meetings(db: Session, *, committee_id: Optional[int] = None,
                  status: Optional[str] = None, tenant_id: Optional[int] = None) -> List[CommitteeMeeting]:
    q = db.query(CommitteeMeeting).filter(CommitteeMeeting.tenant_id == tenant_id)
    if committee_id is not None:
        q = q.filter(CommitteeMeeting.committee_id == committee_id)
    if status:
        q = q.filter(CommitteeMeeting.status == status)
    return q.order_by(CommitteeMeeting.created_at.desc()).all()


def open_meeting(db: Session, meeting_id: int) -> CommitteeMeeting:
    m = get_meeting(db, meeting_id)
    if m is None:
        raise ValueError("meeting not found")
    if m.status == "closed":
        raise ValueError("meeting already closed")
    m.status = "in_session"
    m.opened_at = datetime.utcnow()
    db.commit()
    db.refresh(m)
    return m


def close_meeting(db: Session, meeting_id: int) -> Dict[str, Any]:
    m = get_meeting(db, meeting_id)
    if m is None:
        raise ValueError("meeting not found")
    m.status = "closed"
    m.closed_at = datetime.utcnow()
    # Auto-generate minutes if none were entered.
    if not m.minutes:
        m.minutes = _auto_minutes(db, m)
    db.commit()
    db.refresh(m)
    return meeting_detail(db, m)


def mark_attendance(db: Session, meeting_id: int, *, user_id: Optional[int], name: str,
                    present: bool = True) -> CommitteeMeeting:
    m = get_meeting(db, meeting_id)
    if m is None:
        raise ValueError("meeting not found")
    # Rebuild with fresh dicts so SQLAlchemy detects the JSON mutation.
    now = datetime.utcnow().isoformat()
    attendees = []
    found = False
    for a in (m.attendees or []):
        if not found and ((user_id is not None and a.get("user_id") == user_id)
                          or a.get("name") == name):
            attendees.append({"user_id": user_id, "name": name, "present": present,
                              "joined_at": now})
            found = True
        else:
            attendees.append(dict(a))
    if not found:
        attendees.append({"user_id": user_id, "name": name, "present": present,
                          "joined_at": now})
    m.attendees = attendees
    db.commit()
    db.refresh(m)
    return m


def set_minutes(db: Session, meeting_id: int, minutes: str) -> CommitteeMeeting:
    m = get_meeting(db, meeting_id)
    if m is None:
        raise ValueError("meeting not found")
    m.minutes = minutes
    db.commit()
    db.refresh(m)
    return m


# ---------------------------------------------------------------------------
# Agenda + voting
# ---------------------------------------------------------------------------
def add_agenda_item(db: Session, *, meeting_id: int, title: str, subject_ref: Optional[str] = None,
                    assessment_id: Optional[int] = None, presenter: Optional[str] = None,
                    summary: Optional[str] = None, proposed_action: Optional[str] = None,
                    amount: Optional[float] = None, materials: Optional[list] = None,
                    order_no: Optional[int] = None, tenant_id: Optional[int] = None) -> AgendaItem:
    m = get_meeting(db, meeting_id)
    if m is None:
        raise ValueError("meeting not found")
    if order_no is None:
        order_no = db.query(AgendaItem).filter(AgendaItem.meeting_id == meeting_id).count() + 1
    i = AgendaItem(tenant_id=tenant_id, meeting_id=meeting_id, title=title,
                   subject_ref=subject_ref, assessment_id=assessment_id, presenter=presenter,
                   summary=summary, proposed_action=proposed_action, amount=amount,
                   materials=materials or [], order_no=order_no, status="pending")
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def get_agenda_item(db: Session, item_id: int) -> Optional[AgendaItem]:
    return db.query(AgendaItem).filter(AgendaItem.id == item_id).first()


def cast_vote(db: Session, item_id: int, *, vote: str, rationale: Optional[str] = None,
              voter_user_id: Optional[int] = None, voter_name: Optional[str] = None,
              weight: float = 1.0, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if vote not in VOTE_KINDS:
        raise ValueError(f"vote must be one of {VOTE_KINDS}")
    item = get_agenda_item(db, item_id)
    if item is None:
        raise ValueError("agenda item not found")
    meeting = get_meeting(db, item.meeting_id)
    if meeting and meeting.status == "closed":
        raise ValueError("meeting is closed")
    # One vote per member: update in place if they already voted.
    existing = None
    if voter_user_id is not None:
        existing = (db.query(CommitteeVote)
                    .filter(CommitteeVote.agenda_item_id == item_id,
                            CommitteeVote.voter_user_id == voter_user_id).first())
    sig = signature(item_id, voter_user_id, voter_name, vote, weight)
    if existing:
        existing.vote = vote
        existing.rationale = rationale
        existing.weight = weight
        existing.signature = sig
        row = existing
    else:
        row = CommitteeVote(tenant_id=tenant_id, agenda_item_id=item_id, meeting_id=item.meeting_id,
                            voter_user_id=voter_user_id, voter_name=voter_name, vote=vote,
                            weight=weight, rationale=rationale, signature=sig)
        db.add(row)
    db.commit()
    return {"vote_id": row.id, "signature": sig, "tally": tally(db, item_id)}


def tally(db: Session, item_id: int) -> Dict[str, Any]:
    item = get_agenda_item(db, item_id)
    if item is None:
        raise ValueError("agenda item not found")
    votes = db.query(CommitteeVote).filter(CommitteeVote.agenda_item_id == item_id).all()
    meeting = get_meeting(db, item.meeting_id)
    committee = get_committee(db, meeting.committee_id) if meeting else None
    quorum = committee.quorum if committee else 1

    weighted = {k: 0.0 for k in VOTE_KINDS}
    counts = {k: 0 for k in VOTE_KINDS}
    for v in votes:
        weighted[v.vote] = weighted.get(v.vote, 0.0) + (v.weight or 1.0)
        counts[v.vote] = counts.get(v.vote, 0) + 1

    voters = len(votes)
    quorum_met = voters >= quorum
    # Decisive weight excludes abstentions.
    approve_w, reject_w, defer_w = weighted["approve"], weighted["reject"], weighted["defer"]
    if not quorum_met:
        recommendation = "no_quorum"
    elif defer_w > approve_w and defer_w > reject_w:
        recommendation = "defer"
    elif approve_w > reject_w:
        recommendation = "approve"
    elif reject_w > approve_w:
        recommendation = "reject"
    else:
        recommendation = "tie_defer"
    return {
        "item_id": item_id, "voters": voters, "quorum": quorum, "quorum_met": quorum_met,
        "counts": counts, "weighted": {k: round(v, 3) for k, v in weighted.items()},
        "recommendation": recommendation,
        "signatures_valid": all(v.signature for v in votes),
    }


def finalize_decision(db: Session, item_id: int) -> Dict[str, Any]:
    item = get_agenda_item(db, item_id)
    if item is None:
        raise ValueError("agenda item not found")
    t = tally(db, item_id)
    if not t["quorum_met"]:
        raise ValueError(f"quorum not met ({t['voters']}/{t['quorum']})")
    rec = t["recommendation"]
    decision = {"approve": "approve", "reject": "reject"}.get(rec, "defer")
    item.decision = decision
    item.status = "decided" if decision != "defer" else "deferred"
    item.decision_rationale = (
        f"Committee {decision} — weighted approve {t['weighted']['approve']} vs "
        f"reject {t['weighted']['reject']} ({t['voters']} voters, quorum {t['quorum']}).")
    item.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return {"decision": decision, "item": agenda_dict(item), "tally": t}


# ---------------------------------------------------------------------------
# Minutes + analytics
# ---------------------------------------------------------------------------
def _auto_minutes(db: Session, meeting: CommitteeMeeting) -> str:
    items = db.query(AgendaItem).filter(AgendaItem.meeting_id == meeting.id).order_by(AgendaItem.order_no).all()
    present = [a.get("name") for a in (meeting.attendees or []) if a.get("present")]
    lines = [f"Minutes — {meeting.title}",
             f"Present: {', '.join(present) if present else 'n/a'}",
             f"Agenda items: {len(items)}"]
    for it in items:
        lines.append(f"  {it.order_no}. {it.title} — {it.decision or it.status}")
    return "\n".join(lines)


def analytics(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    meetings = db.query(CommitteeMeeting).filter(CommitteeMeeting.tenant_id == tenant_id).all()
    items = db.query(AgendaItem).filter(AgendaItem.tenant_id == tenant_id).all()
    decided = [i for i in items if i.decision]
    by_decision: Dict[str, int] = {}
    for i in decided:
        by_decision[i.decision] = by_decision.get(i.decision, 0) + 1
    approved = by_decision.get("approve", 0)
    return {
        "committees": db.query(Committee).filter(Committee.tenant_id == tenant_id).count(),
        "meetings": len(meetings),
        "meetings_closed": sum(1 for m in meetings if m.status == "closed"),
        "agenda_items": len(items),
        "decided": len(decided),
        "by_decision": by_decision,
        "approval_rate": round(approved / len(decided), 3) if decided else None,
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def committee_dict(c: Committee) -> Dict[str, Any]:
    return {"id": c.id, "name": c.name, "description": c.description, "quorum": c.quorum,
            "members": c.members, "is_active": c.is_active}


def meeting_dict(m: CommitteeMeeting) -> Dict[str, Any]:
    return {"id": m.id, "committee_id": m.committee_id, "title": m.title, "status": m.status,
            "location": m.location, "chair": m.chair, "attendees": m.attendees,
            "minutes": m.minutes,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
            "opened_at": m.opened_at.isoformat() if m.opened_at else None,
            "closed_at": m.closed_at.isoformat() if m.closed_at else None}


def agenda_dict(i: AgendaItem) -> Dict[str, Any]:
    return {"id": i.id, "meeting_id": i.meeting_id, "order_no": i.order_no, "title": i.title,
            "subject_ref": i.subject_ref, "assessment_id": i.assessment_id, "presenter": i.presenter,
            "summary": i.summary, "proposed_action": i.proposed_action, "amount": i.amount,
            "materials": i.materials, "status": i.status, "decision": i.decision,
            "decision_rationale": i.decision_rationale,
            "decided_at": i.decided_at.isoformat() if i.decided_at else None}


def meeting_detail(db: Session, m: CommitteeMeeting) -> Dict[str, Any]:
    items = db.query(AgendaItem).filter(AgendaItem.meeting_id == m.id).order_by(AgendaItem.order_no).all()
    agenda = []
    for it in items:
        votes = db.query(CommitteeVote).filter(CommitteeVote.agenda_item_id == it.id).all()
        agenda.append({**agenda_dict(it),
                       "votes": [{"voter_name": v.voter_name, "vote": v.vote, "weight": v.weight,
                                  "rationale": v.rationale, "signature": v.signature} for v in votes]})
    return {**meeting_dict(m), "agenda": agenda}
