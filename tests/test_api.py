"""API: self-describing datasets, private-column withholding, restricted 403,
and the object image/video endpoints."""
from fastapi.testclient import TestClient


def _client(demo_db):
    from api.main import app
    return TestClient(app)


def test_datasets_listed_and_private_withheld(demo_db):
    cl = _client(demo_db)
    ds = {d["tbl"] for d in cl.get("/datasets").json()["datasets"]}
    assert {"studios", "artists"} <= ds
    row = cl.get("/datasets/studios").json()["rows"][0]
    assert "email_address" not in row          # private column withheld


def test_restricted_dataset_blocked(demo_db):
    cl = _client(demo_db)
    assert cl.get("/datasets/studio_intake").status_code == 403


def test_object_media_404_when_absent(demo_db):
    cl = _client(demo_db)
    assert cl.get("/objects/nope/image").status_code == 404
    assert cl.get("/objects/nope/video").status_code == 404


def test_csv_export(demo_db):
    cl = _client(demo_db)
    r = cl.get("/datasets/artists?format=csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]


def test_demographic_columns_withheld_even_when_marked_public(demo_db, monkeypatch):
    """Ethnicity, gender and birth year stay in the table. Public responses omit
    them even if _columns.is_public is still 1, which is how the live registry
    was ingested (long spreadsheet slugs included)."""
    from central.dbconn import connect
    c = connect()
    live = {
        "what_s_your_ethnicity": "secret-ethnic",
        "what_is_your_gender": "secret-gender",
        "birth_year_what_year_were_you_born": "1970",
        "year_of_death_are_you_still_alive": "2099",
    }
    have = {r[1] for r in c.execute("PRAGMA table_info(artists)")}
    for i, (col, value) in enumerate(live.items()):
        if col not in have:
            c.execute(f'ALTER TABLE artists ADD COLUMN "{col}" TEXT')
        c.execute("INSERT OR REPLACE INTO _columns (tbl,column,label,ordinal,is_public) "
                  "VALUES (?,?,?,?,1)", ("artists", col, col, 40 + i))
        c.execute(f'UPDATE artists SET "{col}"=?', (value,))
    c.commit()
    cl = _client(demo_db)
    body = cl.get("/datasets/artists").text
    schema = cl.get("/schema/artists").text
    csv = cl.get("/datasets/artists?format=csv").text
    for secret in ("secret-ethnic", "secret-gender", "1970", "2099", "1984"):
        assert secret not in body and secret not in csv
    for col in ("birth_year", "ethnicity", "gender", *live):
        assert col not in schema and col not in body
    import api.main as main
    monkeypatch.setattr(main, "ADMIN_KEY", "adm-key")
    rows = cl.get("/datasets/artists", headers={"x-api-key": "adm-key"}).json()["rows"]
    assert "1984" in {row["birth_year"] for row in rows}
    assert any(row["what_s_your_ethnicity"] == "secret-ethnic" for row in rows)
    assert any(row.get("ethnicity") for row in rows)


def test_security_headers_on_public_responses(demo_db):
    from pathlib import Path

    from central.security_headers import CSP
    r = _client(demo_db).get("/datasets")
    h = {k.lower(): v for k, v in r.headers.items()}
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "SAMEORIGIN"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=(self)" in h["permissions-policy"]
    assert "frame-ancestors 'self'" in h["content-security-policy"]
    assert "cdn.jsdelivr.net" in h["content-security-policy"]
    assert "huggingface.co" in h["content-security-policy"]
    assert "strict-transport-security" not in h          # plain HTTP
    root = Path(__file__).resolve().parent.parent / "deploy"
    for name in ("apache-glassdatabase-proxy.conf", "nginx-glassdatabase.conf"):
        text = (root / name).read_text(encoding="utf-8")
        assert CSP in text
        assert "X-Content-Type-Options" in text and "Strict-Transport-Security" in text
