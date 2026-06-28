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
├── engine/      Python engine
├── examples/    Sample projects and configs
└── app/         Flutter desktop frontend (added at Phase 5)
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

The CLI installs as `fuzzmark`. Every subcommand is non-interactive — flags and
arguments only, no prompts.

| Command | What it does |
|---|---|
| `extract <url>` | Parse a page's interactive form fields and print them as JSON. |
| `suggest <url>` | Same as `extract` but also emits per-field rule-based suggestion chips. |
| `scan <url>` | Same-origin BFS crawl within bounds; emits a site map. |
| `capture <url> <out.png>` | One-shot screenshot plus error-signal JSON. |
| `run <test.json> --out DIR` | Drive a Test JSON flow; writes per-capture PNGs and prints the run result to stdout. |
| `report <result.json> --out DIR` | Render a static HTML report against optional approved baselines. |
| `approve <result.json> --baselines DIR` | Promote captures from a run into the baseline store. |
| `compare <baseline> <candidate>` | Standalone SSIM diff between two PNGs; exits non-zero on change. |

Run any subcommand with `--help` for its flags. `extract`, `suggest`, `scan`,
`capture`, and `run` accept `--headed` to watch the browser.

### Smoke test

```bash
cd engine
fuzzmark extract "file://$(pwd)/fixtures/form.html"
```

Expect six fields (`email`, `fullname`, `zip`, `age`, `state`, `message`); the
hidden input and submit button are skipped.

### End-to-end walkthrough

[`examples/contact-form/`](examples/contact-form/) runs the full MVP loop —
extract, suggest, run, report, approve, re-run — against a self-contained
sample site, no network required. Start there to see how the pieces fit.

## Status

MVP modules — extractor, suggestions, driver, capture, compare, baselines, and
report — are runnable end-to-end via the CLI. Phase 2 (multi-page crawl with
`scan` and the baselines/approve loop) has landed; the polished Flutter app
arrives at Phase 5 per the spec's phase ladder.
