# Fuzzmark — CLAUDE.md

Operating guide for working in this repo. This file is *how* to work here; for
*what* Fuzzmark is and *why*, see [`docs/fuzzmark-spec.md`](docs/fuzzmark-spec.md)
(product scope, decisions, and the phase ladder). Don't restate the spec here.

## Project

Fuzzmark is a scan-first QA tool: it discovers a site's pages and form fields,
generates rule-based fuzzing suggestions per field, and runs tests that combine
form-input fuzzing with visual-regression checking. No agent runs inside the
site under test.

## Layout

- `engine/` — Python engine. All current work happens here.
- `engine/src/fuzzmark/` — the package; one subfolder per spec module.
- `app/` — Flutter desktop frontend. Phase 5. Do not scaffold it yet.
- `docs/` — specification.
- `examples/` — sample projects and configs.

## Environment

```
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## Run and verify

- Smoke test: `fuzzmark extract "file://$(pwd)/fixtures/form.html"` — expect 6
  fields (`email`, `fullname`, `zip`, `age`, `state`, `message`); the hidden
  input and submit button are skipped.
- Tests: run `pytest` from `engine/`.
- Run the smoke test after any change to `extractor` or `cli`.

## Conventions

- Package name is `fuzzmark`; use relative imports within the package.
- Scripts and the CLI are non-interactive: they take arguments and flags and
  never call `input()` or otherwise block on stdin. An interactive prompt would
  hang an automated session. Keep it that way.
- No suggestion or TODO comments in code.
- The module folders `scanner`, `suggestions`, `driver`, `capture`, `compare`,
  `baselines`, and `report` are documented placeholders. Implement them in the
  spec's build order; do not jump ahead of the current phase.
- Keep logic modules importable without a browser. Only `extractor`, `driver`,
  and `capture` should depend on the browser; `suggestions`, `compare`,
  `baselines`, and `report` should not.

## Scope guardrails — current phase: MVP

- In scope: single page. Order: extractor (done) → suggestions → capture →
  diff → report.
- Out of scope until later phases: crawling, auth/sessions, viewport matrix,
  dynamic-content masks, mobile/simulator, and the Flutter UI.
- Diff definition of done: zero false positives across 20 identical captures of
  an unchanged page, and 100% catch on the breakage fixtures. Catch, not
  classify — verdict labeling is a later phase.

## Permissions

Non-destructive commands (inspection, Python and tests, the `fuzzmark` CLI,
read-only and staging git, in-repo file reads and edits) auto-run via
`.claude/settings.json`. History-writing git (commit, push, checkout, rebase)
and `rm` prompt first. Destructive or external-effect commands (`rm -rf`,
`git reset --hard`, `git clean`, `sudo`, network fetch) are denied. Personal
overrides belong in `.claude/settings.local.json`, which is gitignored.
