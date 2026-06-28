# Fuzzmark

A scan-first QA tool: point it at any local or live site, let it discover the
pages and form fields, get rule-based fuzzing suggestions per field, then run
repeatable tests that combine form-input fuzzing with visual-regression
checking. No agent runs inside the site under test.

See [`docs/fuzzmark-spec.md`](docs/fuzzmark-spec.md) for the full specification.

## Structure

```
fuzzmark/
├── docs/        Specification and design docs
├── engine/      Python engine (the MVP lives here)
├── app/         Flutter desktop frontend (added at Phase 5)
└── examples/    Sample projects and configs
```

The Python engine and the Flutter app are separate processes that talk over a
local API. Build order follows the phase ladder in the spec: the engine first,
the frontend later.

## Engine quickstart

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

Extract the form fields from any page:

```bash
fuzzmark extract https://example.com/contact
```

This prints a JSON description of every interactive field on the page — the raw
material the suggestion engine and test builder work from. Run with `--headed`
to watch the browser.

## Status

MVP, first module: the field extractor is runnable. Next up per the spec are the
suggestion tables, then capture and diff.
