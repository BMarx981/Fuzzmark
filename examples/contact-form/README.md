# Contact-form example

A self-contained walkthrough of the Fuzzmark MVP loop on a tiny feedback form:
**scan → extract → suggest → run → report → approve → re-run**. No network
required.

```
contact-form/
├── site/
│   ├── index.html      Landing page that links to the form
│   └── feedback.html   Form with email / text / tel / number / select / textarea
├── tests/
│   ├── happy-path.json        Fills every field with a valid value and submits
│   └── missing-required.json  Leaves the required topic blank and submits
└── baselines/          Populated by `fuzzmark approve` on the first clean run
```

The form posts back to itself with `action="#sent"` and reveals a thank-you
panel via CSS `:target`, so the post-submit capture is visually distinct
from the filled-form capture without needing a backend.

## Prerequisites

Install and activate the engine once (see the repo [README](../../README.md));
then from this directory:

```bash
cd examples/contact-form
python3 -m http.server 8000 --directory site &   # serves the sample site
```

All commands below assume the server is running on port 8000.

## 1. Look at the site

Open <http://localhost:8000/> in a browser to see the landing page and form.

## 2. Extract the form fields

```bash
fuzzmark extract http://localhost:8000/feedback.html
```

Expect six interactive fields: `email`, `name`, `phone`, `rating`, `topic`,
`message`. The hidden `:target` panel and the submit button are skipped.

## 3. See the per-field suggestions

```bash
fuzzmark suggest http://localhost:8000/feedback.html
```

Each field comes back with a list of rule-generated values keyed off its type
and validation metadata — boundary values for `rating`, format-invalid
payloads for `email`, the option set for `topic`, and so on. This is the
"chips" data the test builder UI will eventually render.

## 4. Run the happy-path test

```bash
fuzzmark run tests/happy-path.json --out runs/happy
```

This writes a screenshot per `capture` step into `runs/happy/` plus a
`result.json` summarizing the flow. Three captures: `blank-form`,
`filled-form`, `thank-you`.

## 5. Render a report

```bash
fuzzmark report runs/happy/result.json --out runs/happy/report
open runs/happy/report/index.html
```

The first time you run this there are no baselines yet, so every capture is
shown without a verdict — just the screenshots and the error panel.

## 6. Approve the first clean run as the baseline

```bash
fuzzmark approve runs/happy/result.json --baselines baselines
```

This copies each capture PNG into `baselines/` keyed by capture name. Commit
the `baselines/` directory alongside the test JSON to version-control the
"approved" look of the form.

## 7. Re-run and compare

```bash
fuzzmark run tests/happy-path.json --out runs/happy-2
fuzzmark report runs/happy-2/result.json --out runs/happy-2/report \
  --baselines baselines
open runs/happy-2/report/index.html
```

Now every capture has a verdict. On an unchanged form they should all read
`pass`. Edit a colour or move the submit button in `site/feedback.html` and
re-run to see a non-pass verdict and a diff heatmap.

## 8. Run the negative test

```bash
fuzzmark run tests/missing-required.json --out runs/missing
fuzzmark report runs/missing/result.json --out runs/missing/report
```

`missing-required` shares the same flow shape but leaves the required `topic`
select blank. Same flow, different values, different test — exactly the model
described in the spec.

## Beyond the MVP loop

```bash
fuzzmark scan http://localhost:8000/ --ignore-robots
```

Crawls the two-page sample site and emits a site map. Phase 2 work; included
here so you can see the scanner output against a known small site.
