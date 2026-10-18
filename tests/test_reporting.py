from dataclasses import replace
from datetime import UTC, date, datetime
import json
import sqlite3
import os
import subprocess
import sys

import pytest

from solids import reporting
from solids.geometry import Parameters, make_design
from solids.reporting import ReportSettings, build_digest, cloudflare_analytics
from solids.usage import UsageStore, setup_from_design


def settings(**overrides):
    values=dict(data_dir="/tmp/unused-solids-report",timezone_name="America/Los_Angeles",
        hostname="solids.tobiasbrownheft.xyz",cloudflare_zone_id="zone",cloudflare_token="private-token-value",
        report_to="owner@example.test",report_from="reports@example.test",smtp_host="smtp.example.test",
        smtp_port=587,smtp_security="starttls",smtp_user="owner",smtp_password="private-password-value")
    return ReportSettings(**(values|overrides))


def test_cloudflare_uses_hostname_local_day_and_aggregates_only():
    captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self):
            return json.dumps({"data":{"viewer":{"zones":[{"httpRequestsAdaptiveGroups":[
                {"count":20,"sum":{"visits":7,"edgeResponseBytes":2048}},
                {"count":5,"sum":{"visits":2,"edgeResponseBytes":512}},
            ]}]}}}).encode()
    def opener(request,timeout):
        captured.update(body=json.loads(request.data),timeout=timeout)
        return Response()
    assert cloudflare_analytics(settings(),date(2026,11,1),opener=opener)=={
        "status":"available","visits":9,"requests":25,"bytes":2560}
    variables=captured["body"]["variables"]
    assert variables=={"zone":"zone","host":"solids.tobiasbrownheft.xyz",
        "start":"2026-11-01T07:00:00+00:00","end":"2026-11-02T08:00:00+00:00"}
    query=captured["body"]["query"]
    assert 'requestSource: "eyeball"' in query
    assert "clientIP" not in query and "userAgent" not in query
    assert captured["timeout"]==20
    assert cloudflare_analytics(settings(cloudflare_token=None),date(2026,7,19))["status"]=="unavailable"
    assert "private-token-value" not in repr(settings())
    assert "private-password-value" not in repr(settings())


def test_digest_groups_sizes_by_construction_and_keeps_pdf_svg_coupon_totals_separate(tmp_path):
    store=UsageStore(tmp_path)
    day=date(2026,11,1)
    setup=setup_from_design(make_design(Parameters(solid_id="cube")))
    large=setup|{"edge_length_mm":150.}
    for at in (datetime(2026,11,1,8,tzinfo=UTC),datetime(2026,11,1,9,tzinfo=UTC)):
        store.record("pdf","success",setup,at=at)
    store.record("pdf","success",large,at=datetime(2026,11,1,20,tzinfo=UTC))
    store.record("svg","success",setup,"A",at=datetime(2026,11,1,20,tzinfo=UTC))
    store.record("calibration","success",at=datetime(2026,11,1,20,tzinfo=UTC))
    store.record("pdf","rejected",at=datetime(2026,11,1,20,tzinfo=UTC))
    store.record("pdf","error",at=datetime(2026,11,1,20,tzinfo=UTC))
    rows=store.snapshot(day,"America/Los_Angeles")
    body=build_digest(day,rows,rows,{"status":"unavailable","detail":"not configured"},settings())
    assert "PDF template sets: 3" in body
    assert "SVG individual panels: 1" in body
    assert "Calibration coupon exports: 1" in body
    assert "Rejected exports (4xx): 1" in body and "Server export errors (5xx): 1" in body
    assert "3 PDF sets: Cube / original" in body
    assert "edge 120 mm" in body and "edge 150 mm" in body
    assert "01:00 PDT" in body and "01:00 PST" in body
    assert "not unique people or confirmed saves/prints" in body
    assert "Cloudflare analytics: unavailable" in body
    assert "2 PDF sets: edge 120 mm" in body
    assert "1 SVG panel: Cube / original / panel A" in body
    store.close()


def test_reporter_imports_no_geometry_or_numeric_runtime():
    result=subprocess.run([sys.executable,"-c",
        "import sys; from solids import reporting; reporting._construction_label('cube','original'); "
        "assert not {'numpy','scipy','solids.registry','solids.geometry'} & sys.modules.keys()"],
        env={**os.environ,"PYTHONPATH":"backend"},capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_settings_load_secrets_from_files_and_reject_invalid_timezone(monkeypatch,tmp_path):
    token=tmp_path/"cloudflare-token";token.write_text("secret-cf-value\n")
    password=tmp_path/"smtp-password";password.write_text("secret-smtp-value\n")
    monkeypatch.setenv("SOLIDS_CLOUDFLARE_API_TOKEN_FILE",str(token))
    monkeypatch.setenv("SOLIDS_SMTP_PASSWORD_FILE",str(password))
    monkeypatch.setenv("SOLIDS_REPORT_TIMEZONE","America/Los_Angeles")
    config=ReportSettings.from_env()
    assert config.cloudflare_token=="secret-cf-value" and config.smtp_password=="secret-smtp-value"
    assert "secret-cf-value" not in repr(config) and "secret-smtp-value" not in repr(config)
    monkeypatch.setenv("SOLIDS_REPORT_TIMEZONE","not/a/timezone")
    with pytest.raises(KeyError):
        ReportSettings.from_env()


def configure(monkeypatch,tmp_path):
    config=settings(data_dir=str(tmp_path))
    monkeypatch.setattr(ReportSettings,"from_env",classmethod(lambda cls:config))
    monkeypatch.setattr(reporting,"cloudflare_analytics",lambda *args:{"status":"unavailable"})
    return config


def test_dry_run_never_sends_or_claims_and_covers_empty_usage(monkeypatch,tmp_path,capsys):
    config=configure(monkeypatch,tmp_path)
    monkeypatch.setattr(ReportSettings,"from_env",classmethod(lambda cls:replace(config,report_to=None,smtp_host=None)))
    def fail(*args,**kwargs):
        raise AssertionError("Dry run must not send")
    monkeypatch.setattr(reporting,"send_email",fail)
    assert reporting.main(["--dry-run","--date","2020-07-19"])==0
    output=capsys.readouterr().out
    assert "PDF template sets: 0" in output and "No PDF exports recorded" in output
    with sqlite3.connect(tmp_path/"usage.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM report_deliveries").fetchone()[0]==0


def test_repeat_invocations_send_at_most_once_even_when_cloudflare_fails(monkeypatch,tmp_path,capsys):
    configure(monkeypatch,tmp_path)
    def fail_cf(*args):
        raise TimeoutError("simulated remote timeout")
    sent=[]
    monkeypatch.setattr(reporting,"cloudflare_analytics",fail_cf)
    monkeypatch.setattr(reporting,"send_email",lambda *args,**kwargs:sent.append(args))
    for _ in range(2):
        assert reporting.main(["--date","2020-07-19"])==0
    assert len(sent)==1
    assert "Analytics query failed (TimeoutError)" in sent[0][2]
    assert "already claimed" in capsys.readouterr().out
    with sqlite3.connect(tmp_path/"usage.sqlite3") as connection:
        assert connection.execute("SELECT status FROM report_deliveries").fetchone()[0]=="sent"


def test_smtp_failure_marks_claim_and_is_not_automatically_retried(monkeypatch,tmp_path):
    configure(monkeypatch,tmp_path)
    attempts=[]
    def fail(*args,**kwargs):
        attempts.append(1)
        raise RuntimeError("simulated ambiguous SMTP failure")
    monkeypatch.setattr(reporting,"send_email",fail)
    with pytest.raises(RuntimeError):
        reporting.main(["--date","2020-07-19"])
    assert reporting.main(["--date","2020-07-19"])==0
    assert len(attempts)==1
    with sqlite3.connect(tmp_path/"usage.sqlite3") as connection:
        assert connection.execute("SELECT status FROM report_deliveries").fetchone()[0]=="failed"


def test_invalid_mail_config_cannot_consume_a_delivery_claim(monkeypatch,tmp_path):
    config=configure(monkeypatch,tmp_path/"unused")
    monkeypatch.setattr(ReportSettings,"from_env",classmethod(lambda cls:replace(config,report_to=None)))
    with pytest.raises(ValueError,match="SOLIDS_REPORT_TO"):
        reporting.main(["--date","2020-07-19"])
    assert not (tmp_path/"unused").exists()


def test_email_test_does_not_open_usage_store(monkeypatch,tmp_path):
    configure(monkeypatch,tmp_path/"unused")
    sent=[]
    monkeypatch.setattr(reporting,"send_email",lambda *args,**kwargs:sent.append((args,kwargs)))
    assert reporting.main(["--test-email"])==0
    assert sent[0][1]["subject"]=="Solids reporting test"
    assert not (tmp_path/"unused").exists()


def test_future_day_is_rejected_without_claim(monkeypatch,tmp_path):
    configure(monkeypatch,tmp_path/"unused")
    with pytest.raises(SystemExit):
        reporting.main(["--dry-run","--date","2999-01-01"])
    assert not (tmp_path/"unused").exists()


@pytest.mark.parametrize("security",["starttls","ssl"])
def test_mail_uses_tls_before_authentication_and_sends_plain_text(monkeypatch,security):
    calls=[]
    class Client:
        def __init__(self,*args,**kwargs): calls.append(("connect",kwargs))
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self,**kwargs): calls.append(("tls",kwargs))
        def login(self,*args): calls.append(("login",args))
        def send_message(self,message): calls.append(("send",message))
    monkeypatch.setattr(reporting.smtplib,"SMTP",Client)
    monkeypatch.setattr(reporting.smtplib,"SMTP_SSL",Client)
    reporting.send_email(settings(smtp_security=security),date(2020,7,19),"Anonymous totals\n")
    assert [c[0] for c in calls]==(["connect","tls","login","send"] if security=="starttls" else ["connect","login","send"])
    assert calls[-1][1].get_content_type()=="text/plain"
    assert "2020-07-19" in calls[-1][1]["Subject"]
    if security=="ssl":
        assert "context" in calls[0][1]
