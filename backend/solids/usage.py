"""Anonymous hourly export counts. No requests or visitor identifiers are stored."""
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from zoneinfo import ZoneInfo

from .presets import PRESETS


def setup_from_design(design):
    """Canonical effective settings: presets and equivalent manual edits agree.

    Ignore inactive offsets and spelling of the recipe, and normalize numeric
    representation. Only allowlisted design fields can reach persistent storage.
    """
    parameters = design["parameters"]
    faces = {
        face["id"]: {"mode": face["transform"]["mode"],
                     "offset_mm": round(float(face["transform"]["offset_mm"]), 6)}
        for face in design["base_faces"]
        if face["transform"]["mode"] != "flat" and face["transform"]["offset_mm"] > 1e-7
    }
    construction = "original" if not faces else "custom"
    for preset in PRESETS:
        expected = {f["id"] for f in design["base_faces"][:1 if preset["scope"] == "one" else None]}
        if (preset["solid_id"] == parameters["solid_id"] and set(faces) == expected
                and all(f["mode"] == preset["mode"] for f in faces.values())
                and len({f["offset_mm"] for f in faces.values()}) == 1):
            construction = preset["id"]
            break
    return {
        "version": 1, "solid_id": parameters["solid_id"], "construction": construction,
        "face_transforms": faces,
        **{key: round(float(parameters[key]), 6) for key in
           ("edge_length_mm", "thickness_mm", "shrinkage_percent")},
        "page_format": parameters["page_format"], "angle_precision": parameters["angle_precision"],
    }


def utc_range(day: date, timezone_name: str):
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    return start.isoformat(), end.isoformat()


class UsageStore:
    """One small, persistent database shared by the app and one-shot reporter."""

    def __init__(self, data_dir):
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path / "usage.sqlite3", check_same_thread=False, timeout=2)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        with self._db:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS setups (
                    key TEXT PRIMARY KEY, solid_id TEXT NOT NULL,
                    construction TEXT NOT NULL, settings TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hourly_exports (
                    hour_utc TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('pdf','svg','calibration')),
                    outcome TEXT NOT NULL CHECK (outcome IN ('success','rejected','error')),
                    setup_key TEXT NOT NULL, template_id TEXT NOT NULL,
                    count INTEGER NOT NULL CHECK (count > 0),
                    PRIMARY KEY (hour_utc,kind,outcome,setup_key,template_id)
                );
                CREATE TABLE IF NOT EXISTS report_deliveries (
                    day TEXT PRIMARY KEY, claimed_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('claimed','sent','failed'))
                );
            """)

    def record(self, kind, outcome, setup=None, template_id="", *, at=None):
        instant = at or datetime.now(UTC)
        if instant.tzinfo is None:
            raise ValueError("Usage timestamps must be timezone-aware")
        hour = instant.astimezone(UTC).replace(minute=0, second=0, microsecond=0).isoformat()
        settings = json.dumps(setup, sort_keys=True, separators=(",", ":")) if setup else None
        key = hashlib.sha256(settings.encode()).hexdigest() if settings else ""
        with self._lock, self._db:
            if setup:
                self._db.execute("INSERT OR IGNORE INTO setups VALUES (?,?,?,?)",
                                 (key, setup["solid_id"], setup["construction"], settings))
            self._db.execute("""
                INSERT INTO hourly_exports VALUES (?,?,?,?,?,1)
                ON CONFLICT (hour_utc,kind,outcome,setup_key,template_id)
                DO UPDATE SET count=count+1
            """, (hour, kind, outcome, key, template_id))

    def snapshot(self, day: date, timezone_name: str, *, days=1):
        start, _ = utc_range(day - timedelta(days=days-1), timezone_name)
        _, end = utc_range(day, timezone_name)
        with self._lock:
            rows = self._db.execute("""
                SELECT e.*, s.settings FROM hourly_exports e
                LEFT JOIN setups s ON s.key=e.setup_key
                WHERE hour_utc>=? AND hour_utc<? ORDER BY hour_utc,kind,setup_key,template_id
            """, (start,end)).fetchall()
        return [{**dict(row), "settings": json.loads(row["settings"]) if row["settings"] else None}
                for row in rows]

    def claim_delivery(self, day: date):
        with self._lock, self._db:
            cursor = self._db.execute("INSERT OR IGNORE INTO report_deliveries VALUES (?,?,'claimed')",
                                      (day.isoformat(), datetime.now(UTC).isoformat()))
        return cursor.rowcount == 1

    def finish_delivery(self, day: date, status):
        if status not in {"sent", "failed"}:
            raise ValueError("Invalid delivery status")
        with self._lock, self._db:
            self._db.execute("UPDATE report_deliveries SET status=? WHERE day=?", (status,day.isoformat()))

    def close(self):
        with self._lock:
            self._db.close()
