"""Stage 3: deterministic quality signals over the ontology.

These are objective, computable checks that (a) surface data-quality / catalog issues on
their own and (b) become evidence for the AI rubric evaluation. Output: metrics.json.

Course-level:   in/out prerequisite degree, prerequisite-chain depth, dangling prereqs,
                missing credits, missing / very short description.
Program-level:  referenced-course count, missing (dangling) referenced courses,
                deepest prerequisite chain touched, credit reconciliation (stated vs summed).
Graph-level:    prerequisite cycles (expected: none), depth distribution, orphan courses.
"""
import json
import os
import sys

import config

SHORT_DESC = 120  # chars; below this a description is "thin"


def compute(ontology):
    courses = {c["code"]: c for c in ontology["courses"]}
    pre_edges = [e for e in ontology["prerequisiteEdges"] if e["kind"] == "prerequisite"]

    # adjacency: course -> list of prerequisite courses (that exist in the catalog)
    prereqs = {code: [] for code in courses}
    in_deg = {code: 0 for code in courses}
    dangling = {code: [] for code in courses}
    for e in pre_edges:
        frm, to = e["from"], e["to"]
        if frm not in courses:
            continue
        if to in courses:
            prereqs[frm].append(to)
            in_deg[to] += 1
        else:
            dangling[frm].append(to)

    # depth via memoised DFS with cycle detection
    depth = {}
    cycles = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {c: WHITE for c in courses}

    def dfs(u, stack):
        color[u] = GRAY
        best = 0
        for v in prereqs[u]:
            if color[v] == GRAY:
                # back-edge -> cycle
                if u != v:
                    cycles.append(stack[stack.index(v):] + [u] if v in stack else [u, v])
                continue
            if color[v] == WHITE:
                dfs(v, stack + [v])
            best = max(best, depth.get(v, 0) + 1)
        depth[u] = best
        color[u] = BLACK

    import sys
    sys.setrecursionlimit(10000)
    for c in courses:
        if color[c] == WHITE:
            dfs(c, [c])

    course_metrics = {}
    for code, c in courses.items():
        out_d = len(prereqs[code])
        desc = c.get("description") or ""
        course_metrics[code] = {
            "inDegree": in_deg[code],
            "outDegree": out_d,
            "depth": depth.get(code, 0),
            "danglingPrereqs": sorted(set(dangling[code])),
            "missingCredits": c.get("credits") in (None, 0),
            "missingDescription": not desc,
            "thinDescription": bool(desc) and len(desc) < SHORT_DESC,
        }

    orphans = [code for code in courses
               if in_deg[code] == 0 and len(prereqs[code]) == 0]

    # program-level
    program_metrics = {}
    for p in ontology["programs"]:
        refs = p.get("courseCodes", []) or []
        missing = [c for c in refs if c not in courses]
        present = [c for c in refs if c in courses]
        max_depth = max((depth.get(c, 0) for c in present), default=0)
        stated = p.get("statedTotalCredits")
        summed = p.get("totalCredits")
        reconcile = None
        if stated is not None and summed is not None:
            reconcile = round(summed - stated, 1)
        program_metrics[p["id"]] = {
            "referencedCourses": len(refs),
            "missingCourses": missing,
            "missingCourseCount": len(missing),
            "deepestPrereqChain": max_depth,
            "requirementGroups": len(p.get("requirementGroups", []) or []),
            "statedTotalCredits": stated,
            "summedTermCredits": summed,
            "creditReconcileDelta": reconcile,
            "hasDescription": bool(p.get("description")),
        }

    total_dangling = sum(len(v["danglingPrereqs"]) for v in course_metrics.values())
    depth_hist = {}
    for m in course_metrics.values():
        depth_hist[m["depth"]] = depth_hist.get(m["depth"], 0) + 1

    summary = {
        "courses": len(courses),
        "coursesWithPrereqs": sum(1 for m in course_metrics.values() if m["outDegree"] > 0),
        "prerequisiteEdges": len(pre_edges),
        "danglingPrereqReferences": total_dangling,
        "coursesWithDanglingPrereqs": sum(1 for m in course_metrics.values() if m["danglingPrereqs"]),
        "prerequisiteCycles": len(cycles),
        "maxPrereqDepth": max((m["depth"] for m in course_metrics.values()), default=0),
        "depthHistogram": {str(k): depth_hist[k] for k in sorted(depth_hist)},
        "orphanCourses": len(orphans),
        "coursesMissingCredits": sum(1 for m in course_metrics.values() if m["missingCredits"]),
        "coursesMissingDescription": sum(1 for m in course_metrics.values() if m["missingDescription"]),
        "coursesThinDescription": sum(1 for m in course_metrics.values() if m["thinDescription"]),
        "programs": len(program_metrics),
        "programsCreditMismatch": sum(1 for m in program_metrics.values()
                                      if m["creditReconcileDelta"] not in (None, 0)),
    }

    return {
        "summary": summary,
        "cycles": cycles[:50],
        "courses": course_metrics,
        "programs": program_metrics,
    }


def main(level="undergraduate"):
    cfg = config.resolve(level)
    ontology = json.load(open(cfg["ontology"]))
    metrics = compute(ontology)
    with open(cfg["metrics"], "w") as f:
        json.dump(metrics, f, separators=(",", ":"))
    print(f"[{level}] Wrote {cfg['metrics']}")
    print(json.dumps(metrics["summary"], indent=2))


if __name__ == "__main__":
    main(config.level_from_argv(sys.argv))
