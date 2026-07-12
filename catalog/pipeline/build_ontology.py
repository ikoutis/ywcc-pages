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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "..", "data")
SCHEMA = os.path.join(HERE, "..", "schema", "ontology.schema.json")
PDF_PATH = os.path.join(ROOT, "2024-2025 Undergraduate.pdf")
CODE_RE = re.compile(r"^[A-Z]{2,4} \d{3}[A-Z]?$")


def build():
    with open(os.path.join(DATA, "pages.json")) as f:
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
    with pdfplumber.open(PDF_PATH) as pdf:
        entries = parse_toc(pdf)
    colleges, departments, programs = build_hierarchy(entries)

    order = sorted(programs, key=lambda p: p["printedPage"])
    full_programs = []
    for i, p in enumerate(order):
        prev = order[i - 1]["printedPage"] if i > 0 else None
        nxt = order[i + 1]["printedPage"] if i + 1 < len(order) else None
        full_programs.append(parse_program_body(p, pages, prev, nxt))

    ontology = {
        "meta": {
            "source": "2024-2025 Undergraduate.pdf",
            "catalogYear": "2024-2025",
            "level": "undergraduate",
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

    out = os.path.join(DATA, "ontology.json")
    with open(out, "w") as f:
        json.dump(ontology, f, indent=None, separators=(",", ":"))
    print("Wrote", out)
    print("counts:", json.dumps(ontology["meta"]["counts"]))
    return ontology


if __name__ == "__main__":
    build()
