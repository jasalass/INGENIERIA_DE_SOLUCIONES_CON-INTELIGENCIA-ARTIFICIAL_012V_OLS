"""Captura evidencia HTTP real de la demo levantada, sin sobrescribir resultados."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def run(base_url: str):
    def call(path, data=None, method=None):
        request = Request(base_url.rstrip("/") + path, data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type": "application/json"}, method=method)
        with urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None

    health = call("/api/health")
    if health["mode"] != "demo":
        raise RuntimeError("Este guion captura solo evidencia de demo; no invoca servicios reales")
    cases = [
        ("Derechos", "¿Qué dice el artículo 4?", {}, "4"),
        ("Ámbito territorial", "¿Qué dice el artículo 1 bis?", {}, "1"),
        ("Artículo inexistente", "¿Qué dice el artículo 999?", {}, None),
        ("Fuera del tema", "Receta pizza margarita", {}, None),
        ("Transitorios", "¿Qué establecen las disposiciones transitorias?", {"ambito": "transitorio"}, "transitorio"),
        ("Consentimiento", "¿Qué dice el artículo 11?", {}, "11"),
        ("Portabilidad", "¿Qué dice el artículo 9?", {}, "9"),
        ("Principios", "¿Qué dice el artículo 3?", {}, "3"),
        ("Control por ámbito", "¿Qué dice el artículo 4?", {"ambito": "transitorio"}, None),
        ("Trato de texto HTML", "<img src=x onerror=alert(1)> artículo 4", {}, "4"),
    ]
    results = []
    for name, question, filters, expected in cases:
        answer = call("/api/chat", {"message": question, "filters": filters})
        sources = answer["sources"]
        valid = (answer["insufficient_context"] and not sources) if expected is None else bool(sources) and all((s["ambito"] == expected if expected == "transitorio" else s["articulo"] == expected) for s in sources)
        valid = valid and all(s["texto"][:650] in answer["answer"] and f"[{s['chunk_id']}]" in answer["answer"] for s in sources)
        results.append({"name": name, "request": {"message": question, "filters": filters}, "passed": valid, "response": answer})
        if name == "Derechos":
            follow = call("/api/chat", {"message": "¿Y eso cómo funciona?", "conversation_id": answer["conversation_id"]})
            results.append({"name": "Seguimiento conversacional", "passed": follow["turn_count"] == 2 and "artículo 4" in follow["retrieval_query"], "response": follow})
        call(f"/api/conversations/{answer['conversation_id']}", method="DELETE")
    now = datetime.now(timezone.utc)
    output = Path(__file__).resolve().parents[1] / "docs/evidencia_local"
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"demo_http_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    report = {"captured_at_utc": now.isoformat(), "base_url": base_url, "scope": "Demo local: sin LLM, embeddings ni pgvector. No demuestra precisión jurídica ni retrieval semántico.", "health": health, "passed": sum(r["passed"] for r in results), "total": len(results), "cases": results}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['passed']}/{report['total']} casos correctos. Evidencia: {destination}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    run(parser.parse_args().base_url)
