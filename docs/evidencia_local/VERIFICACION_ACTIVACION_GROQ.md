# Verificación de activación Groq — 08-09-2026 (Chile)

La clave fue aportada por el usuario en `.env`. No se incluye en este informe.
Modelo: `qwen/qwen3.6-27b`; recuperación léxica, no vectorial.

## Ajuste observado

La clave permitió una llamada directa al proveedor. El error inicial del chat
fue HTTP 429 `rate_limit_exceeded`, tipo `tokens`: el proveedor rechazaba 2000
tokens de salida solicitados frente a un límite de 1000 por minuto. Se redujo
el máximo por llamada a 512, configurable con `LLM_MAX_TOKENS`. El ajuste no
elimina los límites acumulados; puede ser necesario espaciar consultas.

## Informe de verificación

| Control | Resultado |
|---|---|
| Build | PASS: imagen Docker reconstruida y API saludable en modo groq |
| Sintaxis | PASS: Python compileall y JavaScript node --check |
| Tipos estáticos | No ejecutado: pyright no disponible/configurado |
| Lint | No ejecutado: ruff no disponible/configurado |
| Pruebas offline | PASS: 33/33; incluye rechazo de límites de salida inválidos y comprobación de 512 en la petición del SDK |
| Cobertura | No medida; no se afirma alcanzar un porcentaje |
| Dependencias | PASS: pip check sin incompatibilidades |
| Secretos | `.env` ignorado por Git; búsqueda de la clave configurada en 22 archivos de código/documentación/configuración sin coincidencias. No es una auditoría integral de seguridad |
| Diff | git diff --check sin errores; fuentes de etapa1 y PDF sin cambios; no push |

Guía aplicada: verification-loop. Se separaron controles offline y evidencia
del proveedor real, dejando explícitos los controles no ejecutados.

## Evidencia real y límites

**Segunda corrida completa: 7/7 casos HTTP correctos** en modo Groq:
[groq_http_20260909T011249432805Z.json](groq_http_20260909T011249432805Z.json).
Cinco casos invocan al modelo (presentación, recuerdo, sesión nueva, artículo y
seguimiento); los dos casos sin fragmentos se abstienen localmente y no gastan
tokens de generación. Los cinco turnos con modelo tardaron aproximadamente
0,74–1,25 segundos según el servidor, sin contar pausas entre pruebas.
El seguimiento mantiene el artículo 4 y su respuesta está respaldada por el
fragmento citado. Esta muestra limitada no acredita exactitud general.

La primera corrida HTTP está en
[groq_http_20260909T010926168687Z.json](groq_http_20260909T010926168687Z.json):
4 de 5 casos intentados correctos. Recuerdo de Felipe, separación de sesiones y
respuesta con cita al artículo 4 comprobados; seguimiento rechazado con 503 de
validación. Se conservó el fallo como evidencia. Una llamada directa posterior
del seguimiento produjo una generación válida, pero no establece que todas las
variaciones del modelo sean correctas.

La respuesta sobre artículo 4 se contrastó con el texto recuperado: los derechos
enumerados y la condición relativa a herederos figuraban en el fragmento. Es
comprobación de fidelidad al corpus, no asesoramiento ni validación de vigencia.
La pregunta de nombre en sesión nueva recibió que no había dato en la conversación.

La API mantiene la validación de fuentes y no guarda turnos fallidos. La memoria
es temporal de seis intercambios; recargar la página inicia otra sesión.
