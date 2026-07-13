"""Stage 2b: parse the table-of-contents hierarchy and per-program requirements.

The catalog TOC (first ~6 pages) encodes college -> department -> program via left-edge
indentation (word x0). Each entry ends in a printed page number. We reconstruct the
hierarchy, then for each program read its page range and pull out:
  - stated total credits ("Total Credits N")
  - a short description (prose before the plan of study)
  - requirement groups (plan of study, grouped by Year / Semester)
  - the set of course codes it references (inline codes + ?P=SUBJ%20NUM catalog links)

Printed page number == PDF index + 1 for this document (verified: all pages agree).
"""
import re
from collections import defaultdict

PRINTED_OFFSET = 1  # printed_page = pdf_index + 1

DEGREE_RE = re.compile(
    r"^(B\.S\.|B\.A\.|B\.F\.A\.|B\.Arch\.?|Bachelor|B\.S\.E\.T\.|B\.S\.[A-Z]"
    r"|M\.S\.|M\.A\.|M\.Arch\.?|M\.B\.A\.?|M\.F\.A\.?|M\.Eng\.?|M\.Sc\.?"
    r"|Master|Ph\.?\s?D\.?|Doctor)", re.I
)
URL_RE = re.compile(r"\((?:https?://)?catalog\.njit\.edu[^)]*\)")
PPARAM_RE = re.compile(r"\?P=([A-Z]{2,4})%20(\d{3}[A-Z]?)")
CODE_INLINE_RE = re.compile(r"\b([A-Z]{2,4}) (\d{3}[A-Z]?)\b")
NOISE_LINE_RE = re.compile(
    r"^(?:2024-2025 (?:Undergraduate|Graduate) \d+|\d+ New Jersey Institute of Technology)\s*$")

YEAR_RE = re.compile(r"^((?:First|Second|Third|Fourth|Fifth|Sixth) Year)\s*$")
SEM_RE = re.compile(r"^(\d(?:st|nd|rd|th) Semester|Fall Semester|Spring Semester|Summer(?: Semester)?)(?:\s+Credits)?\s*$")
TERMCR_RE = re.compile(r"^Term Credits\s+(\d+(?:\.\d+)?)\s*$")
TOTALCR_RE = re.compile(r"Total Credits\s+(\d+(?:\.\d+)?)")

# graduate requirement-group format: "Core Courses (12 credits)", "Elective Courses (18 credits)"
GRAD_GROUP_RE = re.compile(r"^(.{2,60}?)\s*\((\d+(?:\.\d+)?)\s*credits?\)\s*$", re.I)
GRAD_ROWCODE_RE = re.compile(r"^([A-Z]{2,4}(?:/[A-Z]{2,4})?\s\d{3}[A-Z]?)\s+(.+)$")
GRAD_TOTAL_RE = re.compile(
    r"(?:completion of|requires?(?:\s+a\s+minimum\s+of)?|minimum of|total of)\s+(\d+)\s+credits", re.I)
# start of a course-DESCRIPTION block ("CS 610. Data Structures. 3 credits") — marks the end
# of a program's requirements region and the beginning of the department course dump
COURSE_DESC_ANCHOR = re.compile(r"^[A-Z]{2,4} \d{3}[A-Z]?\. .+?\. \d+(?:\.\d+)? credits", re.I)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def looks_like_program(title):
    return bool(DEGREE_RE.match(title)) or "Minor" in title or "Certificate" in title


def program_kind(title):
    if "Minor" in title:
        return "minor"
    if "Certificate" in title:
        return "certificate"
    if DEGREE_RE.match(title):
        return "degree"
    return "other"


def degree_of(title):
    m = re.match(
        r"(B\.S\.|B\.A\.|B\.F\.A\.|B\.Arch\.?|M\.S\.|M\.A\.|M\.Arch\.?|M\.B\.A\.?|M\.F\.A\.?"
        r"|M\.Eng\.?|Ph\.?\s?D\.?|Bachelor of [A-Za-z]+|Master of [A-Za-z]+|Doctor of [A-Za-z]+)",
        title)
    return m.group(1).strip() if m else None


def parse_toc(pdf):
    """Return list of entries {x0, title, printed} in reading order from TOC pages."""
    entries = []
    for i in range(0, 8):
        page = pdf.pages[i]
        text = page.extract_text() or ""
        if text.count("..") < 20:
            continue
        words = page.extract_words(use_text_flow=True)
        lines = defaultdict(list)
        for w in words:
            lines[round(w["top"])].append(w)
        for top in sorted(lines):
            ws = sorted(lines[top], key=lambda w: w["x0"])
            txt = " ".join(w["text"] for w in ws)
            m = re.match(r"(.+?)\s*\.{2,}\s*(\d+)\s*$", txt)
            if not m:
                continue
            title = m.group(1).strip(" .")
            entries.append({"x0": round(ws[0]["x0"]), "title": title, "printed": int(m.group(2))})
    return entries


def build_hierarchy(entries, level="undergraduate"):
    """From TOC entries, produce colleges, departments, programs (with page ranges).

    Programs sit at the deepest TOC indentation (x0==81). For undergraduate we key off the
    degree/minor/certificate wording; for graduate, many certificates are named by topic
    ("Foundations of Cybersecurity") with no degree wording, so every x0==81 entry under a
    college is treated as a program (non-degree ones are graduate certificates).
    """
    colleges, departments, programs = [], [], []
    cur_college = None
    cur_dept = None
    # academic content begins at the first real college; ignore front matter
    for idx, e in enumerate(entries):
        title, printed = e["title"], e["printed"]
        if "College" in title and printed >= 113:
            cur_college = {"id": slug(title), "name": title, "printedPage": printed}
            colleges.append(cur_college)
            cur_dept = None
            continue
        if printed < 145:  # front matter / policies, before first college
            continue
        is_program = looks_like_program(title)
        if not is_program and level == "graduate" and e.get("x0") == 81 and cur_college:
            is_program = True  # topic-named graduate certificate
        if is_program:
            kind = program_kind(title)
            if kind == "other" and level == "graduate":
                kind = "certificate"
            programs.append({
                "id": slug(title) + f"-{printed}",
                "name": title,
                "degree": degree_of(title),
                "kind": kind,
                "collegeId": cur_college["id"] if cur_college else None,
                "departmentId": cur_dept["id"] if cur_dept else None,
                "printedPage": printed,
                "_order": idx,
            })
        else:
            # a department / section heading
            cur_dept = {"id": slug(title), "name": title,
                        "collegeId": cur_college["id"] if cur_college else None,
                        "printedPage": printed}
            departments.append(cur_dept)
    return colleges, departments, programs


def _clean_lines(pages, start_idx, end_idx):
    lines = []
    for i in range(start_idx, min(end_idx, len(pages))):
        for ln in (pages[i]["text"] or "").split("\n"):
            if NOISE_LINE_RE.match(ln.strip()):
                continue
            lines.append(ln.rstrip())
    return lines


def _coalesce(lines):
    """Merge lines whose parentheses are unbalanced (a catalog URL wrapped across a line
    break) into one logical line, so URL parentheticals strip cleanly afterwards."""
    out, buf = [], None
    for ln in lines:
        s = ln.rstrip()
        buf = s if buf is None else (buf + " " + s.strip())
        if buf.count("(") <= buf.count(")"):
            out.append(buf)
            buf = None
    if buf is not None:
        out.append(buf)
    return out


CREDITS_HDR_RE = re.compile(r"\((\d+(?:\.\d+)?)\s*credits", re.I)
PLAN_HDR_RE = re.compile(r"^(First Year|Plan of Study|Degree Requirements|Curriculum|Program Requirements)\b")


def parse_program_body(program, pages, prev_printed, next_printed, level="undergraduate"):
    name = program["name"]
    # generous idx window around the TOC page (the spread starts a page or two before it)
    lo = max(0, (prev_printed - PRINTED_OFFSET) if prev_printed else program["printedPage"] - PRINTED_OFFSET - 4)
    hi = min(len(pages), (next_printed - PRINTED_OFFSET + 1) if next_printed else program["printedPage"] - PRINTED_OFFSET + 4)
    lines = _clean_lines(pages, lo, hi)
    # drop running-header lines "<pageno> <program name>"
    hdr_re = re.compile(r"^\d{1,4}\s+" + re.escape(name) + r"\s*$")
    lines = [ln for ln in lines if not hdr_re.match(ln.strip())]

    # Graduate programs use named "(N credits)" requirement groups rather than a term-by-term
    # plan of study, so they get a dedicated parser.
    if level == "graduate":
        return _finish_graduate(program, lines)

    # locate the canonical requirements block: a bare program-name line followed shortly
    # by "(NN credits" or a plan header, reading to the next "Total Credits N".
    # Only degrees have a year/semester plan of study; minors/certificates are flat course
    # lists, so we skip the plan search for them (it would absorb an adjacent degree's plan).
    nonempty = [(k, ln.strip()) for k, ln in enumerate(lines) if ln.strip()]
    start_k = None
    stated = None
    if program.get("kind") == "degree":
        for pos, (k, s) in enumerate(nonempty):
            if s == name:
                lookahead = " ".join(t for _, t in nonempty[pos + 1:pos + 4])
                cm = CREDITS_HDR_RE.search(lookahead)
                if cm or PLAN_HDR_RE.search(lookahead):
                    start_k = k
                    if cm:
                        stated = float(cm.group(1))
                    break

    # Bound the requirements region so course-code collection doesn't bleed into the
    # neighbouring department's course-description pages.
    if start_k is not None:
        end_k = len(lines)
        for j in range(start_k + 1, len(lines)):
            if TOTALCR_RE.search(lines[j]):
                end_k = j + 1
                break
        else:
            end_k = min(len(lines), start_k + 160)
        req_lines = lines[start_k:end_k]
    else:
        # no clean plan-of-study block: fall back to a narrow window around the TOC page
        nlo = max(0, program["printedPage"] - PRINTED_OFFSET - 1)
        nhi = min(len(pages), program["printedPage"] - PRINTED_OFFSET + 2)
        req_lines = [ln for ln in _clean_lines(pages, nlo, nhi)
                     if not hdr_re.match(ln.strip())]

    req_lines = _coalesce(req_lines)
    req_raw = "\n".join(req_lines)
    if stated is None:
        tm = TOTALCR_RE.search(req_raw)
        if tm:
            stated = float(tm.group(1))
    # a minor/certificate credit total in the 100s is implausible (bled from a neighbour)
    if program.get("kind") in ("minor", "certificate") and stated is not None and stated > 40:
        stated = None

    # referenced course codes within the bounded requirements region
    codes = set()
    for m in PPARAM_RE.finditer(req_raw):
        codes.add(f"{m.group(1)} {m.group(2)}")
    for m in CODE_INLINE_RE.finditer(URL_RE.sub(" ", req_raw)):
        codes.add(f"{m.group(1)} {m.group(2)}")

    groups = []
    cur = None
    cur_year = ""
    for ln in (req_lines if program.get("kind") == "degree" else []):
        s = ln.strip()
        if not s:
            continue
        if TOTALCR_RE.search(s) and groups:
            break
        ym = YEAR_RE.match(s)
        if ym:
            cur_year = ym.group(1)
            continue
        sm = SEM_RE.match(s)
        if sm:
            cur = {"name": f"{cur_year} — {sm.group(1)}".strip(" —"), "credits": None, "items": []}
            groups.append(cur)
            continue
        tcm = TERMCR_RE.match(s)
        if tcm and cur:
            cur["credits"] = float(tcm.group(1))
            cur = None
            continue
        if cur is not None:
            item = _parse_req_item(s)
            if item:
                cur["items"].append(item)

    program = {k: v for k, v in program.items() if not k.startswith("_")}
    program.update({
        "statedTotalCredits": stated,
        "totalCredits": sum(g["credits"] for g in groups if g["credits"]) or None,
        "description": None,
        "requirementGroups": [g for g in groups if g["items"]],
        "courseCodes": sorted(codes),
    })
    return program


def _finish_graduate(program, lines):
    """Parse a graduate program: named '(N credits)' requirement groups, 'Code Title' rows,
    and a stated total from 'requires the completion of N credits' (or the sum of groups)."""
    name = program["name"]
    start = next((i for i, ln in enumerate(lines) if ln.strip() == name), 0)
    block = _coalesce(lines[start:])

    # Bound the block: stop at the next program heading, at the first course-DESCRIPTION line
    # ("CS 610. Title. 3 credits" — the department course dump, which is not requirements),
    # or after a hard line cap. This prevents stub/certificate pages from absorbing the
    # neighbouring course-description section.
    trimmed = []
    for j, ln in enumerate(block):
        s = ln.strip()
        if j > 0 and COURSE_DESC_ANCHOR.match(s):
            break
        if j > 0 and s != name and DEGREE_RE.match(s) and len(s) < 80 and \
                (any(GRAD_GROUP_RE.match(x.strip()) for x in trimmed) or len(trimmed) > 10):
            break
        trimmed.append(ln)
        if len(trimmed) >= 150:
            break
    block = trimmed
    raw = "\n".join(block)

    stated = None
    gm = GRAD_TOTAL_RE.search(raw)
    if gm:
        stated = float(gm.group(1))
    if stated is not None and stated < 6:  # implausible total for a grad program -> unreliable
        stated = None

    codes = set()
    for m in PPARAM_RE.finditer(raw):
        codes.add(f"{m.group(1)} {m.group(2)}")
    for m in CODE_INLINE_RE.finditer(URL_RE.sub(" ", raw)):
        codes.add(f"{m.group(1)} {m.group(2)}")

    groups = []
    cur = None
    for ln in block:
        s = URL_RE.sub("", ln).strip()
        if not s:
            continue
        gh = GRAD_GROUP_RE.match(s)
        if gh and not re.match(r"(?i)^(select|required|total|choose|up to|at least|at most)\b", gh.group(1)):
            cur = {"name": gh.group(1).strip(), "credits": float(gh.group(2)), "items": []}
            groups.append(cur)
            continue
        if re.match(r"(?i)^(code title credits|total credits\b|select .*following|required:|choose )", s):
            continue
        if cur is not None:
            rm = GRAD_ROWCODE_RE.match(s)
            if rm:
                cur["items"].append({"code": re.sub(r"\s+", " ", rm.group(1)),
                                     "title": rm.group(2).strip() or None,
                                     "credits": None, "raw": s})
    if stated is None and groups:
        stated = sum(g["credits"] for g in groups if g["credits"]) or None

    program = {k: v for k, v in program.items() if not k.startswith("_")}
    program.update({
        "statedTotalCredits": stated,
        "totalCredits": sum(g["credits"] for g in groups if g["credits"]) or None,
        "description": None,
        "requirementGroups": [g for g in groups if g["items"]],
        "courseCodes": sorted(codes),
    })
    return program


def _parse_req_item(s):
    s = URL_RE.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return None
    # trailing credit number (may be preceded by a footnote superscript digit)
    m = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)$", s)
    credits = None
    body = s
    if m:
        body = m.group(1).strip()
        credits = float(m.group(2))
    cm = re.match(r"^([A-Z]{2,4} \d{3}[A-Z]?)\s+(.*)$", body)
    if cm:
        return {"code": cm.group(1), "title": cm.group(2).strip() or None,
                "credits": credits, "raw": s}
    # a category / choice row (e.g. "Free Elective", "History and Humanities GER 200 level")
    return {"code": None, "title": body or None, "credits": credits, "raw": s}


if __name__ == "__main__":
    import json
    import pdfplumber

    pdf = pdfplumber.open("../../2024-2025 Undergraduate.pdf")
    entries = parse_toc(pdf)
    colleges, departments, programs = build_hierarchy(entries)
    print(f"colleges={len(colleges)} departments={len(departments)} programs={len(programs)}")
    for c in colleges:
        print("  COLLEGE", c["printedPage"], c["name"])
    pages = json.load(open("../data/pages.json"))["pages"]
    order = sorted(programs, key=lambda p: p["printedPage"])
    # find CS program
    for i, p in enumerate(order):
        if p["name"] == "B.S. in Computer Science":
            nxt = order[i + 1]["printedPage"] if i + 1 < len(order) else None
            prev = order[i - 1]["printedPage"] if i > 0 else None
            full = parse_program_body(p, pages, prev, nxt)
            print("\n=== B.S. in Computer Science ===")
            print("college:", full["collegeId"], "dept:", full["departmentId"])
            print("statedTotalCredits:", full["statedTotalCredits"], " summed:", full["totalCredits"])
            print("groups:", len(full["requirementGroups"]), " courseCodes:", len(full["courseCodes"]))
            print("sample groups:")
            for g in full["requirementGroups"][:3]:
                print(f"  [{g['name']}] credits={g['credits']} items={len(g['items'])}")
                for it in g["items"][:4]:
                    print("     -", it["code"], "|", it["title"], "|", it["credits"])
            print("sample codes:", full["courseCodes"][:15])
            break
