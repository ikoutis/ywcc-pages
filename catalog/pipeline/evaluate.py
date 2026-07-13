"""Stage 4 (merge): assemble per-program AI evaluations into data/evaluations.json.

The AI rubric pass (run via Claude subagents at build time) writes one JSON file per
program to data/evals/<id>.json. This script validates and merges them, attaching the
deterministic evidence used, and records which programs remain unevaluated so coverage is
never silently overstated.
"""
import glob
import json
import os
import sys

import config

DIMS = ["curriculum_coherence", "prereq_structure", "learning_outcomes",
        "credit_balance", "presentation", "industry_relevance"]


def main(level="undergraduate"):
    cfg = config.resolve(level)
    ontology = json.load(open(cfg["ontology"]))
    metrics = json.load(open(cfg["metrics"]))
    programs = {p["id"]: p for p in ontology["programs"]}

    evals = {}
    malformed = []
    for path in sorted(glob.glob(os.path.join(cfg["evals_dir"], "*.json"))):
        try:
            ev = json.load(open(path))
        except Exception as e:
            malformed.append(os.path.basename(path))
            print(f"WARN: malformed JSON, skipping {os.path.basename(path)}: {e}")
            continue
        pid = ev.get("id")
        if pid not in programs:
            print("WARN: evaluation for unknown program id:", pid, os.path.basename(path))
            continue
        dims = {d["key"]: d for d in ev.get("dimensions", [])}
        missing = [k for k in DIMS if k not in dims]
        if missing:
            print(f"WARN: {pid} missing dimensions: {missing}")
        fa = ev.get("fieldAnalysis") or {}
        if not fa.get("missingTopics") and not fa.get("emergingTrends"):
            print(f"WARN: {pid} has no fieldAnalysis (missing topics / trends)")
        # recompute overall from present program dimensions for consistency
        scores = [d["score"] for d in ev.get("dimensions", []) if isinstance(d.get("score"), (int, float))]
        ev["overallScore"] = round(sum(scores) / len(scores), 2) if scores else None
        ev["evidence"] = metrics["programs"].get(pid, {})
        evals[pid] = ev

    evaluated = set(evals)
    all_ids = [p["id"] for p in ontology["programs"]]
    by_college = {}
    for p in ontology["programs"]:
        by_college.setdefault(p["collegeId"], []).append(p["id"])
    coverage = {c: {"total": len(ids), "evaluated": len(set(ids) & evaluated)}
                for c, ids in by_college.items()}
    out = {
        "meta": {
            "level": level,
            "rubric": "schema/rubric.md",
            "method": "rubric + AI-assisted (Claude), grounded in deterministic metrics; "
                      "includes field missing-topics and emerging-trends analysis",
            "scope": "all colleges",
            "evaluatedCount": len(evals),
            "totalPrograms": len(all_ids),
            "coverageByCollege": coverage,
            "unevaluated": sorted(set(all_ids) - evaluated),
            "malformedFiles": malformed,
        },
        "programs": evals,
    }
    with open(cfg["evaluations"], "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"[{level}] Wrote {cfg['evaluations']}: {len(evals)} programs evaluated")
    for pid, ev in evals.items():
        print(f"  {pid:44} overall={ev.get('overallScore')}")


if __name__ == "__main__":
    main(config.level_from_argv(sys.argv))
