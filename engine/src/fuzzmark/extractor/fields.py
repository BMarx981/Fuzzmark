"""Extract interactive form fields from a rendered page using Chromium.

The walker covers native `input/select/textarea`, ARIA-role widgets
(`textbox`, `combobox`, `listbox`, `checkbox`, `switch`, `radio`,
`spinbutton`), `contenteditable` editors, pierces open shadow roots, and
recurses into same-origin iframes. Non-native widgets are mapped onto the
same (kind, type) taxonomy as natives so the suggestion engine works
without changes. Selectors emitted across shadow or iframe boundaries are
joined with ` >>> ` so the driver can later resolve them per hop.

Passing `reveal=N` runs an active discovery pass after the passive walk:
up to `N` clicks of reveal-triggers in document order, re-extracting and
merging any newly-mounted fields. Trigger predicates, in priority order:
`aria-expanded="false"` controls, closed `<details>` summaries,
`aria-haspopup` dialog/menu openers, a narrow allowlist of reveal-verb
buttons ("Add another", "Show more", "More options", …), and wizard
advance buttons ("Next", "Continue", "Step 2", …). Submit buttons are
excluded. Bounded by `N` and idempotent: disclosure-style triggers are
clicked at most once per call (tracked by a stable signature) and
wizard-advance buttons are clicked at most once per iteration (the
signature folds in the iteration index), so two invocations with the
same `reveal=N` yield the same field set on the same page.
"""

from __future__ import annotations

from .models import Field, Option, Validation

_EXTRACT_JS = r"""
() => {
  const cssEscape = (s) =>
    (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/([^a-zA-Z0-9_-])/g, '\\$1');

  const intAttr = (el, a) =>
    el.hasAttribute(a) ? parseInt(el.getAttribute(a), 10) : null;
  const strAttr = (el, a) => (el.hasAttribute(a) ? el.getAttribute(a) : null);
  const boolAria = (el, a) => {
    if (!el.hasAttribute(a)) return false;
    const v = (el.getAttribute(a) || '').toLowerCase();
    return v === '' || v === 'true';
  };

  const resolveId = (root, id) => {
    if (!id) return null;
    if (root.getElementById) return root.getElementById(id);
    return root.querySelector('#' + cssEscape(id));
  };

  const labelFor = (el, root) => {
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const text = lb.split(/\s+/)
        .map((id) => resolveId(root, id))
        .filter(Boolean)
        .map((r) => (r.textContent || '').trim())
        .filter(Boolean)
        .join(' ')
        .trim();
      if (text) return text;
    }
    if (el.id) {
      const l = root.querySelector('label[for="' + cssEscape(el.id) + '"]');
      if (l && l.textContent.trim()) return l.textContent.trim();
    }
    if (el.closest) {
      const anc = el.closest('label');
      if (anc && anc.textContent.trim()) return anc.textContent.trim();
    }
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const ph = el.getAttribute('placeholder');
    if (ph && ph.trim()) return ph.trim();
    return null;
  };

  const localSelectorFor = (el, root) => {
    if (el.id) return '#' + cssEscape(el.id);
    const tag = el.tagName.toLowerCase();
    if (el.name) return tag + '[name="' + el.name + '"]';
    const same = Array.from(root.querySelectorAll(tag));
    return tag + ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
  };

  const emptyValidation = () => ({
    required: false, maxlength: null, minlength: null,
    min: null, max: null, step: null, pattern: null, accept: null,
  });

  const skipInputTypes = ['hidden', 'submit', 'button', 'reset', 'image'];

  const fromNative = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag !== 'input' && tag !== 'select' && tag !== 'textarea') return null;
    let type = null;
    if (tag === 'input') {
      type = (el.getAttribute('type') || 'text').toLowerCase();
      if (skipInputTypes.includes(type)) return null;
    }
    const options = [];
    if (tag === 'select') {
      Array.from(el.options).forEach((o) =>
        options.push({ value: o.value, label: (o.textContent || '').trim() })
      );
    }
    return {
      kind: tag,
      type: type,
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
    };
  };

  const ARIA_KINDS = new Set(['textbox', 'combobox', 'listbox', 'checkbox', 'switch', 'radio', 'spinbutton']);

  const optionsFromListbox = (lb) => {
    if (!lb) return [];
    const out = [];
    lb.querySelectorAll('[role="option"]').forEach((o) => {
      const text = (o.textContent || '').trim();
      const value = o.getAttribute('aria-label') || strAttr(o, 'data-value') || o.id || text;
      out.push({ value: value, label: text || (o.getAttribute('aria-label') || '') });
    });
    return out;
  };

  const fromRole = (el, root) => {
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (!ARIA_KINDS.has(role)) return null;
    // Skip when the native tag already matches the role — fromNative handled it.
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' || tag === 'select' || tag === 'textarea') return null;

    const validation = emptyValidation();
    if (boolAria(el, 'aria-required')) validation.required = true;

    if (role === 'textbox') {
      return {
        kind: boolAria(el, 'aria-multiline') ? 'textarea' : 'input',
        type: boolAria(el, 'aria-multiline') ? null : 'text',
        validation: validation,
        options: [],
      };
    }
    if (role === 'spinbutton') {
      validation.min = strAttr(el, 'aria-valuemin');
      validation.max = strAttr(el, 'aria-valuemax');
      return { kind: 'input', type: 'number', validation: validation, options: [] };
    }
    if (role === 'checkbox' || role === 'switch') {
      return { kind: 'input', type: 'checkbox', validation: validation, options: [] };
    }
    if (role === 'radio') {
      return { kind: 'input', type: 'radio', validation: validation, options: [] };
    }
    if (role === 'listbox') {
      return { kind: 'select', type: null, validation: validation, options: optionsFromListbox(el) };
    }
    if (role === 'combobox') {
      const ctrl = strAttr(el, 'aria-controls') || strAttr(el, 'aria-owns');
      let lb = null;
      if (ctrl) {
        for (const id of ctrl.split(/\s+/)) {
          const found = resolveId(root, id);
          if (found && (found.getAttribute('role') || '').toLowerCase() === 'listbox') {
            lb = found;
            break;
          }
        }
      }
      if (lb) {
        return { kind: 'select', type: null, validation: validation, options: optionsFromListbox(lb) };
      }
      return { kind: 'input', type: 'text', validation: validation, options: [] };
    }
    return null;
  };

  const fromContentEditable = (el) => {
    if (!el.hasAttribute('contenteditable')) return null;
    const raw = (el.getAttribute('contenteditable') || '').toLowerCase();
    if (raw === 'false') return null;
    if (raw !== '' && raw !== 'true' && raw !== 'plaintext-only') return null;
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea') return null;
    const validation = emptyValidation();
    if (boolAria(el, 'aria-required')) validation.required = true;
    return { kind: 'textarea', type: null, validation: validation, options: [] };
  };

  const out = [];

  const walk = (root, pathPrefix) => {
    if (!root) return;
    const all = root.querySelectorAll('*');
    all.forEach((el) => {
      let info = fromNative(el);
      if (!info) info = fromRole(el, root);
      if (!info) info = fromContentEditable(el);
      if (info) {
        out.push({
          selector: pathPrefix + localSelectorFor(el, root),
          kind: info.kind,
          type: info.type,
          name: el.getAttribute('name'),
          id: el.id || null,
          label: labelFor(el, root),
          validation: info.validation,
          options: info.options,
        });
      }
      if (el.shadowRoot) {
        const hostSel = pathPrefix + localSelectorFor(el, root);
        walk(el.shadowRoot, hostSel + ' >>> ');
      }
      if (el.tagName === 'IFRAME') {
        let doc = null;
        try { doc = el.contentDocument; } catch (_) { doc = null; }
        if (doc) {
          const iframeSel = pathPrefix + localSelectorFor(el, root);
          walk(doc, iframeSel + ' >>> ');
        }
      }
    });
  };

  walk(document, '');
  return out;
}
"""


_REVEAL_CLICK_NEXT_JS = r"""
({clicked, iter}) => {
  const seen = new Set(clicked || []);
  const trim = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 64);

  // Conservative reveal-verb patterns. Anchored at start of the trimmed
  // textContent so unrelated CTAs ("Add to cart", "Show details") don't
  // match. Keep this list narrow on purpose — false positives here would
  // fire arbitrary buttons during a scan.
  const TEXT_REVEAL_RE = /^(add (another|more|new|item|field|row|step|line)|show (more|all|fields|optional)|more (options|fields|details)|see more|reveal more)\b/i;

  // Wizard advance buttons. Same button text typically persists across
  // steps, so the signature folds in the iteration index — letting one
  // "Next" element fire once per pass while the reveal budget allows.
  const ADVANCE_RE = /^(next|continue|step \d+|go to step \d+)\b/i;

  const isSubmit = (el) => {
    const t = (el.getAttribute('type') || '').toLowerCase();
    if (el.tagName === 'BUTTON') return t === 'submit';
    if (el.tagName === 'INPUT') return t === 'submit';
    return false;
  };

  const cands = [];

  // 1. aria-expanded="false" controls — the highest-signal disclosure trigger.
  document.querySelectorAll('[aria-expanded="false"]').forEach((el) => {
    cands.push({
      el: el,
      sig: 'exp|' + (el.id || '') + '|' + (el.getAttribute('aria-controls') || '') + '|' + trim(el.textContent),
    });
  });

  // 2. Closed <details>.
  document.querySelectorAll('details:not([open]) > summary').forEach((el) => {
    cands.push({ el: el, sig: 'sum|' + trim(el.textContent) });
  });

  // 3. Dialog openers — buttons advertising aria-haspopup, minus any
  // already matched by the aria-expanded pass above.
  document.querySelectorAll('[aria-haspopup]').forEach((el) => {
    const v = (el.getAttribute('aria-haspopup') || '').toLowerCase();
    if (v !== 'dialog' && v !== 'true' && v !== 'menu') return;
    if (el.hasAttribute('aria-expanded')) return;
    cands.push({
      el: el,
      sig: 'dlg|' + (el.id || '') + '|' + (el.getAttribute('aria-controls') || '') + '|' + trim(el.textContent),
    });
  });

  // 4. Text-pattern triggers — narrow allowlist; skips submits and anything
  // already covered by aria-expanded. Wizard-advance buttons get an
  // iter-aware signature so a stable "Next" can fire on each iteration.
  document.querySelectorAll('button, [role="button"]').forEach((el) => {
    if (isSubmit(el)) return;
    if (el.hasAttribute('aria-expanded')) return;
    if (el.hasAttribute('aria-haspopup')) return;
    if (el.disabled) return;
    if ((el.getAttribute('aria-disabled') || '').toLowerCase() === 'true') return;
    const txt = trim(el.textContent);
    if (ADVANCE_RE.test(txt)) {
      cands.push({ el: el, sig: 'adv|' + (el.id || '') + '|' + txt + '|' + iter });
    } else if (TEXT_REVEAL_RE.test(txt)) {
      cands.push({ el: el, sig: 'txt|' + (el.id || '') + '|' + txt });
    }
  });

  for (const c of cands) {
    if (seen.has(c.sig)) continue;
    try { c.el.click(); } catch (_) { continue; }
    return c.sig;
  }
  return null;
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
    reveal: int = 0,
) -> list[Field]:
    """Load a page and return the interactive form fields found on it.

    Covers native form controls, ARIA-role widgets, contenteditable
    editors, open shadow roots, and same-origin iframes. When `session`
    is a path to a Playwright storage_state file, its cookies and
    origins are restored so authenticated pages can be extracted.

    `reveal` opts into an active discovery pass: after the passive walk,
    up to `reveal` reveal-triggers are clicked in document order and the
    page is re-extracted, merging any new fields by selector. Trigger
    predicates, in priority order: `aria-expanded="false"` controls,
    closed `<details>` summaries, `aria-haspopup` dialog/menu openers,
    a narrow allowlist of reveal-verb buttons ("Add another", "Show
    more", "More options", …), and wizard advance buttons ("Next",
    "Continue", "Step 2", …). Submit buttons are excluded. Disclosure
    triggers are clicked at most once per call; wizard-advance buttons
    fire at most once per iteration, so a 3-step wizard walks with
    `reveal=2`. The pass remains bounded and idempotent.
    """
    from playwright.sync_api import sync_playwright

    if reveal < 0:
        raise ValueError("reveal must be >= 0")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(storage_state=session) if session else browser.new_context()
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                raw_fields = page.evaluate(_EXTRACT_JS)
                if reveal > 0:
                    clicked: list[str] = []
                    for i in range(reveal):
                        sig = page.evaluate(
                            _REVEAL_CLICK_NEXT_JS,
                            {"clicked": clicked, "iter": i},
                        )
                        if not sig:
                            break
                        clicked.append(sig)
                        page.wait_for_timeout(200)
                        seen = {f["selector"] for f in raw_fields}
                        for f in page.evaluate(_EXTRACT_JS):
                            if f["selector"] not in seen:
                                raw_fields.append(f)
                                seen.add(f["selector"])
            finally:
                context.close()
        finally:
            browser.close()

    return [_to_field(item) for item in raw_fields]
