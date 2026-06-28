"""Extract interactive form fields from a rendered page using Chromium."""

from __future__ import annotations

from .models import Field, Option, Validation

_EXTRACT_JS = r"""
() => {
  const cssEscape = (s) =>
    (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/([^a-zA-Z0-9_-])/g, '\\$1');

  const labelFor = (el) => {
    if (el.id) {
      const l = document.querySelector('label[for="' + cssEscape(el.id) + '"]');
      if (l && l.textContent.trim()) return l.textContent.trim();
    }
    const anc = el.closest('label');
    if (anc && anc.textContent.trim()) return anc.textContent.trim();
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const ph = el.getAttribute('placeholder');
    if (ph && ph.trim()) return ph.trim();
    return null;
  };

  const selectorFor = (el) => {
    if (el.id) return '#' + cssEscape(el.id);
    const tag = el.tagName.toLowerCase();
    if (el.name) return tag + '[name="' + el.name + '"]';
    const same = Array.from(document.querySelectorAll(tag));
    return tag + ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
  };

  const intAttr = (el, a) =>
    el.hasAttribute(a) ? parseInt(el.getAttribute(a), 10) : null;
  const strAttr = (el, a) => (el.hasAttribute(a) ? el.getAttribute(a) : null);

  const skipInputTypes = ['hidden', 'submit', 'button', 'reset', 'image'];
  const out = [];

  document.querySelectorAll('input, select, textarea').forEach((el) => {
    const tag = el.tagName.toLowerCase();
    let type = null;
    if (tag === 'input') {
      type = (el.getAttribute('type') || 'text').toLowerCase();
      if (skipInputTypes.includes(type)) return;
    }

    const options = [];
    if (tag === 'select') {
      Array.from(el.options).forEach((o) =>
        options.push({ value: o.value, label: o.textContent.trim() })
      );
    }

    out.push({
      selector: selectorFor(el),
      kind: tag,
      type: type,
      name: el.getAttribute('name'),
      id: el.id || null,
      label: labelFor(el),
      validation: {
        required: el.hasAttribute('required'),
        maxlength: intAttr(el, 'maxlength'),
        minlength: intAttr(el, 'minlength'),
        min: strAttr(el, 'min'),
        max: strAttr(el, 'max'),
        step: strAttr(el, 'step'),
        pattern: strAttr(el, 'pattern'),
        accept: strAttr(el, 'accept'),
      },
      options: options,
    });
  });

  return out;
}
"""


def _to_field(raw: dict) -> Field:
    return Field(
        selector=raw["selector"],
        kind=raw["kind"],
        type=raw.get("type"),
        name=raw.get("name"),
        id=raw.get("id"),
        label=raw.get("label"),
        validation=Validation(**raw.get("validation", {})),
        options=[Option(**o) for o in raw.get("options", [])],
    )


def extract_fields(
    url: str,
    timeout_ms: int = 15000,
    headless: bool = True,
    *,
    session: str | None = None,
) -> list[Field]:
    """Load a page and return the interactive form fields found on it.

    When `session` is a path to a Playwright storage_state file, its cookies
    and origins are restored so authenticated pages can be extracted.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(storage_state=session) if session else browser.new_context()
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                raw_fields = page.evaluate(_EXTRACT_JS)
            finally:
                context.close()
        finally:
            browser.close()

    return [_to_field(item) for item in raw_fields]
