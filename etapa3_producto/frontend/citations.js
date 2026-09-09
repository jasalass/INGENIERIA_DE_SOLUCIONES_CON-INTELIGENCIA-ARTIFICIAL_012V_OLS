"use strict";

// Solo convierte referencias que existen en las fuentes de ESTA respuesta.
// No interpreta Markdown ni HTML del modelo; lo demás sigue siendo texto.
function citationSegments(text, sources) {
  const numbers = new Map(sources.map((source, index) => [source.chunk_id, index + 1]));
  const segments = [];
  let start = 0;
  for (const match of text.matchAll(/\[([^\[\]\r\n]+)\]/g)) {
    const number = numbers.get(match[1]);
    if (!number) continue;
    if (match.index > start) segments.push({ text: text.slice(start, match.index) });
    segments.push({ number });
    start = match.index + match[0].length;
  }
  if (start < text.length) segments.push({ text: text.slice(start) });
  return segments;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { citationSegments };
}
