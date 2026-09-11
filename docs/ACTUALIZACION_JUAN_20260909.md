# Actualización del trabajo de Juan — 09-09-2026

Actualización posterior: la integración y el indexado ya están completados
localmente; ver [resultado verificado](INTEGRACION_VECTORIAL_20260909.md).
Este documento conserva el diagnóstico al momento del pull.

## Incorporado localmente

- Remoto: `origin`, repositorio del equipo `jasalass/INGENIERIA_DE_SOLUCIONES_CON-INTELIGENCIA-ARTIFICIAL_012V_OLS`.
- Rama mantenida: `codex/etapa3-producto-local`.
- Actualización fast-forward desde `158c8c4` hasta `f82fdd8` (dos commits).
- `184d131`: normalización de `Docs/` a `docs/`.
- `f82fdd8`: motor RAG de Juan, esquema SQL, indexador, pruebas manuales y documentación.
- No se hizo push ni un commit adicional del avance de Jenaro.

Se aplicó la guía git-workflow: fetch e inspección previa, respaldo local,
fast-forward y restauración del README con nuestros avisos locales. No hubo
conflictos. Los cambios propios continúan sin publicar.

## Preservación del avance

El `.env` no fue reemplazado ni incorporado al respaldo: su hash antes/después de
la actualización coincidió, y Git sigue ignorándolo. No se expuso su contenido.
La plantilla `.env.example` conserva las opciones de Juan y añade las de nuestro
producto; la configuración real sigue usando Groq/Qwen y 512 tokens de salida.

Respaldo sin secretos dentro del clon:
`.git/codex-backups/antes-juan-5c036757923f44cd8931bd909b921c81/`.
Contiene README, configuración no secreta, plantilla, producto y documentos
locales anteriores. Además se conserva el stash del README
`83fe4247212f9c010e7d66ecbf524253deaf55f5`, ya aplicado correctamente. No es
necesario volver a aplicarlo; queda como recuperación.

La carpeta física se normalizó a `docs` también en Windows. Se actualizaron las
rutas del PDF en nuestra API y Dockerfile, los generadores de evidencia y enlaces
de la guía del producto. Los documentos/evidencias locales se conservaron. El
contenido del PDF y de los chunks no se modificó.

## Qué entregó Juan

| Componente | Código recibido |
|---|---|
| Embeddings | `etapa2_rag/rag/embeddings.py`: API Mistral, `mistral-embed`, 1024 dimensiones |
| Base vectorial | `etapa2_rag/docker-compose.yml` y `sql/001_schema.sql`: PostgreSQL/pgvector, tabla e índices |
| Indexación | `scripts/build_index.py`: lectura de los 140 chunks y upsert por lotes |
| Recuperación | `rag/retrieval.py`: similitud coseno y filtros SQL por artículo, título y ámbito |
| Generación | `rag/prompts.py` y `rag/chain.py`: contexto + historial + modelo compatible con OpenAI |
| Evaluación | `scripts/test_retrieval.py`: ocho preguntas con resultados para revisión manual; no son ocho asserts automatizados |

El README de Juan declara 140/140 chunks indexados y ocho consultas revisadas en
su máquina. Esto es evidencia declarada por él, no una ejecución realizada en
este equipo. Git trae el código y esquema; no trae su volumen PostgreSQL ni sus
credenciales.

## Qué falta para conectarlo a nuestro chat

1. Configurar `MISTRAL_API_KEY` localmente. La comprobación mostró que no está
   presente; `DATABASE_URL` tampoco. La clave de Groq existente es para el chat,
   no sustituye la credencial que solicita el código de embeddings de Juan.
2. Levantar una base local e indexar los 140 chunks con Mistral. Docker Desktop
   estaba apagado/no disponible durante esta actualización (no existía el pipe
   `dockerDesktopLinuxEngine`). No se creó ni se modificó una base.
3. Conectar el contrato de etapa 2 a la API. `answer_question()` devuelve texto y
   metadatos resumidos; nuestra API requiere además texto de fuente, procedencia,
   IDs citados y abstención. Hay que adaptar ese contrato, preservando memoria y
   validación, o reutilizar `search()` de Juan con nuestro generador ya probado.
4. Unificar dependencias antes de instalar todo junto: el archivo raíz recibido
   fija `langchain-core==1.6.0` y `langchain-openai==1.6.0`; nuestro producto usa
   1.6.2 y 1.6.1. No se degradó ni alteró el entorno existente en esta actualización.
5. Conservar la detección de artículos explícitos al pasar a búsqueda vectorial.
   Juan documenta que por similitud sola puede no recuperarse el artículo pedido.
   Su lista de filtros tampoco incluye `articulo_sufijo`, utilizado por nuestro
   chat; la integración debe cubrir los artículos bis/ter sin mezclarlos.
6. Mantener límites de salida y tiempos de espera acordes con nuestra cuenta,
   fuentes completas, etiquetas de transitorios y metadatos de ley referenciada.
   Nuestro modelo Qwen no se cambió al GPT-OSS del ejemplo de Juan.

No se activó automáticamente la etapa 2 ni se llamó a Mistral/Groq en esta tarea.
El trabajo pedido fue traer cambios; la integración y su evaluación real son
el siguiente paso, no una consecuencia automática de actualizar Git.

## Verificación realizada

- HEAD actualizado a `f82fdd8`, conservando los cambios locales.
- 33/33 pruebas offline de etapa 3 correctas después de ajustar rutas.
- Sintaxis Python de etapa 2 comprobada con compileall, sin ejecutar indexación.
- `pip check`: entorno existente sin incompatibilidades.
- Intento de reconstrucción Docker bloqueado por motor apagado; no se afirma
  arranque ni prueba HTTP después del cambio de rutas.
- Fuentes originales preservadas; comprobar el diff contra `origin/main` permite
  distinguir nuestras adaptaciones del código recibido.
