"""Prueba real opt-in: consume cuota de Groq, solo con datos sintéticos.

No carga claves: consulta la API local. Genera evidencia nueva y borra únicamente
las sesiones creadas por esta prueba. Los checks no sustituyen revisión semántica.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from .demo import normalize


def overview_supported(response):
    answer = normalize(response["answer"])
    return (not response["insufficient_context"]
            and "[doc-21719-p1]" in answer
            and "datos personales" in answer and "agencia" in answer
            and any(s["chunk_id"] == "doc-21719-p1" and s["pagina_pdf"] == 1 for s in response["sources"]))


def run(pause_seconds: float = 20):
    sessions = set()
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8080", timeout=60) as client:
        health = client.get("/api/health").json()
        if health.get("mode") not in {"groq", "live"}:
            raise RuntimeError("Requiere API local con proveedor real; no se acepta evidencia de demo")

        def ask(name, message, cid=None, filters=None, check=lambda r: True):
            if results:
                time.sleep(pause_seconds)
            payload = {"message": message, "conversation_id": cid, "filters": filters or {}}
            response = client.post("/api/chat", json=payload)
            data = response.json()
            if response.is_success:
                sessions.add(data["conversation_id"])
            valid = response.is_success and check(data)
            results.append({"case": name, "request": payload, "status": response.status_code, "passed": valid, "response": data})
            print(f"{name}: {'PASS' if valid else 'FAIL'} (HTTP {response.status_code})", flush=True)
            if not response.is_success:
                raise RuntimeError("Consulta fallida: ver evidencia local; no hay reintento automático")
            return data

        try:
            if health["mode"] == "live":
                overview = ask("Regresión: pregunta exacta del usuario", "De qué trata la ley 21.719?", check=overview_supported)
                ask("Relación entre ley fuente y ley modificada", "¿Por qué aparece la Ley 19.628 si el documento es la Ley 21.719?", overview["conversation_id"], check=lambda r: not r["insufficient_context"] and "19.628" in r["answer"] and "21.719" in r["answer"] and "modific" in normalize(r["answer"]) and "[doc-21719-p1]" in r["answer"])
                ask("Resumen general del PDF", "Resume de qué trata este documento PDF", check=overview_supported)
                ask("Número de ley sin separador", "¿Cuál es el objetivo de la ley 21719?", check=overview_supported)
                ask("Otra ley no se confunde con el documento", "¿De qué trata la Ley 99.999?", check=lambda r: r["insufficient_context"])
            first = ask("Presentación", "Hola, me llamo Felipe", check=lambda r: r["answer_kind"] == "conversation" and not r["sources"])
            ask("Recuerdo de nombre", "¿Cómo me llamaba?", first["conversation_id"], check=lambda r: "felipe" in r["answer"].lower() and not r["sources"] and r["turn_count"] == 2)
            ask("Sesión nueva sin nombre", "¿Cómo me llamo?", check=lambda r: "felipe" not in r["answer"].lower() and r["insufficient_context"] and not r["sources"])
            law = ask("Artículo con cita", "¿Qué dice el artículo 4?", check=lambda r: bool(r["sources"]) and all(s["articulo"] == "4" and f"[{s['chunk_id']}]" in r["answer"] for s in r["sources"]))
            ask("Seguimiento documental", "¿Y eso cómo funciona?", law["conversation_id"], check=lambda r: "4" in r["retrieval_query"] and r["turn_count"] == 2 and bool(r["sources"]))
            ask("Artículo inexistente", "¿Qué dice el artículo 999?", check=lambda r: r["insufficient_context"] and not r["sources"])
            ask("Filtro transitorio", "¿Qué dice el artículo 4?", filters={"ambito": "transitorio"}, check=lambda r: r["insufficient_context"] and not r["sources"])
            if health["mode"] == "live":
                ask("Búsqueda semántica", "¿Qué derechos tiene el titular de datos personales?", check=lambda r: bool(r["sources"]) and any(s["articulo"] == "4" for s in r["sources"]))
                ask("Artículo bis", "¿Qué dice el artículo 1 bis?", check=lambda r: bool(r["sources"]) and all(s["articulo"] == "1" and s["articulo_sufijo"] == "bis" for s in r["sources"]))
                ask("Transitorios con resultados", "¿Cuándo entra en vigencia la ley según sus disposiciones transitorias?", filters={"ambito": "transitorio"}, check=lambda r: bool(r["sources"]) and all(s["ambito"] == "transitorio" and s["nivel1"] for s in r["sources"]))
                ask("Fuera de tema", "¿Cómo preparo una pizza margarita?", check=lambda r: r["insufficient_context"])
        finally:
            for cid in sessions:
                client.delete(f"/api/conversations/{cid}")
            now = datetime.now(timezone.utc)
            output = Path(__file__).resolve().parents[1] / "docs/evidencia_local"
            output.mkdir(exist_ok=True)
            destination = output / f"{health['mode']}_http_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
            report = {"captured_at_utc": now.isoformat(), "health": health, "scope": "Consultas HTTP reales; checks funcionales, no evaluación jurídica exhaustiva. Datos de usuario ficticios.", "passed": sum(r["passed"] for r in results), "total": len(results), "cases": results}
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Evidencia: {destination}", flush=True)
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", help="Autoriza llamadas reales que consumen cuota")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("Requiere --run-live para consumir cuota del proveedor")
    run()
