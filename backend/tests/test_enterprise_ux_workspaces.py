"""Track 4 M1 (UX) + M2 (Workspaces) tests."""

from backend.tests._enterprise_platform_helpers import admin_client


def test_preferences_and_layouts():
    _, client = admin_client()
    r = client.get("/api/ent/ux/preferences")
    assert r.json()["exists"] is False and r.json()["theme"] == "system"
    r = client.post("/api/ent/ux/preferences", json={"theme": "dark", "density": "compact"})
    assert r.json()["theme"] == "dark"
    r = client.get("/api/ent/ux/preferences")
    assert r.json()["exists"] is True and r.json()["theme"] == "dark"
    r = client.post("/api/ent/ux/preferences", json={"theme": "invalid"})
    assert r.status_code == 400
    r = client.post("/api/ent/ux/layouts", json={"name": "Trading View", "surface": "/fin-treasury",
                                                "config": {"panels": 3}, "is_default": True})
    assert r.json()["is_default"] is True
    r = client.get("/api/ent/ux/layouts")
    assert len(r.json()["layouts"]) == 1


def test_command_palette():
    _, client = admin_client()
    r = client.get("/api/ent/ux/commands")
    assert len(r.json()["commands"]) > 10
    r = client.get("/api/ent/ux/commands", params={"query": "treasury"})
    assert all("treasury" in c["label"].lower() or "treasury" in c["group"].lower()
               for c in r.json()["commands"])


def test_workspaces():
    _, client = admin_client()
    r = client.get("/api/ent/ux/../workspaces/types") if False else client.get("/api/ent/workspaces/types")
    assert "organization" in r.json()["workspace_types"]
    r = client.post("/api/ent/workspaces", json={"name": "Risk Team", "workspace_type": "team"})
    wid = r.json()["workspace_id"]
    r = client.post("/api/ent/workspaces/members", json={"workspace_id": wid, "user_ref": "bob@x.com",
                                                       "role": "member"})
    assert r.json()["role"] == "member"
    r = client.post("/api/ent/workspaces/items", json={"workspace_id": wid, "item_type": "pinned_dashboard",
                                                      "title": "Treasury KPIs", "ref": "/fin-treasury"})
    assert r.json()["item_type"] == "pinned_dashboard"
    r = client.get(f"/api/ent/workspaces/{wid}")
    assert len(r.json()["items"]) == 1 and len(r.json()["members"]) >= 1
    r = client.get(f"/api/ent/workspaces/{wid}/analytics")
    assert r.json()["item_count"] == 1


def test_workspace_duplicate_key_rejected():
    _, client = admin_client()
    client.post("/api/ent/workspaces", json={"name": "Dup", "key": "dup"})
    r = client.post("/api/ent/workspaces", json={"name": "Dup2", "key": "dup"})
    assert r.status_code == 400
