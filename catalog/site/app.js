/* NJIT Catalog Ontology dashboard — vanilla JS, no dependencies.
   Loads the generated JSON (ontology, metrics, evaluations) and renders the overview
   and per-program pages, including a self-contained layered SVG prerequisite graph. */
"use strict";

const PARAMS = new URLSearchParams(location.search);
const LEVEL = PARAMS.get("level") === "graduate" ? "graduate" : "undergraduate";
const DATA = `../data/${LEVEL}`;
let O, M, E, COURSES;

async function loadData() {
  const [o, m, e] = await Promise.all([
    fetch(`${DATA}/ontology.json`).then((r) => r.json()),
    fetch(`${DATA}/metrics.json`).then((r) => r.json()),
    fetch(`${DATA}/evaluations.json`).then((r) => r.json()).catch(() => ({ programs: {} })),
  ]);
  O = o; M = m; E = e;
  COURSES = new Map(O.courses.map((c) => [c.code, c]));
}

// Wire the Undergraduate / Graduate switch (links preserve the current page).
function markLevelNav(page) {
  document.querySelectorAll(".levelnav a").forEach((a) => {
    const lv = a.dataset.level;
    a.href = page === "program" ? `index.html?level=${lv}` : `index.html?level=${lv}`;
    a.classList.toggle("active", lv === LEVEL);
  });
}
const levelParam = () => `level=${LEVEL}`;

const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));
const scoreClass = (n) => (n == null ? "" : "s" + Math.max(1, Math.min(5, Math.round(n))));
const collegeName = (id) => (O.colleges.find((c) => c.id === id) || {}).name || "—";
const deptName = (id) => (O.departments.find((d) => d.id === id) || {}).name || null;

/* ---------------- Overview page ---------------- */
function renderOverview() {
  const c = O.meta.counts;
  const s = M.summary;
  document.getElementById("stats").innerHTML = [
    ["Colleges", c.colleges], ["Departments", c.departments], ["Programs", c.programs],
    ["Courses", c.courses], ["Prereq edges", c.prerequisiteEdges], ["Subjects", c.subjects],
  ].map(([k, v]) => `<article><span>${k}</span><strong>${v}</strong></article>`).join("");

  document.getElementById("quality").innerHTML = [
    ["Prerequisite cycles", s.prerequisiteCycles, s.prerequisiteCycles ? "bad" : "ok"],
    ["Max prereq depth", s.maxPrereqDepth, "ok"],
    ["Dangling prereq refs", s.danglingPrereqReferences, s.danglingPrereqReferences ? "warn" : "ok"],
    ["Courses missing description", s.coursesMissingDescription, s.coursesMissingDescription ? "warn" : "ok"],
    ["Courses with thin description", s.coursesThinDescription, "warn"],
    ["Programs w/ credit mismatch", s.programsCreditMismatch, s.programsCreditMismatch ? "warn" : "ok"],
  ].map(([k, v, t]) => `<div class="flag"><span class="dot ${t}"></span><div><b>${v}</b>${k}</div></div>`).join("");

  // college filter
  const sel = document.getElementById("f-college");
  sel.innerHTML = `<option value="">All colleges</option>` +
    O.colleges.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  ["f-college", "f-kind", "f-q"].forEach((id) =>
    document.getElementById(id).addEventListener("input", renderProgramGrid));
  renderProgramGrid();
}

function programScore(pid) {
  const ev = E.programs[pid];
  return ev && ev.overallScore != null ? ev.overallScore : null;
}

function renderProgramGrid() {
  const col = document.getElementById("f-college").value;
  const kind = document.getElementById("f-kind").value;
  const q = document.getElementById("f-q").value.trim().toLowerCase();
  let progs = O.programs.filter((p) =>
    (!col || p.collegeId === col) && (!kind || p.kind === kind) &&
    (!q || p.name.toLowerCase().includes(q)));
  progs.sort((a, b) => (programScore(b.id) ?? -1) - (programScore(a.id) ?? -1) || a.name.localeCompare(b.name));
  document.getElementById("count").textContent = `${progs.length} programs`;
  document.getElementById("grid").innerHTML = progs.map((p) => {
    const sc = programScore(p.id);
    const pm = M.programs[p.id] || {};
    const scoreHtml = sc != null
      ? `<span class="score ${scoreClass(sc)}"><span class="n">${sc.toFixed(1)}</span><span class="d">/5</span></span>`
      : `<span class="unscored">not yet evaluated</span>`;
    return `<a class="card" href="program.html?${levelParam()}&id=${encodeURIComponent(p.id)}">
      <span class="deg">${esc(p.degree || p.kind)}</span>
      <h3>${esc(p.name)}</h3>
      <div class="meta">${esc(collegeName(p.collegeId))}${p.statedTotalCredits ? " · " + p.statedTotalCredits + " cr" : ""}</div>
      <div class="cardfoot">${scoreHtml}<span class="unscored">${pm.referencedCourses || 0} courses</span></div>
    </a>`;
  }).join("") || `<p class="unscored">No programs match.</p>`;
}

/* ---------------- Program page ---------------- */
function renderProgram() {
  const id = new URLSearchParams(location.search).get("id");
  const p = O.programs.find((x) => x.id === id);
  const host = document.getElementById("prog");
  if (!p) { host.innerHTML = `<p>Program not found.</p>`; return; }
  const pm = M.programs[id] || {};
  const ev = E.programs[id];
  document.title = `${p.name} · NJIT Catalog Ontology`;

  const head = document.getElementById("head");
  head.innerHTML = `
    <p class="crumbs"><a href="index.html?${levelParam()}">${O.meta.level === "graduate" ? "Graduate" : "Undergraduate"} catalog</a> › ${esc(collegeName(p.collegeId))}</p>
    <p class="kicker">${esc(p.degree || p.kind)}${deptName(p.departmentId) ? " · " + esc(deptName(p.departmentId)) : ""}</p>
    <h1>${esc(p.name)}</h1>
    <div class="tagrow">
      ${p.statedTotalCredits ? `<span class="pill">${p.statedTotalCredits} credits</span>` : `<span class="pill">credits: n/a</span>`}
      <span class="pill">${pm.referencedCourses || 0} courses referenced</span>
      <span class="pill">deepest prereq chain: ${pm.deepestPrereqChain ?? "—"}</span>
      ${ev ? `<span class="pill ${scoreClass(ev.overallScore)}">quality ${ev.overallScore?.toFixed?.(1) ?? ev.overallScore}/5</span>` : ""}
    </div>`;

  let left = "";
  // scorecard
  if (ev) {
    left += `<div class="panel"><h2>Quality scorecard</h2>
      <p class="sub">Rubric + AI-assisted, grounded in deterministic catalog metrics.</p>`;
    ev.dimensions.forEach((d) => {
      const cls = scoreClass(d.score);
      left += `<div class="dim">
        <div class="row"><b>${esc(d.name)}</b><span class="score ${cls}"><span class="n">${d.score}</span><span class="d">/5</span></span></div>
        <div class="bar"><i class="fill${Math.round(d.score)}" style="width:${(d.score / 5) * 100}%"></i></div>
        <p>${esc(d.justification)}</p>
        ${d.suggestion ? `<div class="sugg">→ ${esc(d.suggestion)}</div>` : ""}
      </div>`;
    });
    if (ev.courseLevel) {
      left += `<div class="dim"><div class="row"><b>Course descriptions</b><span class="score ${scoreClass(ev.courseLevel.descriptionQuality.score)}"><span class="n">${ev.courseLevel.descriptionQuality.score}</span><span class="d">/5</span></span></div><p>${esc(ev.courseLevel.descriptionQuality.justification)}</p></div>`;
      left += `<div class="dim"><div class="row"><b>Prerequisite clarity</b><span class="score ${scoreClass(ev.courseLevel.prerequisiteClarity.score)}"><span class="n">${ev.courseLevel.prerequisiteClarity.score}</span><span class="d">/5</span></span></div><p>${esc(ev.courseLevel.prerequisiteClarity.justification)}</p></div>`;
    }
    left += `</div>`;
  } else {
    left += `<div class="panel"><h2>Quality scorecard</h2><p class="sub">This program is part of the catalog ontology but has not yet been through the AI rubric pass (pilot covers Ying Wu College of Computing degrees). Deterministic metrics are shown at right.</p></div>`;
  }

  // requirement groups
  if (p.requirementGroups && p.requirementGroups.length) {
    left += `<div class="panel"><h2>Plan of study</h2><p class="sub">Parsed from the catalog plan-of-study grid.</p>`;
    p.requirementGroups.forEach((g) => {
      left += `<div class="term"><header><span>${esc(g.name)}</span><span>${g.credits != null ? g.credits + " cr" : ""}</span></header><table>` +
        g.items.map((it) => `<tr><td class="code">${esc(it.code || "")}</td><td>${esc(it.title || it.raw || "")}</td><td class="cr">${it.credits != null ? it.credits : ""}</td></tr>`).join("") +
        `</table></div>`;
    });
    left += `</div>`;
  }

  // right column: flags, suggestions, graph
  let right = "";
  right += `<div class="panel"><h2>Deterministic flags</h2><div class="flags">` +
    flag(pm.creditReconcileDelta === 0, `Credit total reconciles (${pm.summedTermCredits ?? "?"} = ${pm.statedTotalCredits ?? "?"})`,
      pm.creditReconcileDelta == null ? "warn" : "bad",
      pm.creditReconcileDelta == null ? `Credit total not cleanly parsed` : `Credit mismatch: summed ${pm.summedTermCredits} vs stated ${pm.statedTotalCredits} (Δ${pm.creditReconcileDelta})`) +
    flag((pm.missingCourseCount || 0) === 0, `No dangling course references`, "warn",
      `${pm.missingCourseCount} referenced course(s) not found in the undergraduate catalog${pm.missingCourses && pm.missingCourses.length ? ": " + pm.missingCourses.slice(0, 6).join(", ") : ""}`) +
    flag(!!(ev && ev.dimensions.find((d) => d.key === "learning_outcomes" && d.score >= 3)),
      `Learning outcomes present`, "warn", `No explicit program learning outcomes found on the catalog page`) +
    flag((pm.deepestPrereqChain || 0) <= 8, `Prerequisite depth reasonable (${pm.deepestPrereqChain ?? 0})`, "warn", `Deep prerequisite chain (${pm.deepestPrereqChain}) may constrain scheduling`) +
    `</div></div>`;

  if (ev && ev.topSuggestions && ev.topSuggestions.length) {
    right += `<div class="panel"><h2>Top suggestions</h2><ol class="sugg-list">` +
      ev.topSuggestions.map((s) => `<li>${esc(s)}</li>`).join("") + `</ol></div>`;
  }

  const fa = ev && ev.fieldAnalysis;
  if (fa && ((fa.missingTopics && fa.missingTopics.length) || (fa.emergingTrends && fa.emergingTrends.length))) {
    right += `<div class="panel"><h2>Field gaps &amp; trends</h2>
      <p class="sub">Topics the discipline expects but this program underweights, and emerging directions it should position for.</p>`;
    if (fa.missingTopics && fa.missingTopics.length) {
      right += `<h3 class="fa-h gap">Missing / underweighted topics</h3><ul class="fa-list">` +
        fa.missingTopics.map((x) => `<li><b>${esc(x.topic || x.name)}</b><span>${esc(x.rationale || x.why || "")}</span></li>`).join("") + `</ul>`;
    }
    if (fa.emergingTrends && fa.emergingTrends.length) {
      right += `<h3 class="fa-h trend">Emerging trends to position for</h3><ul class="fa-list">` +
        fa.emergingTrends.map((x) => `<li><b>${esc(x.trend || x.name)}</b><span>${esc(x.rationale || x.why || "")}</span></li>`).join("") + `</ul>`;
    }
    right += `</div>`;
  }

  right += `<div class="panel"><h2>Prerequisite dependency graph</h2>
    <p class="sub">Courses referenced by this program; arrows point from a prerequisite to the course that requires it.</p>
    <div class="graph-wrap" id="graph"></div>
    <div class="legend"><span><i style="border-color:rgba(120,140,170,.7)"></i> prerequisite → course</span>
      <span><i style="border-color:var(--accent)"></i> ${esc(dominantSubject(p))} core</span>
      <span>hover a course to trace its chain</span></div></div>`;

  host.innerHTML = `<div class="two-col"><div>${left}</div><div>${right}</div></div>`;
  buildGraph(document.getElementById("graph"), p);
}

function flag(ok, okText, badLevel, badText) {
  return `<div class="flag"><span class="dot ${ok ? "ok" : badLevel}"></span><div><b>${ok ? okText : badText}</b></div></div>`;
}

function dominantSubject(p) {
  const cnt = {};
  (p.courseCodes || []).forEach((c) => { const s = c.split(" ")[0]; cnt[s] = (cnt[s] || 0) + 1; });
  return Object.entries(cnt).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
}

/* ---------------- Dependency graph (layered SVG DAG) ---------------- */
function buildGraph(container, program) {
  const codes = (program.courseCodes || []).filter((c) => COURSES.has(c));
  const nodeSet = new Set(codes);
  const core = dominantSubject(program);
  // intra-program prerequisite edges
  const edges = O.prerequisiteEdges.filter(
    (e) => e.kind === "prerequisite" && nodeSet.has(e.from) && nodeSet.has(e.to));
  if (!codes.length) { container.innerHTML = `<p class="unscored" style="padding:18px">No catalog courses resolved for this program.</p>`; return; }

  const prereqOf = new Map(codes.map((c) => [c, []])); // course -> its prereqs
  edges.forEach((e) => prereqOf.get(e.from).push(e.to));

  // longest-path layering
  const layer = new Map();
  const visiting = new Set();
  function lay(c) {
    if (layer.has(c)) return layer.get(c);
    visiting.add(c);
    let L = 0;
    for (const p of prereqOf.get(c) || []) {
      if (visiting.has(p)) continue;
      L = Math.max(L, lay(p) + 1);
    }
    visiting.delete(c);
    layer.set(c, L);
    return L;
  }
  codes.forEach(lay);

  const cols = {};
  codes.forEach((c) => { const L = layer.get(c); (cols[L] = cols[L] || []).push(c); });
  Object.values(cols).forEach((arr) => arr.sort());
  const maxL = Math.max(...Object.keys(cols).map(Number));
  const COLW = 168, ROWH = 46, NW = 128, NH = 32, PAD = 24;
  const height = Math.max(...Object.values(cols).map((a) => a.length)) * ROWH + PAD * 2;
  const width = (maxL + 1) * COLW + PAD * 2;

  const pos = new Map();
  for (let L = 0; L <= maxL; L++) {
    const arr = cols[L] || [];
    const colH = arr.length * ROWH;
    const y0 = PAD + (height - PAD * 2 - colH) / 2;
    arr.forEach((c, i) => pos.set(c, { x: PAD + L * COLW, y: y0 + i * ROWH + ROWH / 2 }));
  }

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "depgraph");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  // edges (curved)
  const edgeEls = [];
  edges.forEach((e) => {
    const a = pos.get(e.to), b = pos.get(e.from); // a=prereq (source), b=course (target)
    if (!a || !b) return;
    const x1 = a.x + NW / 2, y1 = a.y, x2 = b.x - NW / 2, y2 = b.y;
    const mx = (x1 + x2) / 2;
    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
    path.setAttribute("class", "edge");
    path.dataset.from = e.from; path.dataset.to = e.to;
    svg.appendChild(path);
    edgeEls.push(path);
  });

  // nodes
  codes.forEach((c) => {
    const p = pos.get(c);
    const course = COURSES.get(c);
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute("class", "node" + (c.startsWith(core + " ") ? " core" : ""));
    g.setAttribute("transform", `translate(${p.x - NW / 2},${p.y - NH / 2})`);
    g.dataset.code = c;
    const rect = document.createElementNS(svgNS, "rect");
    rect.setAttribute("width", NW); rect.setAttribute("height", NH);
    const t1 = document.createElementNS(svgNS, "text");
    t1.setAttribute("x", 8); t1.setAttribute("y", 14); t1.textContent = c;
    const t2 = document.createElementNS(svgNS, "text");
    t2.setAttribute("x", 8); t2.setAttribute("y", 26); t2.setAttribute("class", "t");
    t2.textContent = (course.title || "").slice(0, 20);
    g.append(rect, t1, t2);
    const title = document.createElementNS(svgNS, "title");
    title.textContent = `${c} — ${course.title || ""}${course.prerequisiteRaw ? "\nPrereq: " + course.prerequisiteRaw : ""}`;
    g.appendChild(title);
    g.addEventListener("mouseenter", () => highlight(c));
    g.addEventListener("mouseleave", clearHl);
    svg.appendChild(g);
  });

  function highlight(code) {
    const keep = new Set([code]);
    edgeEls.forEach((p) => {
      if (p.dataset.from === code || p.dataset.to === code) {
        p.classList.add("hl"); keep.add(p.dataset.from); keep.add(p.dataset.to);
      }
    });
    svg.querySelectorAll(".node").forEach((n) => { if (keep.has(n.dataset.code)) n.classList.add("hl"); });
  }
  function clearHl() {
    edgeEls.forEach((p) => p.classList.remove("hl"));
    svg.querySelectorAll(".node.hl").forEach((n) => n.classList.remove("hl"));
  }

  container.innerHTML = "";
  if (!edges.length) {
    const note = document.createElement("p");
    note.className = "unscored";
    note.style.padding = "0 16px 8px";
    note.textContent = "No prerequisite links among this program's courses lie within the parsed set (electives/GER are unlinked).";
    container.appendChild(note);
  }
  container.appendChild(svg);
}

/* ---------------- boot ---------------- */
async function boot(page) {
  markLevelNav(page);
  try {
    await loadData();
    if (page === "overview") renderOverview();
    else renderProgram();
    if (page === "program") {
      const bl = document.querySelector(".backlink");
      if (bl) bl.setAttribute("href", `index.html?${levelParam()}`);
    }
  } catch (err) {
    document.body.insertAdjacentHTML("beforeend",
      `<div class="wrap"><p style="color:var(--bad)">Failed to load catalog data: ${esc(err.message)}.<br>Serve this folder over HTTP (e.g. <code>python -m http.server</code>) — file:// blocks fetch.</p></div>`);
    console.error(err);
  }
}
