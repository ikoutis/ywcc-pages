# NJIT Catalog Ontology & Quality Dashboard

A structured **ontology** of the NJIT catalog — every program and course, with prerequisite
**dependencies** — plus a **rubric + AI-assisted quality evaluation** (including field
missing-topics / emerging-trends analysis) and a browsable **dashboard**.

Covers **both levels**, each built from its official catalog PDF:

| Level | Source PDF | Colleges | Programs | Courses | Prereq edges |
| --- | --- | --- | --- | --- | --- |
| Undergraduate | `source/2024-2025 Undergraduate.pdf` | 5 | 121 | 1,276 | 2,373 |
| Graduate | `source/2024-2025 Graduate.pdf` | 4 | 130 | 1,207 | 610 |

Live view (once deployed): `njit-jc.cc/catalog/site/` — the dashboard has an
**Undergraduate / Graduate** switch.

```
catalog/
  source/                  the two catalog PDFs
  schema/
    ontology.schema.json   JSON Schema the ontology is validated against
    rubric.md              the quality rubric (dimensions, scales, field analysis)
  pipeline/                the re-runnable, level-aware pipeline
    config.py              level -> {pdf, data dir} resolution
    extract.py             PDF -> per-level page-text cache
    parse_courses.py       course-description blocks -> course records
    parse_programs.py      TOC hierarchy + requirements -> program records
                           (undergraduate term plans AND graduate Core/Elective groups)
    prereq_parser.py       prerequisite string -> boolean AST + dependency edges
    metrics.py             deterministic quality signals + graph metrics
    build_ontology.py      assemble + schema-validate -> <level>/ontology.json
    build_eval_inputs.py   per-college evaluation packets
    evaluate.py            merge AI evaluations -> <level>/evaluations.json
  data/
    undergraduate/         ontology.json, metrics.json, evaluations.json, evals/  [committed]
    graduate/              ontology.json, metrics.json, evaluations.json, evals/  [committed]
    <level>/pages.json, eval_inputs*.json   (gitignored, regenerable caches)
  site/                    self-contained static dashboard (level-switchable)
```

## Data model (`data/<level>/ontology.json`)

- **colleges / departments / subjects** — the academic hierarchy (from the TOC).
- **programs** — `{name, degree, kind, collegeId, departmentId, statedTotalCredits,
  requirementGroups[], courseCodes[]}`. `kind` is degree / minor / certificate. Undergraduate
  requirement groups are the term-by-term plan of study; graduate groups are named
  requirement blocks (Core Courses, Elective Courses, …).
- **courses** — `{code, subject, number, title, credits, contactHours, description,
  prerequisiteRaw, prerequisiteAst, corequisites[]}`.
- **prerequisiteEdges** — directed `from → to` edges (course → its prerequisite), with
  `minGrade` and `kind`. This is the dependency graph.

## Quality evaluation (`schema/rubric.md`)

Hybrid. **Deterministic signals** (`metrics.py`): prerequisite cycles, chain depth, dangling
references, orphan courses, missing/thin descriptions, credit reconciliation. **AI-scored
dimensions** (Claude, grounded in those signals, 1–5 + justification + suggestion):
curriculum coherence, prerequisite-structure health, learning outcomes, credit balance,
presentation, industry relevance — plus course-level description quality and prerequisite
clarity. **Field analysis** (`fieldAnalysis`): per-program `missingTopics` and
`emergingTrends`, each with a discipline-grounded rationale.

Both levels are evaluated across all colleges.

## Regenerate

```bash
pip install -r catalog/pipeline/requirements.txt
cd catalog/pipeline

# choose a level: undergraduate | graduate
LEVEL=graduate
python extract.py $LEVEL          # PDF -> data/$LEVEL/pages.json  (~1-2 min, once)
python build_ontology.py $LEVEL   # -> data/$LEVEL/ontology.json (schema-validated)
python metrics.py $LEVEL          # -> data/$LEVEL/metrics.json

# AI rubric pass (per college):
python build_eval_inputs.py <collegeId> $LEVEL   # -> data/$LEVEL/eval_inputs_<collegeId>.json
#   -> have Claude write data/$LEVEL/evals/<programId>.json per program, scoring against
#      schema/rubric.md (see the instructions used in the eval subagents)
python evaluate.py $LEVEL         # merge data/$LEVEL/evals/*.json -> data/$LEVEL/evaluations.json
```

## View the dashboard locally

```bash
cd catalog
python -m http.server 8137
# open http://localhost:8137/site/index.html  (toggle Undergraduate / Graduate)
```

(Serve over HTTP — `file://` blocks the `fetch()` calls the dashboard uses to load JSON.)

## Notes

- The pipeline auto-adapts to each catalog's layout: undergraduate uses a term-by-term plan
  of study; graduate uses named requirement groups and includes topic-named graduate
  certificates (e.g. "Foundations of Cybersecurity").
- Combined/dual-degree pages and some certificates/minors have known layout quirks, which the
  `creditReconcileDelta` and dangling-reference metrics surface rather than hide.
