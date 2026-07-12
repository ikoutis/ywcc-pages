# NJIT Catalog Ontology & Quality Dashboard

A structured **ontology** of the NJIT undergraduate catalog — every program and course,
with prerequisite **dependencies** — plus a **rubric + AI-assisted quality evaluation** and a
browsable **dashboard** with actionable improvement suggestions.

Source data: **`2024-2025 Undergraduate.pdf`** (at the repo root) — the official catalog,
all disciplines. Everything here is generated from it.

Live view (once deployed): `njit-jc.cc/catalog/site/`.

```
catalog/
  schema/
    ontology.schema.json   JSON Schema the ontology is validated against
    rubric.md              the quality rubric (dimensions, scales, evidence)
  pipeline/                the re-runnable extraction/parsing/scoring pipeline
    extract.py             PDF -> per-page text cache (data/pages.json)
    parse_courses.py       course-description blocks -> course records
    parse_programs.py      TOC hierarchy + plan-of-study -> program records
    prereq_parser.py       prerequisite string -> boolean AST + dependency edges
    metrics.py             deterministic quality signals + graph metrics
    build_ontology.py      assemble + schema-validate -> data/ontology.json
    build_eval_inputs.py   per-program packets for the AI rubric pass
    evaluate.py            merge AI evaluations -> data/evaluations.json
    requirements.txt       pdfplumber, jsonschema
  data/
    ontology.json          the ontology (all disciplines)      [committed]
    metrics.json           deterministic metrics               [committed]
    evaluations.json       AI rubric evaluations (pilot)        [committed]
    evals/<program>.json   per-program AI evaluation source     [committed]
    pages.json             page-text cache (gitignored, regenerable)
    eval_inputs.json       eval packets (gitignored, regenerable)
  site/                    self-contained static dashboard (HTML/CSS/vanilla JS)
```

## Data model (`data/ontology.json`)

- **colleges / departments / subjects** — the academic hierarchy (from the TOC).
- **programs** — `{name, degree, kind, collegeId, departmentId, statedTotalCredits,
  requirementGroups[] (plan of study), courseCodes[]}`.
- **courses** — `{code, subject, number, title, credits, contactHours, description,
  prerequisiteRaw, prerequisiteAst, corequisites[]}`.
- **prerequisiteEdges** — directed `from → to` edges (course → its prerequisite), with
  `minGrade` and `kind` (prerequisite | corequisite). This is the dependency graph.

The prerequisite parser turns catalog strings such as
`(ARCH 196 and ARCH 110) or (ARCH 161 and ARCH 164)` and
`CS 114 with a grade of C or better` into a boolean AST (AND / OR / COURSE / OTHER),
with AND binding tighter than OR and explicit parentheses overriding.

## Quality evaluation

Hybrid, per `schema/rubric.md`:

- **Deterministic signals** (`metrics.py`): prerequisite cycles, chain depth, dangling
  references, orphan courses, missing/thin descriptions, program credit reconciliation.
- **AI-scored dimensions** (Claude, grounded in those signals): curriculum coherence,
  prerequisite-structure health, learning outcomes, credit balance, presentation, industry
  relevance — plus course-level description quality and prerequisite clarity. Each is scored
  1–5 with a justification and a concrete suggestion, and a ranked `topSuggestions` list.
- **Field gap & trend analysis** (`fieldAnalysis`): per program, `missingTopics` (subjects
  the discipline expects but the program underweights) and `emergingTrends` (current/near-
  future directions to position for), each with a rationale grounded in the actual courses.

**Coverage:** all **121 undergraduate programs across all four colleges** (Ying Wu Computing,
Hillier Architecture & Design, Jordan Hu Science & Liberal Arts, Newark College of
Engineering) are evaluated. Re-run per college with the commands below.

## Regenerate

```bash
pip install -r catalog/pipeline/requirements.txt

cd catalog/pipeline
python extract.py          # PDF -> data/pages.json  (~1 min, once)
python build_ontology.py   # -> data/ontology.json (schema-validated)
python metrics.py          # -> data/metrics.json

# AI rubric pass (per college):
python build_eval_inputs.py <collegeId>   # e.g. ying-wu-college-of-computing
#   -> have Claude write data/evals/<programId>.json for each program packet,
#      scoring against schema/rubric.md
python evaluate.py         # merge data/evals/*.json -> data/evaluations.json
```

## View the dashboard locally

```bash
cd catalog
python -m http.server 8137
# open http://localhost:8137/site/index.html
```

(Serve over HTTP — `file://` blocks the `fetch()` calls the dashboard uses to load the JSON.)

## Scope / notes

- This is the **undergraduate** catalog. Graduate programs (e.g. the MS/PhD CS pages under
  `legacy/`) are out of scope for this pass; the schema and pipeline accommodate them when a
  graduate catalog is provided.
- Program plan-of-study parsing is robust for single degrees (credit totals reconcile for the
  large majority); combined/dual-degree pages and some minors have known layout quirks, which
  the `creditReconcileDelta` and dangling-reference metrics surface rather than hide.
