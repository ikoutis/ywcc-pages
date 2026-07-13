"""Stage 2a: parse course-description blocks out of the cached page text.

Course descriptions in the catalog follow a regular signature, e.g.:

    BNFO 135. Programming for Bioinformatics. 3 credits, 3 contact hours (3;0;0).
    <description...>
    BNFO 340. Data Analysis for Bioinformatics II. 3 credits, 3 contact hours (3;0;0).
    Prerequisites: BNFO 240 and R120 101 or equivalent or permission of instructor. <desc...>

We anchor on the "<CODE>. <Title>. <N> credits" signature (the literal word "credits"
after the title distinguishes real course descriptions from plan-of-study table rows,
which show credits as a bare trailing number). Each block runs to the next anchor.
"""
import re

from prereq_parser import parse_prerequisite

# running headers/footers to drop before parsing
NOISE_RE = re.compile(
    r"^(?:2024-2025 (?:Undergraduate|Graduate) \d+|\d+ New Jersey Institute of Technology"
    r"|New Jersey Institute of Technology)\s*$"
)

# anchor: CODE NUM. Title. N credits  (must start a line; single-space separators so we
# never match a code that wraps across a line break inside prose, e.g. "...or CS\n114.")
ANCHOR_RE = re.compile(
    r"(?m)^[ ]*(?P<code>[A-Z]{2,4}) (?P<num>\d{3}[A-Z]?)\. "
    r"(?P<title>[^\n]+?)\. "
    r"(?P<credits>\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s+credits\b"
)
CONTACT_RE = re.compile(r"\A[,\s]*(?P<hours>\d+(?:\.\d+)?)\s+contact hours\s*(?P<tuple>\([0-9.;/ ]+\))?")
PREREQ_RE = re.compile(r"(?:Prerequisites?|Prereq)(?:\s+and\s+Corequisites?)?:\s*([^.]+)\.", re.I)
COREQ_RE = re.compile(r"(?:Corequisites?|Coprerequisites?):\s*([^.]+)\.", re.I)


def clean_pages_text(pages):
    """Join page texts, dropping running header/footer lines."""
    out = []
    for p in pages:
        for line in (p["text"] or "").split("\n"):
            if NOISE_RE.match(line.strip()):
                continue
            out.append(line)
    return "\n".join(out)


def _num(s):
    if s is None:
        return None
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_courses(pages):
    text = clean_pages_text(pages)
    anchors = list(ANCHOR_RE.finditer(text))
    courses = {}
    for i, m in enumerate(anchors):
        code = f"{m.group('code')} {m.group('num')}"
        block_end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        rest = text[m.end():block_end]

        contact_hours = None
        cm = CONTACT_RE.match(rest)
        if cm:
            contact_hours = (cm.group("tuple") or f"{cm.group('hours')} contact hours")
            rest = rest[cm.end():]
        # drop a leading period/space left from the signature line
        rest = rest.lstrip(" .\n")

        prereq_raw = None
        coreq_raw = None
        pm = PREREQ_RE.search(rest[:400])
        if pm:
            val = pm.group(1).strip()
            # graduate courses often say "No formal prerequisites - ..." -> treat as none
            if val.lower() not in ("none", "n/a") and not re.match(
                    r"(?i)^no (formal )?(pre-?requisite|prereq)", val):
                prereq_raw = re.sub(r"\s+", " ", val)
            rest = rest[:pm.start()] + rest[pm.end():]
        km = COREQ_RE.search(rest[:400])
        if km:
            val = km.group(1).strip()
            if val.lower() not in ("none", "n/a"):
                coreq_raw = re.sub(r"\s+", " ", val)
            rest = rest[:km.start()] + rest[km.end():]

        description = re.sub(r"\s+", " ", rest).strip()
        # cut description at the start of the next section header if any leaked in
        description = re.split(r"\b[A-Z][a-z]+ College of\b", description)[0].strip()

        ast, pre_courses = parse_prerequisite(prereq_raw) if prereq_raw else (None, [])
        _, co_courses = parse_prerequisite(coreq_raw) if coreq_raw else (None, [])

        rec = {
            "code": code,
            "subject": m.group("code"),
            "number": m.group("num"),
            "title": re.sub(r"\s+", " ", m.group("title")).strip(),
            "credits": _num(m.group("credits")),
            "creditsRaw": m.group("credits").strip(),
            "contactHours": contact_hours,
            "description": description or None,
            "prerequisiteRaw": prereq_raw,
            "prerequisiteAst": ast,
            "corequisiteRaw": coreq_raw,
            "corequisites": [c["code"] for c in co_courses],
            "_prereqCourses": pre_courses,  # internal, stripped before serialisation
        }
        # keep the first occurrence (course sections are canonical; later dupes are rare)
        if code not in courses:
            courses[code] = rec
    return list(courses.values())


if __name__ == "__main__":
    import json
    import sys

    pages = json.load(open("../data/pages.json"))["pages"] if len(sys.argv) < 2 else json.load(open(sys.argv[1]))["pages"]
    courses = parse_courses(pages)
    print("parsed courses:", len(courses))
    subjects = {}
    for c in courses:
        subjects[c["subject"]] = subjects.get(c["subject"], 0) + 1
    print("subjects:", len(subjects))
    with_pre = sum(1 for c in courses if c["prerequisiteRaw"])
    print("with prerequisite:", with_pre, " with corequisite:", sum(1 for c in courses if c["corequisiteRaw"]))
    # spot-check a few CS courses
    byc = {c["code"]: c for c in courses}
    for code in ["CS 113", "CS 114", "CS 280", "CS 332", "CS 356"]:
        c = byc.get(code)
        if c:
            print(f"\n{code}: {c['title']} | {c['credits']}cr | contact={c['contactHours']}")
            print("  prereq:", c["prerequisiteRaw"])
            print("  desc:", (c["description"] or "")[:120])
