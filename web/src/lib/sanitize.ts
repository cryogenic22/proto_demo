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

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
}
