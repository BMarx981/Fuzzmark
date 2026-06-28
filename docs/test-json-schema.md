# Test JSON schema

Per spec [§5.4](fuzzmark-spec.md#54-test-and-data-model), the Test JSON file is
the single source of truth for a test. The app reads and writes it; users can
also edit it directly in any editor and commit it to version control. The
loader in [`engine/src/fuzzmark/driver/flow.py`](../engine/src/fuzzmark/driver/flow.py)
is the only validator — what passes it is what runs.

This document is what that loader accepts, in human-readable form.

## File shape

```json
{
  "name": "feedback-happy-path",
  "flow": [
    { "kind": "visit", "url": "http://localhost:8000/feedback.html" },
    { "kind": "capture", "name": "blank-form" },
    { "kind": "fill", "selector": "#email", "value": "ada@example.com" },
    { "kind": "interact", "selector": "#topic", "action": "select_option", "value": "praise" },
    { "kind": "submit", "selector": "button[type='submit']" },
    { "kind": "capture", "name": "thank-you" }
  ]
}
```

A test is a JSON object. The required top-level keys are `name` and `flow`; the others are optional.

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Non-empty after trimming. Used in run results and reports. |
| `flow` | array | yes | Non-empty list of step objects. |
| `session` | string | no | Path to a Playwright `storage_state` JSON (produced by `fuzzmark session …`). Replayed into the browser context so the flow runs authenticated. Overrides the CLI `--session` flag when set. |

## Flow rules

The loader enforces these whole-flow invariants:

- The **first step must be a `visit`**.
- The flow must contain **at least one `capture` step**.
- **Capture step `name`s must be unique** within a flow — they key screenshots,
  baselines, and report entries.

The runner walks the flow in order, top to bottom. The same flow with different
field values is a different test.

## Step kinds

Every step is a JSON object whose `kind` selects which other fields apply.
Unknown fields are ignored.

### `visit`

Load a URL. Always the first step.

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"visit"` | yes | |
| `url` | string | yes | Any URL the driver can open: `http://`, `https://`, `file://`. |

```json
{ "kind": "visit", "url": "http://localhost:8000/feedback.html" }
```

### `fill`

Type a literal string into an input, textarea, or contenteditable element.

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"fill"` | yes | |
| `selector` | string | yes | A CSS selector. The driver waits for it before filling. |
| `value` | string | yes | Empty string is allowed and means "leave it blank deliberately." |

```json
{ "kind": "fill", "selector": "#email", "value": "ada@example.com" }
```

### `interact`

Click a button, toggle a checkbox, or choose a select option. Use `fill` for
text entry; `interact` is for non-text controls.

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"interact"` | yes | |
| `selector` | string | yes | CSS selector for the target element. |
| `action` | string | yes | One of `click`, `check`, `uncheck`, `select_option`. |
| `value` | string | required when `action` is `select_option` | The option `value` to pick. |

```json
{ "kind": "interact", "selector": "#topic", "action": "select_option", "value": "praise" }
```

### `submit`

Submit the form that contains the named element. Equivalent to clicking the
matched submit button.

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"submit"` | yes | |
| `selector` | string | yes | Usually a submit button; any element inside the form works. |

```json
{ "kind": "submit", "selector": "button[type='submit']" }
```

### `capture`

Take a screenshot and produce one entry in the run result. Capture names key
into the baseline store and the report.

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"capture"` | yes | |
| `name` | string | yes | Unique within the flow. Becomes the screenshot filename and baseline key. |
| `full_page` | boolean | no, default `true` | `false` captures only the visible viewport. |
| `mask_selectors` | array of strings | no | CSS selectors whose bounding boxes are blanked before comparison. Preferred over `mask_regions` — they survive layout shifts. |
| `mask_regions` | array of region objects | no | Fixed pixel rectangles blanked before comparison. See below. |

A mask region object:

| Field | Type | Required | Notes |
|---|---|---|---|
| `x`, `y` | integer | yes | Top-left in pixels, relative to the capture. |
| `width`, `height` | integer | yes | Must both be positive. |
| `source` | string | no, default `"region"` | Free-text label that appears in the report. |

```json
{
  "kind": "capture",
  "name": "thank-you",
  "mask_selectors": [".timestamp"],
  "mask_regions": [
    { "x": 0, "y": 0, "width": 320, "height": 48, "source": "header" }
  ]
}
```

Masks only apply to `capture` steps; setting them on any other kind is a
validation error.

## Worked example

End-to-end, the two tests under
[`examples/contact-form/tests/`](../examples/contact-form/tests/) — one
happy-path flow that fills every field and submits, plus one negative flow that
leaves a required field blank — show the schema in motion against a real form.

## When to edit by hand

The schema is small enough that hand-editing is a first-class workflow:
duplicating a test to vary one field value, renaming captures, adding masks
around a known-dynamic region. The app round-trips the JSON byte-for-byte
through the same loader — anything you write in an editor that the loader
accepts is what the app sees.
