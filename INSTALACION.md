# Ejecutar y probar el sistema integrado

Esta guía es la entrada principal. Ejecutar todo desde la raíz del repositorio,
no desde `etapa2_rag/`. El Compose raíz levanta PostgreSQL/pgvector, API y frontend.
Los informes de `docs/` conservan estados históricos y evidencias de desarrollo.

## 1. Requisitos y clon

- Git y Docker con Compose v2; en Windows, Docker Desktop iniciado con
  contenedores Linux (habitualmente WSL2).
- Internet para descargar imágenes y consultar Mistral/Groq.
- Una clave propia de Mistral y otra de Groq con acceso al modelo configurado.
- Puertos locales 8080, 8000 y 5433 disponibles. No levantar a la vez el
  Compose independiente de etapa 2.

```powershell
git clone --branch codex/etapa3-producto-local https://github.com/jasalass/INGENIERIA_DE_SOLUCIONES_CON-INTELIGENCIA-ARTIFICIAL_012V_OLS.git asistente-ley
cd asistente-ley
```

No se incluye `.venv`, `.env` ni el volumen de PostgreSQL. Docker instala las
dependencias del servidor automáticamente; Python local es opcional para tests.

## 2. Configuración privada

Copiar la plantilla **solo si no existe** un `.env`:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
```

En macOS/Linux: `test -e .env || cp .env.example .env`, y editar con tu editor.

| Variable | Qué configurar |
| --- | --- |
| `MISTRAL_API_KEY` | Clave de tu cuenta Mistral para embeddings. |
| `LLM_API_KEY` | Clave de tu cuenta Groq para respuestas y memoria. No poner aquí la clave Mistral. |
| `POSTGRES_PASSWORD` | Contraseña propia, preferentemente aleatoria hexadecimal. |
| `DATABASE_URL` | Sustituir `CAMBIAR` por esa misma contraseña, sin cambiar host/puerto/base de la plantilla. La usan los scripts del host; Docker construye su URL interna. |
| `RAG_MODE` / `RAG_BACKEND_FACTORY` | Mantener `live` y el adaptador de la plantilla. |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_MAX_TOKENS` | Mantener los valores probados de Groq/Qwen, con límite de salida 512. El modelo puede cambiar de disponibilidad; no cambiarlo sin repetir pruebas. |
| `MISTRAL_BASE_URL`, `MISTRAL_EMBED_MODEL` | Mantener el endpoint oficial y `mistral-embed`, compatibles con vectores de 1024 dimensiones. |

`GROQ_API_KEY` es una alternativa opcional de etapa 3; dejarla vacía si ya usas
`LLM_API_KEY`. `POSTGRES_USER`, `POSTGRES_DB` y `POSTGRES_PORT` se documentan
para compatibilidad con etapa 2; el Compose raíz fija `rag`, `ley21719` y `5433`.

Las claves simples pueden ir sin comillas. Nunca subir `.env`, pegar sus valores
en un issue ni mostrarlo en una captura. Cambiar la contraseña en `.env` no
cambia automáticamente la contraseña de una base previamente creada.

## 3. Arranque e indexación inicial

```powershell
docker compose up -d --build --wait
docker compose exec -T api python etapa2_rag/scripts/build_index.py
docker compose exec -T api python -m etapa3_producto.audit_index
docker compose ps
```

La primera carga envía el corpus público a Mistral y consume cuota. Debe finalizar
con **140 filas**; la auditoría debe indicar `passed: true`, 140 coincidencias y
140 vectores válidos. Si la carga falla por cuota, corregir el problema y volver
a ejecutarla: hace upsert, no duplica filas, pero vuelve a consumir embeddings.

La auditoría ejecutada en Docker guarda su JSON dentro del contenedor. Para
conservarlo fuera, copiar la ruta exacta que imprime con
`docker compose cp api:/app/docs/evidencia_local/NOMBRE.json ./NOMBRE.json`.

Abrir:

- Chat: <http://localhost:8080>.
- API interactiva: <http://localhost:8000/docs>.
- Estado del proceso: <http://localhost:8080/api/health>.

**Health no verifica las claves ni que el índice esté completo**: por eso se
ejecutan la auditoría y las consultas siguientes. El banner debe indicar RAG
vectorial, no modo demo. El índice vive en el volumen Docker de esta máquina.

## 4. Prueba manual breve

1. «De qué trata la ley 21.719?» → resumen con citas numeradas.
2. Pulsar `[1]` → abre la fuente; el enlace permite consultar el PDF.
3. «¿Por qué aparece la Ley 19.628?» → explicar la relación con la ley modificatoria.
4. Nueva consulta: «Hola, me llamo Felipe», luego «¿Cómo me llamaba?» → recordar Felipe.
5. Nueva consulta: «¿Cómo me llamo?» → no heredar el nombre anterior.
6. «¿Qué dice el artículo 999?» → abstención, no inventar un artículo.

La memoria es temporal: recargar, reiniciar la API o dejar expirar la sesión la
interrumpe. Se conservan seis intercambios, no un historial permanente.

## 5. Tests automatizados (opcionales, host)

Instalar Python 3.13. Para tests de citas también se requiere Node.js con `node:test`.
Configurar primero `.env` como arriba; los tests unitarios simulan proveedores,
no consumen cuota aunque lean variables de configuración.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r etapa3_producto/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s etapa3_producto/tests -v
node --test etapa3_producto/tests/test_citations.cjs
```

En macOS/Linux, usar `python3 -m venv .venv` y `.venv/bin/python`.
Para evaluar la API levantada **con consumo real de cuota**:

```powershell
.\.venv\Scripts\python.exe -m etapa3_producto.live_smoke --run-live
```

El guion tarda varios minutos porque espacia consultas. Genera un JSON nuevo en
`docs/evidencia_local/` y borra solo sus conversaciones de prueba. 50 tests Python,
6 tests JavaScript y 16 checks HTTP fueron verificados durante el desarrollo.
Los checks no garantizan fidelidad jurídica: ver el
[hallazgo pendiente del artículo 1 bis](docs/CORRECCION_CONTEXTO_DOCUMENTAL_20260909.md).

## 6. Siguientes arranques y problemas habituales

```powershell
docker compose stop
docker compose up -d --wait
```

No volver a indexar en cada arranque. Tras cambios de código o `.env`, ejecutar
`docker compose up -d --build --wait`; recargar el navegador con Ctrl+F5.
**No ejecutar `docker compose down -v`** salvo que se quiera borrar la base.

- **Docker no responde:** abrir Docker Desktop y esperar a que inicie el motor.
- **Puerto ocupado:** detener el otro servicio/Compose que usa ese puerto; no
  ejecutar ambos Compose del proyecto al mismo tiempo.
- **Credenciales rechazadas / 401:** revisar proveedor de cada clave y permisos.
- **429:** esperar y revisar cuota del proveedor; no reenviar continuamente.
- **Modelo no disponible:** comprobar acceso a `LLM_MODEL`; cambiarlo exige pruebas.
- **No hay fuentes:** confirmar indexación y que Búsqueda avanzada no esté filtrando.
- **PDF cambiado:** regenerar su contexto con el extractor documentado en
  [etapa 3](etapa3_producto/README.md); nunca editar su huella para saltar el control.

La aplicación está limitada a loopback para pruebas académicas. No exponerla
públicamente sin autenticación y endurecimiento adicionales. Preguntas y contexto
se envían a proveedores externos: usar datos ficticios en las pruebas.
