"""Assemble the full ontology from the parsed courses + program hierarchy, validate it
against the JSON Schema, and write catalog/data/ontology.json.

Run:  python catalog/pipeline/build_ontology.py
Requires catalog/data/pages.json (produced by extract.py).
"""
import json
import os
import re

import pdfplumber
from jsonschema import Draft7Validator

from parse_courses import parse_courses
from parse_programs import parse_toc, build_hierarchy, parse_program_body

import config

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "..", "schema", "ontology.schema.json")
CODE_RE = re.compile(r"^[A-Z]{2,4} \d{3}[A-Z]?$")


def build(level="undergraduate"):
    cfg = config.resolve(level)
    with open(cfg["pages"]) as f:
        pages = json.load(f)["pages"]

    # --- courses + prerequisite/corequisite edges ---
    courses = parse_courses(pages)
    edges = []
    for c in courses:
        for pc in c.pop("_prereqCourses", []):
            if CODE_RE.match(pc["code"]):
                edges.append({"from": c["code"], "to": pc["code"],
                              "minGrade": pc.get("minGrade"), "kind": "prerequisite"})
        for co in c.get("corequisites", []):
            if CODE_RE.match(co):
                edges.append({"from": c["code"], "to": co, "minGrade": None, "kind": "corequisite"})

    # --- subjects ---
    subj = {}
    for c in courses:
        subj[c["subject"]] = subj.get(c["subject"], 0) + 1
    subjects = [{"code": k, "name": None, "courseCount": v} for k, v in sorted(subj.items())]

    # --- college / department / program hierarchy ---
    with pdfplumber.open(cfg["pdf"]) as pdf:
        entries = parse_toc(pdf)
    colleges, departments, programs = build_hierarchy(entries, level)

    order = sorted(programs, key=lambda p: p["printedPage"])
    full_programs = []
    for i, p in enumerate(order):
        prev = order[i - 1]["printedPage"] if i > 0 else None
        nxt = order[i + 1]["printedPage"] if i + 1 < len(order) else None
        full_programs.append(parse_program_body(p, pages, prev, nxt, level))

    ontology = {
        "meta": {
            "source": os.path.basename(cfg["pdf"]),
            "catalogYear": cfg["catalogYear"],
            "level": cfg["level"],
            "generated": "build_ontology.py",
            "counts": {
                "colleges": len(colleges),
                "departments": len(departments),
                "subjects": len(subjects),
                "programs": len(full_programs),
                "courses": len(courses),
                "prerequisiteEdges": len(edges),
            },
        },
        "colleges": colleges,
        "departments": departments,
        "subjects": subjects,
        "programs": full_programs,
        "courses": courses,
        "prerequisiteEdges": edges,
    }

    # --- validate ---
    with open(SCHEMA) as f:
        schema = json.load(f)
    errs = sorted(Draft7Validator(schema).iter_errors(ontology), key=lambda e: e.path)
    if errs:
        for e in errs[:10]:
            print("SCHEMA ERROR:", list(e.path), e.message)
        raise SystemExit(f"Ontology failed schema validation ({len(errs)} errors).")

    out = cfg["ontology"]
    with open(out, "w") as f:
        json.dump(ontology, f, indent=None, separators=(",", ":"))
    print(f"[{level}] Wrote {out}")
    print("counts:", json.dumps(ontology["meta"]["counts"]))
    return ontology


if __name__ == "__main__":
    import sys
    build(config.level_from_argv(sys.argv))
