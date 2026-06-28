# Project JSON schema

Per spec [§9](fuzzmark-spec.md#9-data-model-sketch), a Fuzzmark **project**
bundles the bits the CLI otherwise threads through as loose flags: a base URL,
a viewport list, paths to a saved session / custom suggestion tables / a
cached scan, the baselines directory, and the list of tests that belong to
the project. The loader in
[`engine/src/fuzzmark/project/load.py`](../engine/src/fuzzmark/project/load.py)
is the only validator — what passes it is what the rest of the engine sees.

A project file is a single JSON object stored next to its tests and
baselines. All path fields are interpreted relative to the directory
containing the project file, so the whole bundle is portable: copy the
folder, the project still works.

## File shape

```json
{
  "name": "contact-form",
  "base_url": "http://localhost:8000/",
  "viewports": [
    { "name": "desktop", "width": 1280, "height": 800 },
    { "name": "mobile", "width": 375, "height": 667 }
  ],
  "session": "auth.json",
  "tables": "tables.json",
  "scan": "scan.json",
  "baselines": "baselines",
  "tests": [
    "tests/happy.json",
    "tests/negative.json"
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Non-empty after trimming. |
| `base_url` | string | yes | Non-empty after trimming. Supplies the URL when a command's positional URL is omitted. |
| `viewports` | array | no | Non-empty list of `{name, width, height}`. Names must be unique within the project. The first entry is the default viewport for `capture` and `run`. |
| `session` | string | no | Path to a Playwright `storage_state` JSON (produced by `fuzzmark session …`). |
| `tables` | string | no | Path to a custom suggestion-tables JSON (see [`engine/src/fuzzmark/suggestions/custom.py`](../engine/src/fuzzmark/suggestions/custom.py)). |
| `scan` | string | no | Path to a cached site map produced by `fuzzmark scan`. |
| `baselines` | string | no | Directory of approved baseline PNGs keyed by capture name. |
| `tests` | array | no | List of paths to Test JSON files belonging to the project; entries must be unique. |

All path fields may be relative (resolved against the project file's
directory) or absolute. Unknown top-level fields are ignored.

## CLI integration

Every operating command accepts `--project <path>`, which loads the file and
uses it as a defaults provider. Explicit flags still win.

| Command | What `--project` provides |
|---|---|
| `scan` | `url` ← `base_url`; `--session` ← `session` |
| `extract` | `url` ← `base_url`; `--scan` ← `scan`; `--session` ← `session` |
| `suggest` | `url` ← `base_url`; `--scan` ← `scan`; `--tables` ← `tables`; `--session` ← `session` |
| `capture` | `--width`/`--height` ← first viewport; `--session` ← `session` |
| `run` | `--width`/`--height` ← first viewport; `--session` ← `session` (Test JSON `session` still wins) |
| `report` | `--baselines` ← `baselines` |
| `approve` | `--baselines` ← `baselines` |

## Lifecycle

- `fuzzmark project init <path> --name N --base-url URL [--viewport NAME:WxH ...]`
  writes a starter file. Refuses to overwrite an existing file unless `--force`
  is passed.
- `fuzzmark project show <path>` loads the file and prints it with absolute
  resolved paths beside the original verbatim fields. Useful for verifying
  that relative paths point where you expect.
- After init, hand-edit the file to add `tests`, `baselines`, `session`,
  `tables`, or `scan` — the schema is small enough that direct editing is a
  first-class workflow, just like the [Test JSON](test-json-schema.md).

## When to edit by hand

The same principle as the Test JSON: the schema is small and stable, the
loader is the only validator, and the app and an editor see the same bytes.
Adding a viewport, a new test path, or wiring up a captured session is a
one-line edit.
