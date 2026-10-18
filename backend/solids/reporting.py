"""One-shot daily email: Cloudflare hostname aggregates and anonymous exports."""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
import urllib.request
from zoneinfo import ZoneInfo

from .presets import PRESETS
from .usage import UsageStore, utc_range


def _secret(path):
    source = Path(path)
    return source.read_text().strip() if source.is_file() else None


@dataclass(frozen=True)
class ReportSettings:
    data_dir: str
    timezone_name: str
    hostname: str
    cloudflare_zone_id: str | None
    cloudflare_token: str | None = field(repr=False)
    report_to: str | None
    report_from: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_security: str
    smtp_user: str | None
    smtp_password: str | None = field(repr=False)

    @classmethod
    def from_env(cls):
        zone = os.getenv("SOLIDS_REPORT_TIMEZONE", "America/Los_Angeles")
        ZoneInfo(zone)
        security = os.getenv("SOLIDS_SMTP_SECURITY", "starttls")
        if security not in {"starttls", "ssl"}:
            raise ValueError("SOLIDS_SMTP_SECURITY must be starttls or ssl")
        return cls(
            data_dir=os.getenv("SOLIDS_USAGE_DATA_DIR", "/var/lib/solids"),
            timezone_name=zone,
            hostname=os.getenv("SOLIDS_REPORT_HOSTNAME", "solids.tobiasbrownheft.xyz"),
            cloudflare_zone_id=os.getenv("SOLIDS_CLOUDFLARE_ZONE_ID") or None,
            cloudflare_token=_secret(os.getenv("SOLIDS_CLOUDFLARE_API_TOKEN_FILE", "/run/secrets/solids-reporting/cloudflare-token")),
            report_to=os.getenv("SOLIDS_REPORT_TO"), report_from=os.getenv("SOLIDS_REPORT_FROM"),
            smtp_host=os.getenv("SOLIDS_SMTP_HOST"), smtp_port=int(os.getenv("SOLIDS_SMTP_PORT", "587")),
            smtp_security=security, smtp_user=os.getenv("SOLIDS_SMTP_USER") or None,
            smtp_password=_secret(os.getenv("SOLIDS_SMTP_PASSWORD_FILE", "/run/secrets/solids-reporting/smtp-password")),
        )


def cloudflare_analytics(config, day, *, opener=urllib.request.urlopen):
    if not (config.cloudflare_zone_id and config.cloudflare_token):
        return {"status": "unavailable", "detail": "Cloudflare is not configured."}
    start,end = utc_range(day, config.timezone_name)
    query = """
        query DailyUsage($zone: string!, $host: string!, $start: Time!, $end: Time!) {
          viewer { zones(filter: {zoneTag: $zone}) {
            httpRequestsAdaptiveGroups(limit: 1000, filter: {
              datetime_geq: $start, datetime_lt: $end,
              clientRequestHTTPHost: $host, requestSource: "eyeball"
            }) { count sum { visits edgeResponseBytes } }
          } }
        }
    """
    request = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql",
        data=json.dumps({"query": query, "variables": {
            "zone": config.cloudflare_zone_id, "host": config.hostname, "start": start, "end": end,
        }}).encode(), method="POST", headers={
            "Authorization": f"Bearer {config.cloudflare_token}", "Content-Type": "application/json",
            "User-Agent": "solids-daily-report/1",
        })
    with opener(request, timeout=20) as response:
        payload = json.loads(response.read())
    if payload.get("errors"):
        raise RuntimeError("Cloudflare rejected the analytics query; check token scope and zone configuration.")
    zones = (payload.get("data") or {}).get("viewer", {}).get("zones", [])
    if not zones:
        raise RuntimeError("Cloudflare returned no matching zone")
    groups = zones[0]["httpRequestsAdaptiveGroups"]
    if len(groups) >= 1000:
        raise RuntimeError("Cloudflare query reached its group limit; refusing a potentially partial total")
    return {"status": "available", "visits": sum(g["sum"].get("visits") or 0 for g in groups),
            "requests": sum(g.get("count") or 0 for g in groups),
            "bytes": sum(g["sum"].get("edgeResponseBytes") or 0 for g in groups)}


def _construction_label(solid, construction):
    name = solid.replace("-", " ").capitalize()
    if construction == "original":
        return name + " / original"
    if construction == "custom":
        return name + " / custom faces"
    return next((p["name"] for p in PRESETS if p["id"] == construction), construction)


def _dimension_label(settings):
    return (f"edge {settings['edge_length_mm']:g} mm / slab {settings['thickness_mm']:g} mm / "
            f"shrink {settings['shrinkage_percent']:g}% / {settings['page_format'].upper()}")


def _rank_lines(rows, *, exact=False, kind="pdf"):
    counts = Counter()
    settings = {}
    for row in rows:
        if row["kind"] != kind or row["outcome"] != "success" or not row["settings"]:
            continue
        s = row["settings"]
        key = row["setup_key"] if exact else (s["solid_id"],s["construction"],row["template_id"] if kind=="svg" else "")
        counts[key] += row["count"]
        settings[key] = s
    lines = []
    for key,count in sorted(counts.items(), key=lambda item: (-item[1],item[0]))[:5]:
        s = settings[key]
        label = _construction_label(s["solid_id"],s["construction"])
        if kind=="svg":
            label += f" / panel {key[2]}"
        if exact:
            label += " / " + _dimension_label(s) + f" / {s['angle_precision']} angle decimals"
            faces = s["face_transforms"]
            offsets = {f["offset_mm"] for f in faces.values()}
            if len(offsets) == 1 and s["construction"] != "custom":
                label += f" / apex offset {next(iter(offsets)):g} mm fired"
            elif faces:
                label += " / " + ", ".join(f"{face} {f['mode']} {f['offset_mm']:g} mm" for face,f in list(faces.items())[:6])
                if len(faces)>6:
                    label += f" (+{len(faces)-6} more faces)"
            label += f" [setup {key[:8]}]"
        unit = "PDF set" if kind=="pdf" else "SVG panel"
        lines.append(f"  {count:,} {unit}{'s' if count!=1 else ''}: {label}")
    return lines or [f"  No {kind.upper()} exports recorded."]


def _dimension_lines(rows):
    counts = Counter()
    for row in rows:
        if row["kind"]=="pdf" and row["outcome"]=="success" and (s:=row["settings"]):
            counts[_dimension_label(s)] += row["count"]
    return [f"  {count:,} PDF set{'s' if count!=1 else ''}: {label}" for label,count in
            sorted(counts.items(),key=lambda item:(-item[1],item[0]))[:5]] or ["  No PDF exports recorded."]


def build_digest(day, daily, weekly, edge, config):
    counts = Counter()
    hours = Counter()
    for row in daily:
        counts[(row["kind"],row["outcome"])] += row["count"]
        if row["outcome"] == "success":
            hours[row["hour_utc"]] += row["count"]
    lines = [f"Solids daily usage — {day.isoformat()}", f"Host: {config.hostname}",
             f"Timezone: {config.timezone_name}", "", "Public traffic (Cloudflare estimates)"]
    if edge["status"] == "available":
        lines += [f"Estimated visits: {edge['visits']:,}", f"HTTP requests: {edge['requests']:,}",
                  f"Edge transfer: {edge['bytes']/1024/1024:.2f} MiB"]
    else:
        lines += ["Cloudflare analytics: unavailable", f"Reason: {edge.get('detail','unavailable')}"]
    lines += ["", "Exports generated yesterday",
              f"PDF template sets: {counts['pdf','success']:,}",
              f"SVG individual panels: {counts['svg','success']:,}",
              f"Calibration coupon exports: {counts['calibration','success']:,}",
              f"Rejected exports (4xx): {sum(n for (kind,outcome),n in counts.items() if outcome=='rejected'):,}",
              f"Server export errors (5xx): {sum(n for (kind,outcome),n in counts.items() if outcome=='error'):,}",
              "", "Busiest export hours (all successful formats)"]
    for hour,count in sorted(hours.items(),key=lambda item:(-item[1],item[0]))[:5]:
        local = datetime.fromisoformat(hour).astimezone(ZoneInfo(config.timezone_name))
        lines.append(f"  {local:%H:00 %Z}: {count:,} export{'s' if count!=1 else ''}")
    if not hours:
        lines.append("  No exports recorded.")
    lines += ["", "Top PDF constructions yesterday", *_rank_lines(daily),
              "", "Top PDF constructions — trailing 7 days", *_rank_lines(weekly),
              "", "Top complete PDF setups — trailing 7 days", *_rank_lines(weekly,exact=True),
              "", "Common PDF dimensions — trailing 7 days", *_dimension_lines(weekly),
              "", "Top SVG panel setups — trailing 7 days", *_rank_lines(weekly,kind="svg"),
              "", "Counts are generated exports, not unique people or confirmed saves/prints.",
              "Repeat requests and automated clients can contribute. SVGs and coupons do not inflate PDF rankings.",
              "Only hourly aggregates and normalized design settings are stored by application analytics.",
              "No IP addresses, user agents, cookies, visitor IDs or browsing histories are collected by this reporter."]
    return "\n".join(lines) + "\n"


def _validate_email(config):
    if not (config.report_to and config.report_from and config.smtp_host):
        raise ValueError("SOLIDS_REPORT_TO, SOLIDS_REPORT_FROM and SOLIDS_SMTP_HOST are required")
    if config.smtp_user and not config.smtp_password:
        raise ValueError("SMTP user is configured but its password file is missing")


def send_email(config, day, body, *, subject=None):
    _validate_email(config)
    message = EmailMessage()
    message["To"], message["From"] = config.report_to,config.report_from
    message["Subject"] = subject or f"Solids daily usage — {day.isoformat()}"
    message.set_content(body)
    context = ssl.create_default_context()
    if config.smtp_security == "ssl":
        client = smtplib.SMTP_SSL(config.smtp_host,config.smtp_port,timeout=30,context=context)
    else:
        client = smtplib.SMTP(config.smtp_host,config.smtp_port,timeout=30)
    with client:
        if config.smtp_security == "starttls":
            client.starttls(context=context)
        if config.smtp_user:
            client.login(config.smtp_user,config.smtp_password)
        client.send_message(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report anonymous Solids usage for a complete local day")
    parser.add_argument("--date",type=date.fromisoformat,help="local report date (default: yesterday)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run",action="store_true",help="preview without sending or claiming delivery")
    mode.add_argument("--test-email",action="store_true",help="send an SMTP test without claiming a day")
    args = parser.parse_args(argv)
    config = ReportSettings.from_env()
    today = datetime.now(ZoneInfo(config.timezone_name)).date()
    day = args.date or today-timedelta(days=1)
    if args.test_email:
        send_email(config,day,"Solids reporting SMTP configuration succeeded.\n",subject="Solids reporting test")
        print("Sent reporting test email.")
        return 0
    if day >= today:
        parser.error("Choose a complete local day before today")
    if not args.dry_run:
        _validate_email(config)
    store = UsageStore(config.data_dir)
    try:
        daily = store.snapshot(day,config.timezone_name)
        weekly = store.snapshot(day,config.timezone_name,days=7)
        try:
            edge = cloudflare_analytics(config,day)
        except Exception as error:
            edge = {"status":"unavailable","detail":f"Analytics query failed ({type(error).__name__})."}
        body = build_digest(day,daily,weekly,edge,config)
        if args.dry_run:
            print(body,end="")
            return 0
        if not store.claim_delivery(day):
            print(f"Report for {day} already claimed; no email sent.")
            return 0
        try:
            send_email(config,day,body)
        except Exception:
            store.finish_delivery(day,"failed")
            raise
        store.finish_delivery(day,"sent")
        print(f"Sent usage report for {day}.")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
