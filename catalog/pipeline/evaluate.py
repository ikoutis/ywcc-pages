"""Stage 4 (merge): assemble per-program AI evaluations into data/evaluations.json.

The AI rubric pass (run via Claude subagents at build time) writes one JSON file per
program to data/evals/<id>.json. This script validates and merges them, attaching the
deterministic evidence used, and records which programs remain unevaluated so coverage is
never silently overstated.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
DIMS = ["curriculum_coherence", "prereq_structure", "learning_outcomes",
        "credit_balance", "presentation", "industry_relevance"]


def main():
    ontology = json.load(open(os.path.join(DATA, "ontology.json")))
    metrics = json.load(open(os.path.join(DATA, "metrics.json")))
    programs = {p["id"]: p for p in ontology["programs"]}

    evals = {}
    for path in sorted(glob.glob(os.path.join(DATA, "evals", "*.json"))):
        ev = json.load(open(path))
        pid = ev.get("id")
        if pid not in programs:
            print("WARN: evaluation for unknown program id:", pid, os.path.basename(path))
            continue
        dims = {d["key"]: d for d in ev.get("dimensions", [])}
        missing = [k for k in DIMS if k not in dims]
        if missing:
            print(f"WARN: {pid} missing dimensions: {missing}")
        # recompute overall from present program dimensions for consistency
        scores = [d["score"] for d in ev.get("dimensions", []) if isinstance(d.get("score"), (int, float))]
        ev["overallScore"] = round(sum(scores) / len(scores), 2) if scores else None
        ev["evidence"] = metrics["programs"].get(pid, {})
        evals[pid] = ev

    evaluated = set(evals)
    computing = [p["id"] for p in ontology["programs"]
                 if p["collegeId"] == "ying-wu-college-of-computing"]
    out = {
        "meta": {
            "rubric": "schema/rubric.md",
            "method": "rubric + AI-assisted (Claude), grounded in deterministic metrics",
            "pilotScope": "Ying Wu College of Computing (degree programs)",
            "evaluatedCount": len(evals),
            "unevaluated": {
                "computingRemaining": sorted(set(computing) - evaluated),
                "note": "Other colleges are a follow-up run of the same pipeline.",
            },
        },
        "programs": evals,
    }
    with open(os.path.join(DATA, "evaluations.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Wrote evaluations.json: {len(evals)} programs evaluated")
    for pid, ev in evals.items():
        print(f"  {pid:44} overall={ev.get('overallScore')}")


if __name__ == "__main__":
    main()
