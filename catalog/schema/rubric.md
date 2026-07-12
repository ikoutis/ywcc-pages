# Program & Course Quality Rubric

A hybrid rubric. **Deterministic signals** (computed in `pipeline/metrics.py`) are objective
and feed the AI as evidence. **AI-scored dimensions** are judged by an LLM against that
evidence plus the program's descriptions and structure. Every AI dimension is scored **1–5**
with a one-paragraph justification and one concrete, actionable suggestion.

Score scale (all dimensions): **1** = serious problem · **2** = weak · **3** = adequate ·
**4** = strong · **5** = exemplary.

## Deterministic signals (evidence, not scored directly)

| Signal | Meaning |
| --- | --- |
| `deepestPrereqChain` | Longest prerequisite chain among the program's courses (structure depth). |
| `missingCourseCount` | Referenced course codes absent from the undergraduate catalog (dangling references). |
| `creditReconcileDelta` | Summed term credits − stated total credits (0 = internally consistent). |
| `requirementGroups` | Number of parsed plan-of-study terms/groups. |
| course `danglingPrereqs`, `depth`, `inDegree`/`outDegree` | Per-course prerequisite-graph health. |
| course `missingDescription` / `thinDescription` / `missingCredits` | Course presentation completeness. |

## AI-scored dimensions — Program level

1. **Curriculum coherence & progression** — Do courses build logically term over term; is the
   sequence well-ordered; are there gaps or abrupt jumps in difficulty?
2. **Prerequisite structure health** — Is the prerequisite graph sensible (reasonable depth, no
   dangling references, no over-/under-constraining)? Uses `deepestPrereqChain`,
   `missingCourseCount`, per-course dangling data.
3. **Learning outcomes & objectives** — Are program-level learning outcomes / educational
   objectives stated and clear? (Absence is a real finding for a catalog page.)
4. **Credit distribution & balance** — Is the split across general-education, major core, and
   electives balanced and transparent; does the plan reconcile to the stated total
   (`creditReconcileDelta`)?
5. **Presentation & clarity** — Is the catalog page well-structured, readable, and complete
   (description present, plan legible, terms labeled)?
6. **Industry & currency relevance** — Do required and elective courses reflect current
   practice in the discipline; are there notable modern gaps or dated emphases?

## AI-scored dimensions — Course level (aggregated per program)

- **Description quality** — Are course descriptions present, specific, and informative
  (not thin/placeholder)?
- **Prerequisite clarity** — Are prerequisites stated unambiguously and internally consistent
  (no dangling references, sensible grade conditions)?

## Output

Per program: an `overallScore` (mean of program-level dimensions), each dimension's
`score` + `justification` + `suggestion`, and a ranked `topSuggestions` list (the highest-
impact, most actionable improvements first). Written to `data/evaluations.json`.
