"""Parse a natural-language prerequisite string into a boolean AST + dependency edges.

The NJIT catalog states prerequisites as boolean expressions over course codes, e.g.:

    "AD 161"
    "ARCH 381 or AD 162"
    "AD 150 or ARCH 396 or permission of instructor"
    "(DD 364 or ID 364 or INT 364 or ARCH 364) and PHYS 102"
    "(ARCH 196 and ARCH 110 and ARCH 156) or (ARCH 161 and ARCH 164 and ARCH 156)"
    "CS 114 with a grade of C or better"

Grammar / precedence
--------------------
    expr   := or_expr
    or_expr  := and_expr ( "or"  and_expr )*
    and_expr := atom    ( "and" atom    )*
    atom   := "(" expr ")" | COURSE [grade] | OTHER

We adopt the standard convention that AND binds tighter than OR (so
"A or B and C" == "A or (B and C)"); explicit parentheses in the catalog override
this. Non-course phrases (e.g. "permission of instructor", "senior standing",
GER-category names) become OTHER nodes: they are preserved on the course record but
are NOT turned into dependency edges.

AST node shapes (plain dicts, JSON-serialisable):
    {"op": "and"|"or", "children": [ ... ]}
    {"type": "course", "code": "CS 113", "minGrade": "C" | None}
    {"type": "other", "text": "permission of instructor"}
"""
import re

COURSE_RE = re.compile(r"\b([A-Z]{2,4})\s*([0-9]{3}[A-Z]?)\b")
GRADE_RE = re.compile(
    r"^\s*(?:with\s+)?(?:a\s+)?(?:minimum\s+)?grade\s+(?:of\s+)?([A-D][+-]?)(?:\s+or\s+(?:better|higher))?",
    re.I,
)
# "a grade of C or better in CS 280" -> normalise to "CS 280 with a grade of C or better"
GRADE_IN_RE = re.compile(
    r"(?:a\s+)?(?:minimum\s+)?grade\s+(?:of\s+)?([A-D][+-]?)(?:\s+or\s+(?:better|higher))?\s+in\s+"
    r"([A-Z]{2,4}\s*[0-9]{3}[A-Z]?)",
    re.I,
)


def normalize_code(subject, number):
    return f"{subject.upper()} {number.upper()}"


def _pre_normalize(s):
    """Rewrite 'grade of X or better in COURSE' to 'COURSE with a grade of X or better'."""
    return GRADE_IN_RE.sub(lambda m: f"{m.group(2)} with a grade of {m.group(1)} or better", s)


def tokenize(s):
    """Return a list of tokens: ('LP',) ('RP',) ('AND',) ('OR',)
    ('COURSE', code, minGrade) ('OTHER', text)."""
    s = _pre_normalize(s)
    tokens = []
    i = 0
    n = len(s)
    other_buf = []

    def flush_other():
        if other_buf:
            text = " ".join(other_buf).strip(" ,.;")
            text = re.sub(r"\s+", " ", text)
            if text:
                tokens.append(("OTHER", text))
            other_buf.clear()

    while i < n:
        c = s[i]
        if c.isspace() or c == ",":
            i += 1
            continue
        if c == "(":
            flush_other()
            tokens.append(("LP",))
            i += 1
            continue
        if c == ")":
            flush_other()
            tokens.append(("RP",))
            i += 1
            continue
        # connector words (whole-word)
        m = re.match(r"(and|or)\b", s[i:], re.I)
        if m and not other_buf_would_continue(s, i):
            flush_other()
            tokens.append((m.group(1).upper(),))
            i += m.end()
            continue
        # course code
        m = COURSE_RE.match(s, i)
        if m:
            flush_other()
            code = normalize_code(m.group(1), m.group(2))
            j = m.end()
            grade = None
            gm = GRADE_RE.match(s[j:])
            if gm:
                grade = gm.group(1).upper()
                j += gm.end()
            tokens.append(("COURSE", code, grade))
            i = j
            continue
        # otherwise consume a word into the OTHER buffer
        m = re.match(r"\S+", s[i:])
        word = m.group(0)
        other_buf.append(word)
        i += m.end()
    flush_other()
    return tokens


def other_buf_would_continue(s, i):
    """Heuristic: treat 'and'/'or' as a connector unless it is clearly embedded in a
    free-text phrase with no nearby course code. We keep it simple: always treat
    standalone and/or as connectors. (Kept as a hook for future tuning.)"""
    return False


class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def next(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def parse(self):
        if not self.toks:
            return None
        node = self.parse_or()
        return node

    def parse_or(self):
        children = [self.parse_and()]
        while self.peek() and self.peek()[0] == "OR":
            self.next()
            children.append(self.parse_and())
        children = [c for c in children if c is not None]
        if len(children) == 1:
            return children[0]
        return {"op": "or", "children": children}

    ATOM_STARTERS = ("LP", "COURSE", "OTHER")

    def parse_and(self):
        children = [self.parse_atom()]
        while self.peek():
            kind = self.peek()[0]
            if kind == "AND":
                self.next()
                children.append(self.parse_atom())
            elif kind in self.ATOM_STARTERS:
                # adjacency (e.g. comma-separated list) is an implicit AND
                children.append(self.parse_atom())
            else:
                break
        children = [c for c in children if c is not None]
        if not children:
            return None
        if len(children) == 1:
            return children[0]
        return {"op": "and", "children": children}

    def parse_atom(self):
        t = self.peek()
        if t is None:
            return None
        if t[0] == "LP":
            self.next()
            node = self.parse_or()
            if self.peek() and self.peek()[0] == "RP":
                self.next()
            return node
        if t[0] == "RP":
            return None
        if t[0] == "COURSE":
            self.next()
            node = {"type": "course", "code": t[1]}
            node["minGrade"] = t[2]
            return node
        if t[0] == "OTHER":
            self.next()
            return {"type": "other", "text": t[1]}
        # stray connector — skip
        self.next()
        return None


def parse_prerequisite(raw):
    """Parse a raw prerequisite string. Returns (ast, courses) where courses is a list
    of {"code","minGrade"} dicts for every course referenced (dedup, order-preserving)."""
    if not raw or not raw.strip():
        return None, []
    ast = _Parser(tokenize(raw)).parse()
    courses = []
    seen = set()

    def walk(node):
        if node is None:
            return
        if "op" in node:
            for ch in node["children"]:
                walk(ch)
        elif node.get("type") == "course":
            key = (node["code"], node.get("minGrade"))
            if key not in seen:
                seen.add(key)
                courses.append({"code": node["code"], "minGrade": node.get("minGrade")})

    walk(ast)
    return ast, courses


def edges_for(course_code, raw):
    """Return dependency edges [{"from","to","minGrade"}] from `course_code` to each
    prerequisite course referenced in `raw`."""
    _, courses = parse_prerequisite(raw)
    return [
        {"from": course_code, "to": c["code"], "minGrade": c["minGrade"]}
        for c in courses
    ]


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    samples = [
        "AD 161",
        "ARCH 381 or AD 162",
        "AD 150 or ARCH 396 or permission of instructor",
        "(DD 364 or ID 364 or INT 364 or ARCH 364) and PHYS 102",
        "ARCH 210 or ARCH 251 and ARCH 252",
        "(ARCH 196 and ARCH 110 and ARCH 156) or (ARCH 161 and ARCH 164 and ARCH 156)",
        "CS 114 with a grade of C or better",
        "a grade of C or better in CS 280 and MATH 226",
        "Computing Literacy GER course, AD 150, AD 112",
    ]
    ok = True
    for s in samples:
        ast, courses = parse_prerequisite(s)
        print("\nRAW:", s)
        print("AST:", json.dumps(ast))
        print("COURSES:", [c["code"] + (f"({c['minGrade']})" if c["minGrade"] else "") for c in courses])

    # assertions
    ast, courses = parse_prerequisite("(DD 364 or ID 364 or INT 364 or ARCH 364) and PHYS 102")
    codes = {c["code"] for c in courses}
    assert codes == {"DD 364", "ID 364", "INT 364", "ARCH 364", "PHYS 102"}, codes
    assert ast["op"] == "and", ast

    ast, courses = parse_prerequisite("ARCH 210 or ARCH 251 and ARCH 252")
    assert ast["op"] == "or", ast
    # second branch is an AND of 251 & 252
    assert any(ch.get("op") == "and" for ch in ast["children"]), ast

    ast, courses = parse_prerequisite("CS 114 with a grade of C or better")
    assert courses == [{"code": "CS 114", "minGrade": "C"}], courses

    ast, courses = parse_prerequisite("a grade of C or better in CS 280 and MATH 226")
    codes = {c["code"] for c in courses}
    assert codes == {"CS 280", "MATH 226"}, codes
    assert any(c["minGrade"] == "C" for c in courses), courses

    ast, courses = parse_prerequisite("Computing Literacy GER course, AD 150, AD 112")
    codes = {c["code"] for c in courses}
    assert codes == {"AD 150", "AD 112"}, codes  # comma-separated implicit AND

    print("\nAll prereq_parser self-tests passed.")
