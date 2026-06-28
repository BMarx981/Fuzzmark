"""Extract clickable CTAs (buttons + link-CTAs) from a rendered page.

Sibling to `fields.py`. The walker descends through the same DOM regions
— open shadow roots and same-origin iframes — and emits one record per
clickable element. Selectors across boundaries are joined with ` >>> `
matching the convention used for fields.

Buttons cover native `<button>`, `<input type=submit|button>`, and
`role="button"` elements; links cover `<a>` with a non-empty `href`.
`label` is the accessible name (aria-labelledby → aria-label →
textContent → input value → title). `disabled` is true when the element
carries `[disabled]` or `aria-disabled="true"`.
"""

from __future__ import annotations

from .models import CTA


_EXTRACT_CTAS_JS = r"""
() => {
  const cssEscape = (s) =>
    (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/([^a-zA-Z0-9_-])/g, '\\$1');

  const strAttr = (el, a) => (el.hasAttribute(a) ? el.getAttribute(a) : null);
  const boolAria = (el, a) => {
    if (!el.hasAttribute(a)) return false;
    const v = (el.getAttribute(a) || '').toLowerCase();
    return v === '' || v === 'true';
  };
  const trimTxt = (s) => (s || '').replace(/\s+/g, ' ').trim();

  const resolveId = (root, id) => {
    if (!id) return null;
    if (root.getElementById) return root.getElementById(id);
    return root.querySelector('#' + cssEscape(id));
  };

  const accessibleName = (el, root) => {
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const text = lb.split(/\s+/)
        .map((id) => resolveId(root, id))
        .filter(Boolean)
        .map((r) => trimTxt(r.textContent))
        .filter(Boolean)
        .join(' ')
        .trim();
      if (text) return text;
    }
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const tag = el.tagName.toLowerCase();
    if (tag === 'input') {
      const v = strAttr(el, 'value');
      if (v && v.trim()) return v.trim();
    }
    const txt = trimTxt(el.textContent);
    if (txt) return txt;
    const title = strAttr(el, 'title');
    if (title && title.trim()) return title.trim();
    return null;
  };

  const localSelectorFor = (el, root) => {
    if (el.id) return '#' + cssEscape(el.id);
    const tag = el.tagName.toLowerCase();
    if (el.name) return tag + '[name="' + el.name + '"]';
    const same = Array.from(root.querySelectorAll(tag));
    return tag + ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
  };

  const isDisabled = (el) =>
    el.hasAttribute('disabled') || boolAria(el, 'aria-disabled');

  const classify = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'submit').toLowerCase();
      if (t === 'submit' || t === 'button') return 'button';
      return null;
    }
    if (tag === 'a') {
      const href = strAttr(el, 'href');
      return href && href.trim() ? 'link' : null;
    }
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (role === 'button') return 'button';
    return null;
  };

  const out = [];

  const walk = (root, pathPrefix) => {
    if (!root) return;
    root.querySelectorAll('*').forEach((el) => {
      const kind = classify(el);
      if (kind) {
        const rec = {
          selector: pathPrefix + localSelectorFor(el, root),
          kind: kind,
          label: accessibleName(el, root),
          href: kind === 'link' ? strAttr(el, 'href') : null,
          disabled: isDisabled(el),
        };
        out.push(rec);
      }
      if (el.shadowRoot) {
        walk(el.shadowRoot, pathPrefix + localSelectorFor(el, root) + ' >>> ');
      }
      if (el.tagName === 'IFRAME') {
        let doc = null;
        try { doc = el.contentDocument; } catch (_) { doc = null; }
        if (doc) walk(doc, pathPrefix + localSelectorFor(el, root) + ' >>> ');
      }
    });
  };

  walk(document, '');
  return out;
}
"""


def _to_cta(raw: dict) -> CTA:
    return CTA(
        selector=raw["selector"],
        kind=raw["kind"],
        label=raw.get("label"),
        href=raw.get("href"),
        disabled=bool(raw.get("disabled", False)),
    )


def extract_ctas(
    url: str,
    timeout_ms: int = 15000,
    headless: bool = True,
    *,
    session: str | None = None,
) -> list[CTA]:
    """Load a page and return the clickable CTAs found on it.

    Discovers native `<button>` and `<input type=submit|button>`,
    `role="button"` widgets, and `<a>` with `href`. Pierces open shadow
    roots and same-origin iframes; cross-boundary selectors are joined
    with ` >>> `. When `session` is a path to a Playwright storage_state
    file, its cookies and origins are restored.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(storage_state=session) if session else browser.new_context()
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                raw = page.evaluate(_EXTRACT_CTAS_JS)
            finally:
                context.close()
        finally:
            browser.close()

    return [_to_cta(item) for item in raw]
