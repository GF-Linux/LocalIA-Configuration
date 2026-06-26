import { describe, it, expect } from "vitest";
import { renderHintHtml } from "./renderHint";

describe("renderHintHtml", () => {
  it("mostra comment/why/nudge da dica", () => {
    const html = renderHintHtml({ comment: "C1", why: "W1", nudge: "N1" }, false);
    expect(html).toContain("C1");
    expect(html).toContain("W1");
    expect(html).toContain("N1");
  });

  it("estado vazio quando hint é null", () => {
    expect(renderHintHtml(null, false).toLowerCase()).toContain("observando");
  });

  it("estado mudo", () => {
    expect(renderHintHtml(null, true).toLowerCase()).toContain("mudo");
  });

  it("escapa HTML do conteúdo do modelo", () => {
    const html = renderHintHtml({ comment: "<script>x</script>", why: "w", nudge: "n" }, false);
    expect(html).not.toContain("<script>x");
    expect(html).toContain("&lt;script&gt;");
  });

  it("renderiza bloco de código quando há suggestion", () => {
    const html = renderHintHtml(
      { comment: "c", why: "w", nudge: "n", suggestion: "with open(f) as fh:" },
      false
    );
    expect(html).toContain("<pre><code>");
    expect(html).toContain("with open(f) as fh:");
  });

  it("escapa HTML dentro da suggestion (XSS)", () => {
    const html = renderHintHtml(
      { comment: "c", why: "w", nudge: "n", suggestion: "<script>x</script>" },
      false
    );
    expect(html).not.toContain("<script>x");
    expect(html).toContain("&lt;script&gt;");
  });

  it("não renderiza bloco de código sem suggestion", () => {
    const html = renderHintHtml({ comment: "c", why: "w", nudge: "n" }, false);
    expect(html).not.toContain("<pre>");
  });
});
