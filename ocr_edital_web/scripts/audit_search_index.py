"""Read-only index coverage and distributed item-text verification."""

import json
import re
import sqlite3
import time
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/pncp.sqlite3"
STATUS = ROOT / "data/items_enrichment_priority.status.json"
OUTPUT = ROOT / "reports" / f"search-index-audit-{datetime.now():%Y%m%d-%H%M%S}.json"


def snapshot_status():
    return json.loads(STATUS.read_text(encoding="utf-8"))


def main():
    report = {"started_at": datetime.now().astimezone().isoformat(),
              "mode": "read-only", "checks": {}, "extraction_before": snapshot_status()}

    def save():
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def check(name, sql, params=(), timeout=90):
        started = time.monotonic()
        with sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            db.row_factory = sqlite3.Row
            db.set_progress_handler(lambda: int(time.monotonic() - started > timeout), 20000)
            try:
                value = {"rows": [dict(row) for row in db.execute(sql, params)]}
            except sqlite3.Error as exc:
                value = {"error": str(exc), "timeout_seconds": timeout}
        value["seconds"] = round(time.monotonic() - started, 3)
        report["checks"][name] = value
        print(name, json.dumps(value, ensure_ascii=True)[:1600], flush=True)
        save()
        return value.get("rows", [])

    check("counts", """SELECT (SELECT count(*) FROM opportunities) AS opportunities,
        (SELECT count(*) FROM opportunity_items) AS items,
        (SELECT count(*) FROM opportunity_search_docsize) AS indexed_opportunities""")
    check("coverage", """SELECT count(*) AS missing_index,
        coalesce(sum(EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)),0) AS with_items_missing_index
        FROM opportunities o LEFT JOIN opportunity_search_docsize s ON s.id=o.rowid
        WHERE s.id IS NULL""")
    check("orphan_index", """SELECT count(*) AS orphan_entries
        FROM opportunity_search_docsize s LEFT JOIN opportunities o ON o.rowid=s.id WHERE o.id IS NULL""")
    check("identity", """SELECT count(*) AS mismatched_identity FROM opportunity_search s
        LEFT JOIN opportunities o ON o.rowid=s.rowid WHERE o.id IS NULL OR o.id<>s.opportunity_id""", timeout=180)
    check("pending_items", """SELECT count(*) AS without_items FROM opportunities o
        WHERE NOT EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)""")
    samples = {}
    groups = [
        ("recent", """SELECT o.rowid AS rid,o.id FROM opportunities o
            WHERE EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)
            ORDER BY o.published_at DESC LIMIT 100""", ()),
        ("distributed", """SELECT o.rowid AS rid,o.id FROM opportunities o
            WHERE o.rowid % 997 = 0 AND EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)""", ()),
        ("current_extraction", """SELECT o.rowid AS rid,o.id FROM source_records s
            JOIN opportunities o ON o.id=s.opportunity_id WHERE s.etl_run_id=?
            AND EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)
            ORDER BY s.captured_at DESC LIMIT 100""", (report["extraction_before"]["run_id"],)),
    ]
    for name, sql, params in groups:
        for row in check("sample_" + name, sql, params):
            samples[row["id"]] = row

    validation = {"opportunities": 0, "items": 0, "fields_verified": 0,
                  "match_queries": 0, "errors": []}
    report["sample_validation"] = validation
    fields = ("source_item_id", "lot_number", "item_number", "title", "description",
              "technical_object", "unit", "status")
    for sample in samples.values():
        started = time.monotonic()
        with sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            db.row_factory = sqlite3.Row
            db.set_progress_handler(lambda: int(time.monotonic() - started > 15), 10000)
            db.execute("BEGIN")
            try:
                indexed = db.execute("SELECT content FROM opportunity_search WHERE rowid=?", (sample["rid"],)).fetchone()
                items = db.execute("SELECT * FROM opportunity_items WHERE opportunity_id=?", (sample["id"],)).fetchall()
                if not indexed:
                    validation["errors"].append({"id": sample["id"], "error": "missing_search_content"})
                    continue
                tokens = set()
                for item in items:
                    for field in fields:
                        value = str(item[field] or "")
                        if not value:
                            continue
                        validation["fields_verified"] += 1
                        if value not in indexed["content"]:
                            validation["errors"].append({"id": sample["id"], "item": item["id"], "field": field})
                    normalized = unicodedata.normalize("NFKD", item["description"] or "")
                    normalized = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
                    words = re.findall(r"[a-z]{4,}", normalized)
                    if words:
                        tokens.add(max(words, key=len))
                for token in sorted(tokens, key=lambda word: (-len(word), word))[:3]:
                    hit = db.execute("SELECT rowid FROM opportunity_search WHERE opportunity_search MATCH ? AND rowid=?",
                                     ('"' + token + '"', sample["rid"])).fetchone()
                    validation["match_queries"] += 1
                    if not hit:
                        validation["errors"].append({"id": sample["id"], "token": token, "error": "missing_posting"})
                validation["opportunities"] += 1
                validation["items"] += len(items)
            except sqlite3.Error as exc:
                validation["errors"].append({"id": sample["id"], "error": str(exc)})
        if validation["opportunities"] % 100 == 0:
            print("sample_progress", validation["opportunities"], "errors", len(validation["errors"]), flush=True)
            save()
    report["extraction_after"] = snapshot_status()
    report["finished_at"] = datetime.now().astimezone().isoformat()
    save()
    print(json.dumps(validation, ensure_ascii=True), flush=True)
    print("report", OUTPUT, flush=True)


if __name__ == "__main__":
    main()
