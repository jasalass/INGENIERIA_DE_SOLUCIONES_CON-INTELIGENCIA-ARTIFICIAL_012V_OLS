"""Compara en solo lectura el índice SQL con el corpus original, sin API externa."""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from etapa2_rag.rag.db import get_connection  # noqa: E402


def audit():
    source_path = ROOT / "etapa1_datos/data/processed/chunks.json"
    corpus = {c["chunk_id"]: c for c in json.loads(source_path.read_text(encoding="utf-8"))}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM chunks ORDER BY chunk_id")
            columns = [d.name for d in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    fields = [k for k in columns if k != "embedding"]
    matching = 0
    valid_vectors = 0
    for row in rows:
        original = corpus.get(row["chunk_id"], {})
        metadata = {k: row[k].isoformat() if isinstance(row[k], date) else row[k] for k in fields}
        matching += all(metadata[k] == original.get(k) for k in fields)
        vector = row["embedding"]
        valid_vectors += len(vector) == 1024 and bool(np.isfinite(vector).all()) and bool(np.any(vector))
    report = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "corpus_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "expected_rows": len(corpus), "database_rows": len(rows), "matching_ids": set(corpus) == {r["chunk_id"] for r in rows}, "exact_text_and_metadata_rows": matching, "valid_1024d_vectors": valid_vectors, "external_calls": 0}
    report["passed"] = len(rows) == len(corpus) == matching == valid_vectors and report["matching_ids"]
    output = ROOT / "docs/evidencia_local"
    output.mkdir(exist_ok=True)
    path = output / f"index_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    print(f"Evidencia: {path}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    audit()
