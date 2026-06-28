# Fuzzmark — Product Specification

**Name:** Fuzzmark
**Document status:** Draft v1
**Owner:** Brian / Hawkstreak Studio

---

## 1. Summary

The app is a self-hosted desktop tool that lets anyone point at a website — a local development site or a live URL — automatically discover its pages and forms, and run repeatable tests that combine **form-input fuzzing** with **visual-regression checking**. It captures each screen as it interacts with the site, compares those screens against an approved baseline, and surfaces both visual changes and runtime errors in a reviewable report.

Its distinguishing idea is **scan-first authoring**: instead of requiring the user to write tests before they know what to check, the app crawls the target, extracts every form field, and presents rule-based QA suggestions ("fuzzing chips") beside each field. The user assembles tests by accepting, editing, or ignoring those suggestions. This takes a user from a bare URL to a running test suite without writing a line of test code.

All comparison and suggestion logic is **deterministic and rule-based**. There is no AI agent operating inside the app or inside the site under test.

---

## 2. Positioning and target user

**Primary user:** small teams, solo developers, and digital agencies that ship content-managed sites (Drupal, WordPress, and similar) and have no dedicated QA engineer. These users feel two pains acutely: they don't have time to author test suites from scratch, and CMS theme or content changes silently break layouts at specific breakpoints.

**The wedge:** competing tools (Playwright, Cypress, Applitools, Percy, mabl, BrowserStack) are strong at *running* or *diffing* tests but nearly all assume the user has already authored the tests. The app inverts that: discovery and suggestion come first. That is the feature users will remember and the reason to choose it.

**Explicit non-goal of the positioning:** the app does not try to out-feature the incumbents on scale, cloud orchestration, or CI integration in early versions. It wins on time-to-first-test for people who currently have zero tests.

---

## 3. Core concepts and glossary

| Term | Meaning |
|---|---|
| **Target** | A website under test, identified by a base URL. Either a local dev site or a live site. |
| **Project** | A saved configuration for one target: its base URL, scan results, tests, masks, and baselines. |
| **Scan** | The crawl-and-extract pass that discovers pages and the form fields on them. |
| **Page** | A single discovered URL within a target. |
| **Field** | An interactive form control on a page (`input`, `select`, `textarea`) with its extracted metadata. |
| **Suggestion** | A rule-generated candidate test value for a field (e.g. an over-length string, an injection payload). Shown as a chip. |
| **Test** | A named flow plus, for each field involved, a chosen value or a deliberate empty. |
| **Flow** | The ordered sequence of steps a test performs (visit page, fill fields, submit, capture). |
| **Run** | One execution of a test or set of tests, producing captures and a verdict per step. |
| **Baseline** | The approved reference screenshot for a given step, viewport, and target state. |
| **Verdict** | The classification of a captured screen against its baseline (pass, size-shift, content-change, layout-break, error). |
| **Mask** | A region or DOM selector excluded from comparison to ignore legitimately dynamic content. |
| **Report** | The reviewable output of a run: captures, diffs, verdicts, and collected errors. |

---

## 4. System architecture

Two cooperating processes on the user's machine, no cloud dependency:

**Engine (local service).** Owns crawling, field extraction, suggestion generation, browser driving, screen capture, error collection, image comparison, and the baseline store. This is where the computer-vision work lives. Runs as a local process exposing a local HTTP/WebSocket API.

**Frontend (desktop app).** The user-facing application: project management, the scan view, the test builder with the suggestion panel, run controls, and the diff review interface. Communicates with the engine over the local API only.

**Site under test.** Driven externally through a real browser (web) or device simulator (mobile, later phase). The app never injects an agent, SDK, or instrumentation into the site. Authentication, when needed, is handled by replaying a saved browser session captured once by the user.

This split keeps the heavy automation and CV in the runtime best suited to them while keeping the interface in a single cross-platform desktop codebase.

---

## 5. Functional specification

### 5.1 Scanner

- Accepts a base URL (local or live) plus crawl bounds.
- Honors `robots.txt` and a user-configurable rate limit.
- Produces a **site map**: the set of reachable pages with their titles and link graph.
- Returns control to the user for selection; the user chooses which discovered pages enter the project. The scanner never auto-tests everything it finds.

**Default crawl bounds.** The primary risk crawling content-managed sites is not volume but *crawler traps*: faceted search and filters produce near-infinite URL permutations, calendars expose endless navigation links, and pagination can run unbounded. Defaults are therefore conservative, trap-aware, and never destructive:

| Bound | Default | Notes |
|---|---|---|
| Max depth | 3 | Link-hops from the start URL; covers most small-site templates. |
| Max pages | 50 | Soft cap, user-raisable; guarantees a fast first scan. |
| Scope | same-origin only | No wandering to external domains. |
| `robots.txt` | respected | One-click override for local dev. |
| URL de-duplication | on | Normalize URLs (strip fragments and tracking params, collapse query-string variants); key on normalized path so one template is not captured many times. |
| Exclude list | starter set shipped | Logout/session-destroying links, admin destructive actions (delete/edit/clone), faceted-filter query params, pagination beyond a small N. |
| Rate limit | modest for live, relaxed for local | Avoids hammering production. |

The principle: a first scan is fast, safe, and non-destructive by default; the user raises limits deliberately.

### 5.2 Field extractor

For each selected page, parse the rendered DOM and emit, per interactive control:

- Control kind (`input`, `select`, `textarea`) and `type` attribute.
- `name` / `id` and the associated `<label>` text.
- Validation metadata: `required`, `maxlength`, `minlength`, `min`, `max`, `step`, `pattern`, `accept`.
- For `select`: the option set.
- A stable selector for later driving, preferring accessibility-friendly anchors over brittle positional ones.

The extractor output is the input to the suggestion engine and the raw material the user composes tests from.

### 5.3 Suggestion engine (differentiator)

Pure rule-based generation, keyed off field type and validation metadata. No model. The engine encodes standard QA practice — boundary-value analysis, equivalence partitioning, injection and internationalization probes — as lookup tables. Each suggestion carries a **category** so the UI can group and color them.

Suggestion categories:

| Category | Purpose | Representative values |
|---|---|---|
| **Empty / required** | Probe required-field handling | blank, whitespace-only |
| **Boundary** | Test length and numeric limits | one under `maxlength`, exactly at, one over; `min`-1, `min`, `max`, `max`+1 |
| **Format-invalid** | Test format validation | malformed email, letters in numeric field, impossible date |
| **Format-valid** | Confirm the happy path | a well-formed value matching `type`/`pattern` |
| **Security** | Probe injection handling | script-tag payload, SQL-style payload, `javascript:` URL |
| **Internationalization** | Probe encoding and direction | emoji, RTL text, CJK characters, accented Latin |
| **Type-specific** | Domain quirks per field type | leading-zero numbers, plus-addressed email, international phone formats |

Type-to-suggestion mapping is table-driven and extensible: adding support for a new field type means adding a table row, not new logic. The **curated built-in tables are the product's selling point and ship in the MVP** — a strong, opinionated default set out of the box. User-authored custom tables are a later phase, not a v1 requirement.

**Input model.** Manual entry is the baseline behavior, not a fallback. Every field accepts a free-typed value from the user at any point, whether or not any suggestion is involved. Suggestions are optional shortcuts layered on top of that:

- A field always presents an editable value input.
- Suggestions appear alongside as chips; selecting one is a one-click way to *populate* the field's value.
- A selected suggestion is never locked. Once applied it becomes an ordinary editable value the user can modify, replace, or clear — selecting a chip and then editing the result is a normal, expected path.
- The user can ignore suggestions entirely and type their own value, or mark the field deliberately empty.

The chip is a convenience for getting a good value into the field fast; the field's value is always the user's to edit.

### 5.4 Test and data model

A **test** is a named flow. A **flow** is an ordered list of steps. Step kinds:

- **Visit** a page.
- **Fill** a field with a chosen value (or explicit empty).
- **Interact** (click a button, toggle, select an option).
- **Submit** a form.
- **Capture** the current screen.

The same flow with different field values is a different test. This is the core of how the user expresses "each test has these fields filled or left empty." Tests are saved per project and re-runnable.

**Storage format.** Tests are stored as **JSON** — one human-readable, hand-editable file per test (or per suite). The format is the single source of truth: a user can edit a test in place in the app, edit the JSON directly in an editor, commit it to version control, or run it through the app, and all paths operate on the same file. The schema is stable and documented so direct editing is safe — see [`test-json-schema.md`](test-json-schema.md) for the field-by-field reference.

### 5.5 Driver

- **Web:** a headless-capable real browser engine drives any URL regardless of backend framework, because it operates on rendered output, not source. Auto-waits for network and DOM stability before capture.
- **Mobile (later phase):** device simulator driving via OS-level screenshot and input tooling, no app instrumentation.

### 5.6 Capture

- Full-page or element screenshots at each capture step.
- Collection of console output, uncaught exceptions, and failed network requests during the run.
- Detection of framework error states (e.g. server error pages, CMS error screens) as a distinct signal feeding the **error** verdict.

### 5.7 Comparison engine

A tiered pipeline, cheapest checks first, producing a verdict and a visual heatmap per captured step:

1. **Normalize** — resize to baseline dimensions and normalize color so DPI/scale differences do not register as changes.
2. **Align** — feature-match to find a global transform. If a small translation or scale explains most of the difference, classify as **size-shift** rather than a content regression.
3. **Perceptual diff** — anti-aliasing-aware pixel diff plus a structural-similarity score; catches color and content changes as **content-change**.
4. **Structural diff** — detect element bounding boxes and compare layout structure; distinguishes a broken layout (**layout-break**) from a mere text change.
5. **Masks** — exclude user-defined dynamic regions, by DOM selector (preferred, survives layout shifts) or by region, before scoring.

Verdicts: `pass`, `size-shift`, `content-change`, `layout-break`, `error`. Thresholds are tunable per project.

### 5.8 Baseline store

- Baselines stored as image files keyed by **flow + step + state + viewport**.
- Stored in a version-controllable directory layout so baselines live alongside the project in source control.
- Approving an intentional change writes a new baseline; the diff against the previous one is preserved in history by the user's VCS.

### 5.9 Reporting and review

- Per-step result with side-by-side baseline/capture, an overlay slider, and a difference heatmap.
- A panel listing collected console errors, exceptions, failed requests, and detected error states.
- Per-step approve action that promotes a capture to the new baseline.
- Run summary: counts by verdict, with fast navigation to failures first.

---

## 6. User workflow

1. **Create a project** by entering a target base URL (local or live).
2. **Scan** — the app crawls within bounds and shows the discovered site map.
3. **Select pages** to bring into the project.
4. **Build tests** — for each page, the extracted fields appear with suggestion chips alongside. The user assembles flows: visit, fill (accept a suggestion / edit / type / leave empty), interact, submit, capture.
5. **Define masks** for known dynamic regions.
6. **Run** the test or suite.
7. **Review** the report: diffs, verdicts, errors. Approve intended changes to update baselines; investigate regressions.
8. **Re-run** later against a new build to catch what moved.

---

## 7. UI / UX design

### 7.1 Principles

- **Clean, calm, and legible.** A QA tool is read closely under pressure; clarity beats decoration. Generous whitespace, a restrained palette, strong typographic hierarchy.
- **The field-suggestion panel is the signature surface.** It should feel immediate and a little delightful — chips that invite clicking, clearly color-coded by category, with the dangerous ones (security, boundary) visually distinct from the safe ones.
- **Diff review is the second signature surface.** Comparison must be effortless to read: slider and side-by-side modes, a heatmap toggle, and failures surfaced first.
- **Progressive disclosure.** A first-time user sees URL → Scan → suggestions without configuration. Advanced controls (crawl bounds, thresholds, masks) are present but tucked away until wanted.

### 7.2 Primary screens

1. **Projects / home.** List of saved projects with last-run status at a glance. Prominent "New project" entry taking just a URL.
2. **Scan view.** Progress while crawling, then the discovered site map as a selectable list or graph. Crawl-bound controls available but collapsed by default.
3. **Test builder.** A two-region layout: the flow being assembled on one side; the current page's extracted fields on the other. Each field shows an editable value input as its primary control, with suggestion chips alongside. The user can type directly into any field at any time. Selecting a chip populates that field's input with the suggestion's value, which then remains fully editable in place — chips are a fast way to fill the input, never a replacement for it.
4. **Run view.** Live progress of the executing flow with the screen being captured visible as it goes.
5. **Report / review.** Per-step results, verdict-first ordering, the side-by-side / slider / heatmap diff viewer, and the error panel. Approve-baseline actions inline.

### 7.3 Visual direction

- Neutral base surface with a single confident accent color for primary actions.
- A small, consistent verdict color language reused everywhere: pass, size-shift, content-change, layout-break, error each get one fixed hue and icon, so a user learns the vocabulary once.
- Suggestion categories get their own consistent secondary palette, distinct from the verdict palette to avoid confusion.
- Typography: one clear UI typeface; a monospaced face for field values, selectors, and payloads so test data reads unambiguously.
- Dark and light themes from the outset, since QA work happens in long sessions.

---

## 8. Technology stack and rationale

**Engine: Python.** Strongest single-runtime pairing of browser automation and computer vision. Browser driving, simulator driving, and the image-analysis libraries all have first-class support, and the CV tooling materially exceeds the alternatives. This is where comparison quality is won.

**Frontend: Flutter desktop.** One cross-platform native codebase (macOS first, with Windows/Linux reachable), in the owner's strongest stack. Talks to the engine over the local API. Delivers the "anyone can download and run it" goal as a clean local desktop app.

**Communication:** local HTTP/WebSocket between frontend and engine.

**Rejected alternative:** an all-TypeScript/Electron single binary. Easier to package, but weaker computer-vision libraries and less-documented simulator driving. For a tool whose entire value is comparison quality and field intelligence, that trade is wrong.

---

## 9. Data model sketch

```
Project
  id, name, base_url, created_at
  scan: { pages[], crawl_bounds }
  viewports[]
  masks[]            (per page or global; selector or region)
  tests[]
  baselines/         (directory, VCS-tracked)

Page
  url, title, fields[]

Field
  selector, kind, type, name, label
  validation: { required, maxlength, minlength, min, max, step, pattern, accept }
  options[]          (for select)

Suggestion
  field_ref, category, value, label

Test
  id, name, flow[]

FlowStep
  kind             (visit | fill | interact | submit | capture)
  page_ref, field_ref, value, interaction

Run
  id, test_ref, started_at
  results[]        (per capture step)

Result
  step_ref, viewport, verdict, capture_path, baseline_path, diff_path
  errors[]
```

---

## 10. MVP scope and non-goals

### 10.1 In scope for MVP

The smallest build that proves the wedge is real:

1. One target URL, **single page** (no crawl yet).
2. Scan that page and extract its form fields.
3. Suggestion engine for the **common field types** (text, email, number, tel, select).
4. Fill, submit, capture, and collect console errors.
5. Basic visual diff and a reviewable report.

The MVP succeeds if pointing it at a real form and seeing per-field suggestions appear feels obviously useful. If it does, the rest layers onto a proven core. If it doesn't, that is learned in weeks rather than months.

### 10.2 Definition of done — MVP diff quality

Measured against a small fixture set: a few known-stable pages plus a few with deliberately injected changes (a moved button, a broken breakpoint, a color change, a text change, an added element). Two gates:

- **No false positives:** 20 consecutive captures of the same unchanged page all return `pass`. This flakiness gate is the one that sinks these tools in practice.
- **Catches the obvious:** every injected regression returns a non-`pass` verdict — 100% catch on deliberate breakage.

The MVP bar is **catch, not classify**. Correctly distinguishing size-shift from layout-break is Phase 3 work; the MVP only has to reliably notice a change and reliably stay quiet on identical input, using a single tunable threshold. If no single threshold separates the stable set from the changed set, that is the signal that the alignment and structural passes are needed — i.e. the trigger to begin Phase 3.

### 10.3 Explicit non-goals for MVP

- Full-site crawling (single page only at first).
- Authenticated / logged-in testing.
- Multi-viewport matrix.
- Dynamic-content masking.
- Mobile / simulator support.
- The polished Flutter UI (a minimal interface or generated report suffices to validate the core).
- Accounts, cloud, multi-tenant, or CI integration of any kind.

---

## 11. Phase ladder

1. **MVP** — single-page scan, the curated suggestion tables for common types, fill/submit/capture, basic diff, report.
2. **Crawl** — multi-page discovery, site map, page selection.
3. **Robustness** — alignment + structural diff + masks; the smart verdict classification.
4. **Breadth** — multi-viewport matrix; full suggestion-category coverage; user-extensible suggestion tables; authenticated sessions.
5. **Frontend** — the polished Flutter desktop app: projects, scan view, test builder with the suggestion panel, run view, diff review.
6. **Component coverage** — widen passive extraction beyond native `input/select/textarea`: ARIA-role widgets (`combobox`, `listbox`, `textbox`, `switch`, `checkbox`, `radio`, `spinbutton`), `contenteditable` editors, shadow-DOM piercing, and same-origin iframe recursion. Closes the gap for component-library and web-component sites (Radix, Headless UI, MUI, Stencil, Lit).
7. **Interaction discovery** — active extraction pass that clicks reveal-triggers (elements toggling `aria-expanded`, dialog openers, "Add another" buttons, multi-step wizards) and re-extracts, plus first-class CTA/button modeling for click-driven flows. Bounded and idempotent so a scan stays deterministic.
8. **Mobile** — simulator-driven capture and comparison for native apps.

---

## 12. Open questions

- Visual identity: logo, palette, and type, building on the name Fuzzmark.
- Whether the per-test JSON splits into separate files per test or groups into per-suite files, and the exact on-disk directory layout alongside baselines.
- How much of crawl bounds / thresholds to expose by default versus hide behind advanced settings.
- The exact contents of the shipped suggestion tables and the starter crawl exclude list, to be finalized during MVP build.

### Resolved

- **Name:** Fuzzmark. Clear on PyPI and npm; domain and trademark checked.
- **Test format:** JSON, one source of truth, editable in place in the app or directly in an editor, version-controllable, runnable through the app.
- **Suggestion tables:** curated built-in set ships in the MVP; user-extensibility deferred to Phase 4.
- **Crawl bounds:** conservative trap-aware defaults (depth 3, 50-page soft cap, same-origin, robots respected, URL de-dup on, starter exclude list); see §5.1.
- **MVP diff definition of done:** zero false positives on repeated identical captures and 100% catch on a deliberate-breakage fixture set, single tunable threshold, catch-not-classify; see §10.2.
