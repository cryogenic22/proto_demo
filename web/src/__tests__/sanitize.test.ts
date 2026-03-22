import { describe, it, expect } from "vitest";
import { sanitizeHtml } from "@/lib/sanitize";

describe("sanitizeHtml", () => {
  it("strips script tags", () => {
    const input = '<p>Hello</p><script>alert("xss")</script>';
    const result = sanitizeHtml(input);
    expect(result).not.toContain("<script>");
    expect(result).toContain("<p>Hello</p>");
  });

  it("strips onerror attributes", () => {
    const input = '<img src="x" onerror="alert(1)">';
    const result = sanitizeHtml(input);
    expect(result).not.toContain("onerror");
  });

  it("preserves safe HTML elements", () => {
    const input = "<p>Text</p><strong>Bold</strong><ul><li>Item</li></ul><table><tr><td>Cell</td></tr></table>";
    const result = sanitizeHtml(input);
    expect(result).toContain("<p>");
    expect(result).toContain("<strong>");
    expect(result).toContain("<ul>");
    expect(result).toContain("<table>");
  });

  it("strips iframe", () => {
    const input = '<iframe src="evil.com"></iframe>';
    const result = sanitizeHtml(input);
    expect(result).not.toContain("<iframe>");
  });

  it("strips javascript: protocol in href", () => {
    const input = '<a href="javascript:alert(1)">click</a>';
    const result = sanitizeHtml(input);
    expect(result).not.toContain("javascript:");
  });
});
