"use strict";
const $ = (id) => document.getElementById(id);
const welcome = $("welcome").cloneNode(true);
let conversationId = null;
let busy = false;
let online = false;
let sourceGroup = 0;

function updateControls() {
  $("send").disabled = busy || !online || !$("question").value.trim();
  $("new-chat").disabled = busy;
  $("scope").disabled = busy;
  $("question").disabled = busy;
  document.querySelectorAll("[data-question]").forEach((button) => { button.disabled = busy; });
  $("counter").textContent = `${$("question").value.length} / 2000`;
  const scopeLabel = $("scope").selectedOptions[0].textContent;
  $("advanced-label").textContent = $("scope").value ? `Búsqueda avanzada · ${scopeLabel}` : "Búsqueda avanzada";
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}

function appendMessage(role, text) {
  $("welcome")?.remove();
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const author = document.createElement("div");
  author.className = "message-author";
  author.textContent = role === "user" ? "TÚ" : "CONSULTA · ASISTENTE";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;
  article.append(author, body);
  $("messages").append(article);
  return article;
}

function appendSources(article, result) {
  const list = document.createElement("div");
  list.className = "source-list";
  const group = ++sourceGroup;
  const targets = [];
  for (const [index, source] of result.sources.entries()) {
    const details = document.createElement("details");
    details.className = "source";
    details.id = `source-${group}-${index + 1}`;
    const summary = document.createElement("summary");
    summary.textContent = `[${index + 1}] ${source.label} · Fragmento ${source.parte}`;
    const text = document.createElement("p");
    text.textContent = source.texto;
    const metadata = document.createElement("small");
    metadata.textContent = `Documento de origen: Ley ${source.documento_origen} · ${source.fuente}`;
    const link = document.createElement("a");
    link.textContent = "Abrir PDF de referencia ↗";
    link.href = source.pagina_pdf ? `/api/source.pdf#page=${Number(source.pagina_pdf)}` : "/api/source.pdf";
    link.target = "_blank";
    link.rel = "noopener";
    details.append(summary, metadata, text, link);
    list.append(details);
    targets.push({ details, summary, source });
  }
  const body = article.querySelector(".message-body");
  body.replaceChildren();
  for (const segment of citationSegments(result.answer, result.sources)) {
    if (segment.text !== undefined) {
      body.append(document.createTextNode(segment.text));
      continue;
    }
    const target = targets[segment.number - 1];
    const reference = document.createElement("button");
    reference.type = "button";
    reference.className = "citation-ref";
    reference.textContent = `[${segment.number}]`;
    reference.title = target.source.label;
    reference.setAttribute("aria-label", `Ver fuente ${segment.number}: ${target.source.label}`);
    reference.setAttribute("aria-controls", target.details.id);
    reference.addEventListener("click", () => {
      target.details.open = true;
      target.summary.focus({ preventScroll: true });
      target.details.scrollIntoView({ block: "nearest", behavior: "instant" });
    });
    body.append(reference);
  }
  const meta = document.createElement("p");
  meta.className = "answer-meta";
  const sourceInfo = result.answer_kind === "conversation" ? "Contexto de esta conversación" : `${result.sources.length} ${result.sources.length === 1 ? "fragmento citado" : "fragmentos citados"}`;
  meta.textContent = `${sourceInfo} · Turno ${result.turn_count} · ${result.mode === "demo" ? "Demostración sin LLM" : result.mode === "groq" ? "Groq · búsqueda por palabras" : "Motor conectado"}`;
  article.append(list, meta);
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health", { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error("health");
    const health = await response.json();
    online = true;
    $("connection").textContent = "● Servicio local conectado";
    $("mode-title").textContent = health.mode === "demo" ? "Modo de prueba · sin IA generativa" : health.mode === "groq" ? "RAG básico · Groq configurado" : "RAG vectorial · Mistral + Groq";
    $("mode-description").textContent = health.mode === "demo" ? "Búsqueda por palabras y extractos del documento. No usa Gemini ni pgvector." : health.mode === "groq" ? `${health.model} · Memoria de 6 intercambios. Búsqueda por palabras, aún sin pgvector. Tus mensajes y los fragmentos se envían a Groq al consultar.` : `pgvector + mistral-embed · ${health.model} · Memoria de 6 intercambios. Consultas documentales a Mistral; mensajes, historial y fuentes a Groq.`;
    $("mode-banner").classList.remove("offline");
  } catch {
    online = false;
    $("connection").textContent = "● Servicio sin conexión";
    $("mode-title").textContent = "La API no está disponible";
    $("mode-description").textContent = "Se volverá a comprobar la conexión automáticamente.";
    $("mode-banner").classList.add("offline");
  }
  updateControls();
}

$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("question").value.trim();
  if (busy || !online || !message) return;
  busy = true;
  updateControls();
  showError("");
  const userMessage = appendMessage("user", message);
  const pending = document.createElement("p");
  pending.className = "pending";
  pending.textContent = "Consultando los fragmentos…";
  $("messages").append(pending);
  $("messages").scrollTop = $("messages").scrollHeight;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId, filters: $("scope").value ? { ambito: $("scope").value } : {} }),
      signal: AbortSignal.timeout(65000),
    });
    if (!response.ok) {
      if (response.status === 404) conversationId = null;
      const payload = await response.json().catch(() => ({}));
      throw new Error(typeof payload.detail === "string" ? payload.detail : "No se pudo enviar la consulta. Revisa el texto e intenta nuevamente.");
    }
    const result = await response.json();
    conversationId = result.conversation_id;
    pending.remove();
    const answer = appendMessage("assistant", result.answer);
    appendSources(answer, result);
    $("question").value = "";
    // Mantener el comienzo de la respuesta visible incluso cuando contiene varios extractos.
    answer.scrollIntoView({ block: "start", behavior: "smooth" });
  } catch (error) {
    userMessage.remove();
    const lostConnection = error.name === "TimeoutError" || error instanceof TypeError;
    if (lostConnection) conversationId = null;
    showError(lostConnection ? "Se perdió la conexión o se agotó el tiempo. Conservamos tu pregunta; el siguiente envío iniciará una conversación nueva." : error.message);
  } finally {
    pending.remove();
    busy = false;
    updateControls();
    $("question").focus({ preventScroll: true });
  }
});

$("new-chat").addEventListener("click", async () => {
  if (busy) return;
  const previousId = conversationId;
  conversationId = null;
  $("messages").replaceChildren(welcome.cloneNode(true));
  $("question").value = "";
  $("scope").value = "";
  $("advanced-search").open = false;
  showError("");
  updateControls();
  $("question").focus();
  if (previousId) {
    try {
      const response = await fetch(`/api/conversations/${previousId}`, { method: "DELETE", signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error("delete");
    } catch { showError("Nueva conversación iniciada. La memoria anterior no pudo borrarse del servidor; expirará automáticamente."); }
  }
});
$("messages").addEventListener("click", (event) => {
  const button = event.target.closest("[data-question]");
  if (!button || busy) return;
  $("question").value = button.dataset.question;
  $("scope").value = button.dataset.scope || "";
  $("advanced-search").open = Boolean($("scope").value);
  updateControls();
  $("question").focus();
});
$("question").addEventListener("input", updateControls);
$("scope").addEventListener("change", updateControls);
$("question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("chat-form").requestSubmit();
  }
});
checkHealth();
setInterval(checkHealth, 15000);
