import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "p", "br", "strong", "em", "b", "i", "u",
  "ul", "ol", "li",
  "table", "thead", "tbody", "tr", "th", "td",
  "h1", "h2", "h3", "h4", "h5", "h6",
  "span", "div", "a", "sup", "sub",
  "blockquote", "pre", "code",
];

const ALLOWED_ATTR = [
  "class", "href", "title", "colspan", "rowspan", "target",
];

/**
 * Convert legacy Unicode bullet patterns to proper HTML lists.
 * PDF/Word exports often produce: <p>\uf0b7</p><p>text...</p>
 * or <p>\uf0b7 text...</p>. This converts them to <ul><li>text</li></ul>.
 */
function fixUnicodeBullets(html: string): string {
  // Pattern 1: <p>BULLET</p> followed by content — merge into list
  // Pattern 2: <p>BULLET text...</p> — convert to list item
  const bulletChars = "\uf0b7\uf0a7\u2022\u2023\u25CF\u25CB";
  const bulletRe = new RegExp(
    `<p>\\s*[${bulletChars}]\\s*</p>\\s*(?:<(?:h[34]|p)>)?\\s*(<(?:strong|em|b)>)?`,
    "g"
  );
  // Replace standalone bullet paragraphs with list item markers
  let fixed = html.replace(bulletRe, (_, inlineTag) => {
    return `<li>${inlineTag || ""}`;
  });

  // Also handle inline bullets: <p>BULLET text</p>
  const inlineBulletRe = new RegExp(
    `<p>\\s*[${bulletChars}]\\s+([^<]*)`,
    "g"
  );
  fixed = fixed.replace(inlineBulletRe, "<li>$1");

  // Wrap consecutive <li> runs in <ul> tags
  fixed = fixed.replace(
    /(<li>[\s\S]*?<\/(?:li|p|h[34])>)(?=\s*<li>|\s*$)/g,
    (match) => match
  );

  // Simple approach: wrap any <li> not inside <ul> with <ul>
  if (fixed.includes("<li>") && !fixed.includes("<ul>")) {
    fixed = fixed.replace(/(<li>)/g, "<ul>$1");
    fixed = fixed.replace(/(<\/li>)(?!\s*<li>)/g, "$1</ul>");
  }

  return fixed;
}

export function sanitizeHtml(html: string): string {
  const cleaned = fixUnicodeBullets(html);
  return DOMPurify.sanitize(cleaned, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
}
