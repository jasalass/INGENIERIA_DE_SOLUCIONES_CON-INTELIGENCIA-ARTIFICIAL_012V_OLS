# Producto de Jenaro — sistema local integrado

Estado del 09-09-2026: **modo live** con Mistral (`mistral-embed`), PostgreSQL +
pgvector y generación Groq/Qwen. Los 140 chunks originales están indexados en
esta máquina. Memoria temporal de seis intercambios, API FastAPI y chat HTML/JS.
Para reproducir el sistema desde un clon nuevo, seguir [INSTALACION.md](../INSTALACION.md).
El índice de la máquina de desarrollo no se distribuye: cada equipo debe crearlo una vez.

La API utiliza `search()` de Juan mediante `vector_backend.py`; la generación
y memoria mantienen el cliente y los patrones RA1 ya probados. No es una demo
de coincidencia de palabras. Ver [integración técnica](INTEGRACION_JUAN.md).

## Arranque habitual en este equipo

Desde la raíz del clon, con Docker Desktop iniciado:

```powershell
docker compose up -d --build
docker compose ps
```

- Chat: <http://localhost:8080>.
- Swagger: <http://localhost:8000/docs>.
- Salud del proceso: <http://localhost:8000/health>.
- PostgreSQL para scripts locales: `127.0.0.1:5433`.

Compose levanta db, api y frontend; sus puertos están limitados a loopback.
La base persiste en `ley21719-jenaro_pgdata`. Detener con
`docker compose stop`; volver a iniciar con `docker compose up -d`.
No ejecutar `down -v`: borraría la base indexada.
No levantar simultáneamente el Compose independiente de etapa2 en el mismo puerto.

## Configuración en otro equipo

1. Copiar `.env.example` a `.env` solo si no existe.
2. Configurar `MISTRAL_API_KEY` para embeddings y `LLM_API_KEY` para Groq.
3. Elegir una contraseña propia para `POSTGRES_PASSWORD` y usarla también
   en `DATABASE_URL` (usuario `rag`, BD `ley21719`, host local, puerto 5433).
   Una contraseña hexadecimal evita problemas de caracteres especiales en la URL.
4. Mantener `RAG_MODE=live` y
   `RAG_BACKEND_FACTORY=etapa3_producto.vector_backend:create_backend`.
5. Levantar e indexar con los comandos siguientes.

Las claves sin espacios pueden ir sin comillas. No compartir el `.env`,
mostrarlo en capturas ni pegarlo en el chat. Git y Docker lo excluyen.

## Primera indexación (no necesaria de nuevo en esta máquina)

```powershell
docker compose up -d --build
docker compose exec -T api python etapa2_rag/scripts/build_index.py
docker compose exec -T api python -m etapa3_producto.audit_index
```

La carga envía el corpus público a Mistral en lotes de 20 y consume cuota.
El indexador hace upsert por `chunk_id`; repetirlo vuelve a generar embeddings,
no duplica filas. No hacerlo en cada arranque. El esquema se aplica al crear
el volumen; cambiar un SQL no migra automáticamente un volumen ya existente.

La auditoría compara IDs, texto, metadatos y vectores con el corpus. Genera un
JSON nuevo en `docs/evidencia_local`; cuando se ejecuta dentro del contenedor,
copiar la evidencia a Windows si se quiere conservarla fuera del contenedor.

## Pruebas desde Windows

Si todavía no existe el entorno, crearlo con `py -3.13 -m venv .venv`.
No se distribuye ni se debe commitear ese directorio. Para ejecutar el producto
con Docker no hace falta instalar Python en el host.

```powershell
.\.venv\Scripts\python.exe -m pip install -r etapa3_producto/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s etapa3_producto/tests -v
.\.venv\Scripts\python.exe -m etapa3_producto.audit_index
.\.venv\Scripts\python.exe -m etapa3_producto.live_smoke --run-live
```

Las pruebas unitarias son offline. `audit_index` lee PostgreSQL sin llamar a
proveedores. `live_smoke --run-live` consume cuota real, usa datos ficticios,
espacia consultas y guarda evidencia nueva; elimina solo sus sesiones de prueba.
Incluye recuerdo de nombre, sesión nueva, artículo, seguimiento, inexistente,
filtros, pregunta semántica, artículo bis y pregunta fuera de tema.
Los checks funcionales no sustituyen revisar la fidelidad de las respuestas.

## Modos disponibles

| RAG_MODE | Recuperación | Generación |
|---|---|---|
| live | Mistral + ranking coseno exacto en pgvector | Groq + historial |
| groq | Coincidencia de palabras en JSON | Groq + historial |
| demo | Coincidencia de palabras en JSON | Extractos, sin LLM |

Cambiar el modo en `.env` y recrear con `docker compose up -d`.
La plantilla Compose integrada levanta la base también en demo; para una demo
sin Docker se puede ejecutar uvicorn con `RAG_MODE=demo`.

## Memoria, privacidad y límites

### Procedencia del documento (corrección del 09-09-2026)

El PDF es la Ley 21.719. Sus fragmentos pueden referenciar la Ley 19.628 porque
el artículo primero de la 21.719 introduce modificaciones en ella. El contexto
enviado al LLM distingue `documento_origen` de `ley_referenciada`.

Las búsquedas sin filtros ni artículo concreto, cuando recuperan resultados,
se amplían con un fragmento padre `doc-21719-p1`: título y encabezado originales
de página 1, extraídos mecánicamente, no una respuesta escrita a mano. Es una
fuente adicional a los `top_k` resultados vectoriales; no tiene score vectorial.
No se añadió una fila al índice ni se modificaron los 140 chunks de Pamela.
La fuente se muestra y puede citarse; su enlace abre el PDF en página 1.

El manifiesto `etapa3_producto/document_context.json` registra la huella del PDF;
si cambia el archivo, el backend exige regenerar y revisar el contexto:

```powershell
.\.venv\Scripts\python.exe -m etapa3_producto.build_document_context
```

Requiere PyMuPDF del `requirements.txt` raíz. El servidor usa el JSON derivado,
sin necesidad de instalar el extractor. Las búsquedas vacías, de un artículo
específico o filtradas no se amplían con esta fuente general. Esto evita que
el contexto padre oculte una abstención legítima o salte el filtro elegido.

### Límites generales

- Últimos seis intercambios en RAM, un worker, hasta 100 conversaciones, TTL de una hora.
- Recargar inicia una sesión nueva; reiniciar API elimina la memoria. Nueva consulta
  pide borrar la sesión anterior. No hay cuentas ni historial permanente.
- El historial va a Groq para reformular y responder. Las consultas documentales
  reformuladas van a Mistral para obtener embeddings; pueden incluir contexto del
  usuario. Usar datos ficticios, no información sensible.
- `LLM_MAX_TOKENS=512`: esta cuenta rechazó 2000 por su cuota de salida.
  Un turno puede hacer dos llamadas Groq y una Mistral; pueden aparecer límites.
- Proveedores con timeout y sin fallback a demo; SQL con parámetros y timeout.
  Los turnos fallidos no se guardan. La UI permite reintentar.
- Se valida pertenencia de IDs y citas visibles; eso no demuestra fidelidad semántica.
  El corpus es modificatorio, no consolidado; no inferir vigencia por metadatos.
- Las búsquedas numéricas aplican filtro SQL y distinguen base/bis/ter.
  Los filtros están en Búsqueda avanzada y se restablecen con Nueva consulta.
- Las respuestas se muestran con `textContent`; no se ejecuta HTML generado.
  No hay tracing remoto ni logs de prompts/claves.
- `/health` comprueba el proceso/configuración, no disponibilidad continua de
  proveedores ni que el corpus siga íntegro. Para la base usar `audit_index`.
- Es una aplicación académica local, no una plataforma multiusuario pública.

## Referencias y evidencia

### Presentación de citas

La interfaz muestra referencias numeradas `[1]`, `[2]`, etc., en lugar de los
IDs internos. Cada botón abre y enfoca su fuente; admite teclado y tiene nombre
accesible. La numeración es local a cada respuesta y se conserva al repetir una
cita. API, respuestas originales y validación siguen usando `chunk_id`.
Se construye texto/DOM sin interpretar HTML del modelo; las referencias no
reconocidas no se transforman en enlaces. Los códigos no se muestran en los
metadatos visibles, pero se mantienen en el contrato y evidencias.

Pruebas del formato: `node --test etapa3_producto/tests/test_citations.cjs` (6/6).
Verificación del 09-09-2026: 50/50 tests Python; consulta real desde navegador,
referencias repetidas, clic en `[2]`, apertura con Enter, foco en la fuente y
revisión visual correctos. Sin cambios en motor, prompts, datos ni credenciales.
En el Compose habitual (8080), el frontend está montado: basta recargar con
Ctrl+F5. No fue necesario reiniciar la API ni perder su memoria.

- [Referencias docentes y RA](../docs/REFERENCIAS_DOCENTES_JENARO.md).
- [Auditoría de índice](../docs/evidencia_local/index_audit_20260909T163607122077Z.json).
- [Informe de integración vectorial](../docs/INTEGRACION_VECTORIAL_20260909.md).
