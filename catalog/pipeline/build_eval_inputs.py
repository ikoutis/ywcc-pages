"""Build compact per-program evaluation packets for the AI rubric pass.

Each packet bundles everything an evaluator needs to score a program against the rubric:
program metadata, parsed plan-of-study groups, deterministic metrics, and a sample of the
program's referenced courses (with descriptions + prerequisites). Written to
data/eval_inputs.json keyed by program id.

Usage:
    python build_eval_inputs.py                 # default: Ying Wu College of Computing degrees
    python build_eval_inputs.py <collegeId>     # a different college
"""
import json
import os
import sys

import config

MAX_SAMPLE_COURSES = 40


def build(college_id, level="undergraduate", degrees_only=False):
    cfg = config.resolve(level)
    ontology = json.load(open(cfg["ontology"]))
    metrics = json.load(open(cfg["metrics"]))
    courses = {c["code"]: c for c in ontology["courses"]}
    cmetrics = metrics["courses"]

    packets = {}
    for p in ontology["programs"]:
        if p["collegeId"] != college_id:
            continue
        if degrees_only and p["kind"] != "degree":
            continue
        pm = metrics["programs"][p["id"]]
        refs = p.get("courseCodes", [])
        sample = []
        for code in refs[:MAX_SAMPLE_COURSES]:
            c = courses.get(code)
            if not c:
                continue
            desc = (c.get("description") or "")[:220]
            sample.append({
                "code": code,
                "title": c.get("title"),
                "credits": c.get("credits"),
                "depth": cmetrics.get(code, {}).get("depth"),
                "prerequisiteRaw": c.get("prerequisiteRaw"),
                "descriptionExcerpt": desc,
            })
        groups = [{
            "name": g["name"],
            "credits": g.get("credits"),
            "items": [{"code": it.get("code"), "title": it.get("title"), "credits": it.get("credits")}
                      for it in g["items"]],
        } for g in (p.get("requirementGroups") or [])]

        packets[p["id"]] = {
            "id": p["id"],
            "name": p["name"],
            "degree": p.get("degree"),
            "kind": p["kind"],
            "college": p["collegeId"],
            "department": p.get("departmentId"),
            "statedTotalCredits": p.get("statedTotalCredits"),
            "requirementGroups": groups,
            "metrics": {
                "referencedCourses": pm["referencedCourses"],
                "missingCourseCount": pm["missingCourseCount"],
                "missingCoursesSample": pm["missingCourses"][:15],
                "deepestPrereqChain": pm["deepestPrereqChain"],
                "requirementGroups": pm["requirementGroups"],
                "summedTermCredits": pm["summedTermCredits"],
                "creditReconcileDelta": pm["creditReconcileDelta"],
            },
            "sampleCourses": sample,
        }

    out = os.path.join(cfg["data"], f"eval_inputs_{college_id}.json")
    with open(out, "w") as f:
        json.dump(packets, f, indent=1)
    print(f"[{level}] Wrote {out}: {len(packets)} program packets for {college_id}")
    for pid, pk in packets.items():
        print(f"  {pid:44} {pk['kind']:6} sampleCourses={len(pk['sampleCourses'])}")
    return packets


if __name__ == "__main__":
    # usage: build_eval_inputs.py <collegeId> [level]
    college = sys.argv[1] if len(sys.argv) > 1 else "ying-wu-college-of-computing"
    lvl = sys.argv[2] if len(sys.argv) > 2 else "undergraduate"
    build(college, lvl)
