"""Exercise one real Block 7 job and downloads on the running local app."""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
report = {}


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}), timeout=180) as response:
        return json.load(response)


start = time.perf_counter()
job = request("/catalog-generator/jobs", {
    "pncp_link": "https://pncp.gov.br/app/editais/63025530000104/2026/3356",
    "selected_item_keys": ["1"], "template_id": "modelo_proposta_goldflex.docx",
})
report["create_ms"] = (time.perf_counter() - start) * 1000
report["job_id"] = job["id"]
stages = []
while job["status"] in {"queued", "processing"}:
    if not stages or stages[-1]["stage"] != job["stage"]:
        stages.append({"stage": job["stage"], "seconds": round(time.perf_counter() - start, 3)})
        print(stages[-1], flush=True)
    time.sleep(0.9)
    job = request("/catalog-generator/jobs/" + job["id"])
report["analysis_ms"] = (time.perf_counter() - start) * 1000
report["stages"] = stages
report["status"] = job["status"]
report["warnings"] = (job.get("result") or {}).get("warnings", [])
if job["status"] == "ready":
    start = time.perf_counter()
    exported = request("/catalog-generator/jobs/" + job["id"] + "/export", {"items": job["result"]["items"]})
    report["export_ms"] = (time.perf_counter() - start) * 1000
    report["export_warnings"] = exported.get("export_warnings", [])
    report["downloads"] = {}
    for kind, file in exported["exports"].items():
        start = time.perf_counter()
        with urllib.request.urlopen(BASE + file["download_url"], timeout=30) as response:
            data = response.read()
            assert response.status == 200 and data
        if kind in {"docx", "xlsx"}:
            assert data.startswith(b"PK")
        if kind == "pdf":
            assert data.startswith(b"%PDF-")
        report["downloads"][kind] = {"bytes": len(data), "ms": (time.perf_counter() - start) * 1000}
    report["exports"] = exported["exports"]
output = ROOT / "reports/catalog-audit"
output.mkdir(parents=True, exist_ok=True)
(output / "live-http.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True), flush=True)
