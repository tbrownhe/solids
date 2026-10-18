from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from solids import api
from solids.geometry import Parameters, make_design
from solids.usage import UsageStore, setup_from_design, utc_range


def test_equivalent_presets_and_manual_edits_share_effective_settings():
    preset=make_design(Parameters(solid_id="cube",preset_id="excavated-cube-single"))
    manual=make_design(Parameters(solid_id="cube",apex_offset_mm=987,edge_length_mm=120.0,
        face_transforms={"F001":{"mode":"inward","offset_mm":20.0},
                         "F002":{"mode":"flat","offset_mm":999}}))
    assert setup_from_design(preset)==setup_from_design(manual)
    original=make_design(Parameters(solid_id="cube"))
    zero=make_design(Parameters(solid_id="cube",preset_id="excavated-cube",apex_offset_mm=0))
    assert setup_from_design(original)==setup_from_design(zero)
    custom=make_design(Parameters(solid_id="cube",face_transforms={"F003":{"mode":"outward","offset_mm":15}}))
    assert setup_from_design(custom)["construction"]=="custom"


def test_counts_are_hourly_aggregates_survive_restart_and_keep_formats_separate(tmp_path):
    setup=setup_from_design(make_design(Parameters(solid_id="cube")))
    at=datetime(2026,7,19,18,5,tzinfo=UTC)
    store=UsageStore(tmp_path)
    store.record("pdf","success",setup,at=at)
    store.record("pdf","success",setup,at=at+timedelta(minutes=50))
    store.record("svg","success",setup,"A",at=at)
    store.record("calibration","success",at=at)
    store.record("pdf","rejected",at=at)
    store.close()
    store=UsageStore(tmp_path)
    rows=store.snapshot(date(2026,7,19),"America/Los_Angeles")
    assert len(rows)==4
    assert next(r for r in rows if r["kind"]=="pdf" and r["outcome"]=="success")["count"]==2
    assert next(r for r in rows if r["kind"]=="svg")["template_id"]=="A"
    assert next(r for r in rows if r["kind"]=="calibration")["settings"] is None
    assert {r["hour_utc"] for r in rows}=={"2026-07-19T18:00:00+00:00"}
    store.close()
    connection=sqlite3.connect(tmp_path/"usage.sqlite3")
    assert connection.execute("SELECT COUNT(*) FROM setups").fetchone()[0]==1
    assert not any("visitor" in row[1] for row in connection.execute("PRAGMA table_info(hourly_exports)"))
    connection.close()


@pytest.mark.parametrize("day,hours",[(date(2026,3,8),23),(date(2026,11,1),25)])
def test_local_day_bounds_follow_dst_and_include_each_real_hour(tmp_path,day,hours):
    start,end=map(datetime.fromisoformat,utc_range(day,"America/Los_Angeles"))
    assert (end-start).total_seconds()==hours*3600
    store=UsageStore(tmp_path)
    for i in range(-1,hours+1):
        store.record("pdf","success",at=start+timedelta(hours=i,minutes=10))
    assert len(store.snapshot(day,"America/Los_Angeles"))==hours
    assert sum(r["count"] for r in store.snapshot(day,"America/Los_Angeles",days=7))==hours+1
    store.close()


def test_concurrent_connections_do_not_lose_counts_or_double_claim(tmp_path):
    stores=[UsageStore(tmp_path) for _ in range(4)]
    at=datetime(2026,7,19,12,tzinfo=UTC)
    def write(index):
        for _ in range(30):
            stores[index].record("pdf","success",at=at)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write,range(4)))
        claims=list(pool.map(lambda s:s.claim_delivery(date(2026,7,19)),stores))
    assert sum(claims)==1
    assert stores[0].snapshot(date(2026,7,19),"UTC")[0]["count"]==120
    stores[0].finish_delivery(date(2026,7,19),"sent")
    for store in stores:
        store.close()


def test_api_counts_only_exports_and_never_stores_connection_or_raw_input(monkeypatch,tmp_path):
    monkeypatch.setenv("SOLIDS_USAGE_DATA_DIR",str(tmp_path))
    with TestClient(api.app,raise_server_exceptions=False) as client:
        for path in ("/api/health","/api/solids","/api/presets"):
            assert client.get(path).status_code==200
        assert client.post("/api/design",json={}).status_code==200
        assert client.post("/api/export/pdf",json={"solid_id":"cube"},headers={
            "CF-Connecting-IP":"203.0.113.77","User-Agent":"private-agent-value",
            "Cookie":"visitor=private-cookie-value"}).status_code==200
        assert client.post("/api/export/svg/A",json={"solid_id":"cube"}).status_code==200
        assert client.post("/api/export/calibration",json={}).status_code==200
        assert client.post("/api/export/pdf",json={"secret":"private-request-value"}).status_code==422
        assert client.post("/api/export/pdf",json={"solid_id":"missing"}).status_code==422
        assert client.post("/api/export/svg/Z",json={}).status_code==422
        assert client.post("/api/export/calibration",json={"thickness_mm":-1}).status_code==422
        def fail(_design):
            raise RuntimeError("simulated exporter failure")
        monkeypatch.setattr(api,"pdf_bytes",fail)
        assert client.post("/api/export/pdf",json={}).status_code==500
    connection=sqlite3.connect(tmp_path/"usage.sqlite3")
    totals={(kind,outcome):count for kind,outcome,count in connection.execute(
        "SELECT kind,outcome,SUM(count) FROM hourly_exports GROUP BY kind,outcome")}
    assert totals=={("pdf","success"):1,("svg","success"):1,("calibration","success"):1,
                   ("pdf","rejected"):2,("svg","rejected"):1,("calibration","rejected"):1,("pdf","error"):1}
    dump="\n".join(connection.iterdump())
    for value in ("203.0.113.77","private-agent-value","private-cookie-value","private-request-value"):
        assert value not in dump
    settings=json.loads(connection.execute("SELECT settings FROM setups").fetchone()[0])
    assert set(settings)=={"version","solid_id","construction","face_transforms","edge_length_mm",
                           "thickness_mm","shrinkage_percent","page_format","angle_precision"}
    connection.close()


def test_usage_write_failure_does_not_break_download(monkeypatch,tmp_path,caplog):
    monkeypatch.setenv("SOLIDS_USAGE_DATA_DIR",str(tmp_path))
    def fail(*args,**kwargs):
        raise sqlite3.OperationalError("simulated full disk")
    with TestClient(api.app) as client:
        monkeypatch.setattr(api.app.state.usage,"record",fail)
        response=client.post("/api/export/pdf",json={"solid_id":"cube"})
        assert response.status_code==200 and response.content.startswith(b"%PDF")
    assert "Could not record export count (OperationalError)" in caplog.text


def test_usage_startup_failure_does_not_break_download(monkeypatch,tmp_path,caplog):
    path=tmp_path/"file";path.write_text("not a directory")
    monkeypatch.setenv("SOLIDS_USAGE_DATA_DIR",str(path/"usage"))
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()=={"status":"ok"}
        assert client.post("/api/export/pdf",json={"solid_id":"cube"}).status_code==200
    assert "Usage storage unavailable" in caplog.text
