"""Customer CSV/XLSX imports: validation, explicit confirmation, and isolation."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from backend.app.models.company import Company, CompanyFinancials
from backend.app.models.portfolio_import import PortfolioImport
from backend.app.models.user import User
from backend.app.services.rbac.seeding import assign_role
from backend.tests._demo_portfolio_helpers import auth_headers, fresh_session, make_app, signup


def _upload(client, headers, filename="portfolio.csv", content=None):
    content = content or (
        b"Borrower,Industry,Currency,FY,Sales,Debt\n"
        b"Northwind Components,Manufacturing,USD,2024,1250000.25,300000\n"
    )
    return client.post(
        "/api/portfolio-imports",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
    )


def _mapping(client, headers, import_id, mapping=None, worksheet="CSV"):
    return client.put(
        f"/api/portfolio-imports/{import_id}/mapping",
        headers=headers,
        json={
            "worksheet": worksheet,
            "mapping": mapping or {
                "Borrower": "company_name",
                "Industry": "industry",
                "Currency": "currency",
                "FY": "fiscal_year",
                "Sales": "revenue",
                "Debt": "debt",
            },
        },
    )


def test_csv_requires_mapping_and_confirmation_then_persists_once():
    _, Session = fresh_session()
    client = make_app(Session)
    headers = auth_headers(signup(client, "importer@credit-a.example"))

    upload = _upload(client, headers)
    assert upload.status_code == 201, upload.text
    imported = upload.json()
    assert imported["status"] == "awaiting_mapping"
    assert imported["suggestions"]["Borrower"] == "company_name"
    assert imported["suggestions"]["Sales"] == "revenue"
    assert client.get("/api/portfolio-imports/", headers=headers).status_code == 200

    mapped = _mapping(client, headers, imported["id"])
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["status"] == "awaiting_confirmation"
    preview = client.get(f"/api/portfolio-imports/{imported['id']}/preview", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["items"][0]["canonical"]["revenue"] == "1250000.25"

    db = Session()
    try:
        assert db.query(Company).filter(Company.data_source == "customer_csv_import").count() == 0
    finally:
        db.close()

    confirmed = client.post(f"/api/portfolio-imports/{imported['id']}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "completed"
    assert confirmed.json()["imported_rows"] == 1
    retry = client.post(f"/api/portfolio-imports/{imported['id']}/confirm", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["imported_rows"] == 1

    db = Session()
    try:
        company = db.query(Company).filter(Company.data_source == "customer_csv_import").one()
        financial = db.query(CompanyFinancials).filter_by(company_id=company.id).one()
        tracked = db.query(PortfolioImport).filter_by(id=imported["id"]).one()
        assert company.is_demo is False
        assert financial.revenue == 1250000.25
        assert financial.debt == 300000
        assert tracked.staged_data is None
    finally:
        db.close()


def test_xlsx_upload_and_formula_cells_are_rejected_for_import():
    _, Session = fresh_session()
    client = make_app(Session)
    headers = auth_headers(signup(client, "xlsx@credit-a.example"))
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Borrowers"
    worksheet.append(["Company Name", "Industry", "Currency", "Fiscal Year", "Revenue"])
    worksheet.append(["Synthetic Metals", "Materials", "USD", 2025, 120000])
    worksheet.append(["Formula Co", "Materials", "USD", 2025, "=SUM(1,2)"])
    content = BytesIO()
    workbook.save(content)

    upload = _upload(client, headers, "customers.xlsx", content.getvalue())
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["worksheets"] == ["Borrowers"]
    mapping = {
        "Company Name": "company_name",
        "Industry": "industry",
        "Currency": "currency",
        "Fiscal Year": "fiscal_year",
        "Revenue": "revenue",
    }
    mapped = _mapping(client, headers, body["id"], mapping, worksheet="Borrowers")
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["valid_rows"] == 1
    assert mapped.json()["invalid_rows"] == 1
    assert any(finding["code"] == "formula_cell" for finding in mapped.json()["findings"])


def test_upload_rejects_unsupported_and_malformed_files():
    _, Session = fresh_session()
    client = make_app(Session)
    headers = auth_headers(signup(client, "files@credit-a.example"))
    assert _upload(client, headers, "portfolio.xls").status_code == 400
    assert _upload(client, headers, "portfolio.csv", b"\xff\xfe").status_code == 400
    assert _upload(client, headers, "portfolio.csv", b"a,A\n1,2\n").status_code == 400
    assert _upload(client, headers, "portfolio.xlsx", b"not a workbook").status_code == 400


def test_import_history_and_validation_report_are_tenant_scoped():
    _, Session = fresh_session()
    client = make_app(Session)
    tenant_a = auth_headers(signup(client, "analyst@credit-a.example"))
    tenant_b = auth_headers(signup(client, "analyst@credit-b.example"))
    created = _upload(client, tenant_a, content=b"Borrower,Industry\n,Services\n").json()
    assert client.get(f"/api/portfolio-imports/{created['id']}", headers=tenant_b).status_code == 404
    assert client.get(
        f"/api/portfolio-imports/{created['id']}/validation-report.csv", headers=tenant_b
    ).status_code == 404
    assert client.get("/api/portfolio-imports", headers=tenant_a).json()["total"] == 1
    assert client.get("/api/portfolio-imports", headers=tenant_b).json()["total"] == 0


def test_import_endpoints_require_authentication():
    _, Session = fresh_session()
    client = make_app(Session)
    assert client.get("/api/portfolio-imports").status_code in (401, 403)
    assert client.post(
        "/api/portfolio-imports", files={"file": ("portfolio.csv", b"Company\nA\n")}
    ).status_code in (401, 403)


def test_viewer_can_read_history_but_cannot_upload_or_confirm():
    _, Session = fresh_session()
    client = make_app(Session)
    token = signup(client, "viewer@credit-a.example")
    db = Session()
    try:
        user = db.query(User).filter_by(email="viewer@credit-a.example").one()
        assign_role(db, user, "viewer", replace=True)
    finally:
        db.close()
    headers = auth_headers(token)
    assert client.get("/api/portfolio-imports", headers=headers).status_code == 200
    assert _upload(client, headers).status_code == 403


def test_monetary_values_require_currency_and_can_be_reported():
    _, Session = fresh_session()
    client = make_app(Session)
    headers = auth_headers(signup(client, "currency@credit-a.example"))
    content = b"Company,Year,Revenue\nCurrency Check Ltd,2024,1000\n"
    uploaded = _upload(client, headers, content=content).json()
    result = _mapping(
        client,
        headers,
        uploaded["id"],
        {"Company": "company_name", "Year": "fiscal_year", "Revenue": "revenue"},
    )
    assert result.status_code == 200
    assert result.json()["valid_rows"] == 0
    assert any(finding["code"] == "currency_required" for finding in result.json()["findings"])
    report = client.get(
        f"/api/portfolio-imports/{uploaded['id']}/validation-report.csv", headers=headers
    )
    assert report.status_code == 200
    assert "currency_required" in report.text