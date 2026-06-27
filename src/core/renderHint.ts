import type { Hint } from "./responseParser";
import type { Panorama } from "./panorama";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function renderHintHtml(hint: Hint | null, muted: boolean): string {
  if (muted) return `<div class="empty">🔇 Professor em mudo.</div>`;
  if (!hint) return `<div class="empty">🎓 Observando seu código…</div>`;
  const suggestion = hint.suggestion
    ? `<div class="suggestion"><b>Sugestão:</b><pre><code>${esc(hint.suggestion)}</code></pre></div>`
    : "";
  const source = hint.source
    ? `<div class="source">📚 <a href="#">${esc(hint.source.title)}</a></div>`
    : "";
  return `
    <div class="hint">
      <div class="comment">💡 ${esc(hint.comment)}</div>
      <div class="why"><b>Por quê:</b> ${esc(hint.why)}</div>
      <div class="nudge"><b>Tente:</b> ${esc(hint.nudge)}</div>
      ${suggestion}
      ${source}
    </div>`;
}

export function renderPanoramaHtml(panorama: Panorama | null): string {
  if (!panorama) return "";
  return `
    <div class="panorama">
      <div class="pano-title">🗺️ Panorama</div>
      <div class="structure"><b>Estrutura:</b> ${esc(panorama.structure)}</div>
      <div class="next"><b>Próximo:</b> ${esc(panorama.next)}</div>
    </div>`;
}
