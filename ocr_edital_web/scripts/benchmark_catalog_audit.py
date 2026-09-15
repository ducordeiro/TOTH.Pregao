"""Measure Block 7 locally; optional single live tender analysis, no bulk requests."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import catalog_library
import server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    report = {"reference_samples": 50, "measurements": {}}
    elapsed = []
    for index in range(50):
        start = time.perf_counter()
        catalog_library.find_catalog_references(f"Cadeira giratoria em tela mesh com espuma injetada poliuretano densidade {index + 30} kg apoio lombar pistao classe 4 encosto tecido poliester rodizios")
        elapsed.append((time.perf_counter() - start) * 1000)
    report["references_ms"] = {"total": sum(elapsed), "cold": elapsed[0], "p95": sorted(elapsed)[47]}
    for name, endpoint in (("http_app", "/"), ("http_saved_catalog", "/catalog-generator/jobs/6fa376c4eb5947f7827ee5c200e48d7e")):
        times = []
        for _ in range(10):
            start = time.perf_counter()
            with urllib.request.urlopen("http://127.0.0.1:8765" + endpoint, timeout=15) as response:
                response.read()
                assert response.status == 200
            times.append((time.perf_counter() - start) * 1000)
        report["measurements"][name] = {"samples": len(times), "mean_ms": sum(times) / len(times), "max_ms": max(times)}
    if args.live:
        job_id = "audit-only-in-memory"
        timings = report["live_stages_ms"] = {}
        def timed(name, function):
            def call(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return function(*args, **kwargs)
                finally:
                    timings[name] = (time.perf_counter() - start) * 1000
                    print(name, round(timings[name], 2), flush=True)
            return call
        with (
            patch.dict(server.CATALOG_GENERATOR_JOBS, {job_id: {"id": job_id}}),
            patch.object(server, "pncp_purchase_metadata", timed("metadata", server.pncp_purchase_metadata)),
            patch.object(server, "identify_items_from_pncp_link", timed("items", server.identify_items_from_pncp_link)),
            patch.object(server, "catalog_generator_document_candidates", timed("documents", server.catalog_generator_document_candidates)),
            patch.object(server, "normalize_items", timed("analysis", server.normalize_items)),
            patch.object(server, "saved_catalog_repertoire", timed("saved_repertoire", server.saved_catalog_repertoire)),
        ):
            start = time.perf_counter()
            server.run_catalog_generator_job(job_id, "https://pncp.gov.br/app/editais/63025530000104/2026/3356", ["1"])
            job = server.catalog_generator_job(job_id)
            report["live"] = {"total_ms": (time.perf_counter() - start) * 1000, "status": job["status"], "warnings": (job.get("result") or {}).get("warnings"), "error": job.get("error")}
    output = ROOT / "reports/catalog-audit"
    output.mkdir(parents=True, exist_ok=True)
    (output / "backend.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
