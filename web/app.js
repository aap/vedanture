"use strict";
const $  = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Resolve the API relative to where app.js is served, so the app works under
// any mount path (e.g. nginx proxying /vedanture/ → the server), not only the
// site root. Pair with `location /vedanture/ { proxy_pass http://127.0.0.1:PORT/; }`.
const API = new URL("api", document.currentScript.src).href;
let sheets = [];        // [{id, loc, history, future, doc, el}]
let activeId = null;
let lastActiveId = null;  // the sheet active before the current one
let uid = 0;

// ── data ──────────────────────────────────────────────────────────────────────
async function fetchSheet(loc) {
  const r = await fetch(`${API}/sheet?loc=${encodeURIComponent(JSON.stringify(loc))}`);
  return r.json();
}

async function invGet() {
  return (await fetch(`${API}/inventory`)).json();
}
async function invSet(op, name, loc) {
  return (await fetch(`${API}/inventory`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ op, name, loc }),
  })).json();
}

// ── sheet lifecycle ─────────────────────────────────────────────────────────
function openSheet(loc, afterId = null) {
  const sheet = { id: ++uid, loc, history: [], future: [], doc: null, el: null };
  const idx = afterId == null ? sheets.length
                              : sheets.findIndex(s => s.id === afterId) + 1;
  sheets.splice(idx, 0, sheet);
  renderStack();
  setActive(sheet.id);
  loadSheet(sheet).then(scrollToActive);
  return sheet;
}

async function loadSheet(sheet) {
  sheet.doc = await fetchSheet(sheet.loc);
  renderSheet(sheet);
  if (sheet.content) sheet.content.scrollTop = 0;
}

function navigate(sheet, loc) {
  if (sheet.loc) sheet.history.push(sheet.loc);
  sheet.future = [];
  sheet.loc = loc;
  loadSheet(sheet);
}
function back(sheet) {
  if (!sheet.history.length) return;
  sheet.future.push(sheet.loc);
  sheet.loc = sheet.history.pop();
  loadSheet(sheet);
}
function forward(sheet) {
  if (!sheet.future.length) return;
  sheet.history.push(sheet.loc);
  sheet.loc = sheet.future.pop();
  loadSheet(sheet);
}
function duplicate(sheet) {
  const ns = { id: ++uid, loc: sheet.loc, history: [...sheet.history],
               future: [...sheet.future], doc: sheet.doc, el: null,
               width: sheet.width };
  const idx = sheets.findIndex(s => s.id === sheet.id) + 1;
  sheets.splice(idx, 0, ns);
  renderStack();
  setActive(ns.id);
  scrollToActive();
}
function closeSheet(sheet) {
  sheets = sheets.filter(s => s.id !== sheet.id);
  if (activeId === sheet.id)
    activeId = sheets.length ? sheets[sheets.length - 1].id : null;
  if (lastActiveId === sheet.id) lastActiveId = null;
  renderStack();
}

function lastActiveSheet() {
  return sheets.find(s => s.id === lastActiveId);
}

// Attach navigation to an element for both left- and middle-click (auxclick),
// and suppress the middle-button autoscroll on mousedown.
function bindLink(el, sheet, loc) {
  const go = e => linkClick(e, sheet, loc);
  el.addEventListener("click", go);
  el.addEventListener("auxclick", go);
  el.addEventListener("mousedown", e => { if (e.button === 1) e.preventDefault(); });
}

function linkClick(e, sheet, loc) {
  if (!loc || e.button === 2) return;
  e.preventDefault();
  if (e.button === 1) {                       // middle-click → last-active sheet
    const target = lastActiveSheet();
    if (target && target.id !== sheet.id) {
      navigate(target, loc);
      if (target.el) target.el.scrollIntoView({ inline: "nearest", block: "nearest" });
    } else {
      openSheet(loc, sheet.id);                // no other sheet → spawn one
    }
    return;
  }
  if (e.shiftKey || e.metaKey || e.ctrlKey)   // modified → new sheet
    openSheet(loc, sheet.id);
  else
    navigate(sheet, loc);                      // plain → in place
}

// ── stack rendering ─────────────────────────────────────────────────────────
function renderStack() {
  const stack = $("#stack");
  stack.innerHTML = "";
  for (const sheet of sheets) {
    const el = document.createElement("section");
    el.className = "sheet" + (sheet.id === activeId ? " active" : "");
    el.dataset.id = sheet.id;
    if (sheet.width) el.style.width = sheet.width + "px";
    el.addEventListener("mousedown", () => setActive(sheet.id));

    const content = document.createElement("div");
    content.className = "sheet-content";
    el.appendChild(content);

    const grip = document.createElement("div");
    grip.className = "sheet-resize";
    grip.title = "drag to resize";
    attachResize(grip, sheet, el);
    el.appendChild(grip);

    sheet.el = el;
    sheet.content = content;
    stack.appendChild(el);
    if (sheet.doc) renderSheet(sheet);
    else content.innerHTML = '<div class="loading">…</div>';
  }
}

function attachResize(grip, sheet, el) {
  grip.addEventListener("mousedown", e => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startW = el.getBoundingClientRect().width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    const move = ev => {
      const w = Math.max(240, startW + (ev.clientX - startX));
      el.style.width = w + "px";
      sheet.width = w;
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
}

function setActive(id) {
  if (id !== activeId) { lastActiveId = activeId; activeId = id; }
  $$(".sheet").forEach(el => el.classList.toggle("active", +el.dataset.id === id));
}
function scrollToActive() {
  const el = sheets.find(s => s.id === activeId)?.el;
  if (el) el.scrollIntoView({ inline: "end", block: "nearest" });
}

function iconBtn(sym, title, fn, disabled) {
  const b = document.createElement("button");
  b.className = "ibtn"; b.textContent = sym; b.title = title;
  if (disabled) b.disabled = true;
  else b.addEventListener("click", e => { e.stopPropagation(); fn(); });
  return b;
}

function renderSheet(sheet) {
  const el = sheet.el, doc = sheet.doc, content = sheet.content;
  if (!el || !doc || !content) return;
  content.innerHTML = "";

  const hd = document.createElement("header");
  hd.className = "sheet-hd";

  const btns = document.createElement("div");
  btns.className = "hd-btns";
  btns.appendChild(iconBtn("‹", "back", () => back(sheet), !sheet.history.length));
  btns.appendChild(iconBtn("›", "forward", () => forward(sheet), !sheet.future.length));
  if (doc.nav?.prev) btns.appendChild(iconBtn("↑", "previous verse", () => navigate(sheet, doc.nav.prev)));
  if (doc.nav?.next) btns.appendChild(iconBtn("↓", "next verse", () => navigate(sheet, doc.nav.next)));
  const spacer = document.createElement("span"); spacer.className = "hd-spacer";
  btns.appendChild(spacer);
  btns.appendChild(iconBtn("＋", "keep in inventory", () => keepSheet(sheet)));
  btns.appendChild(iconBtn("⧉", "duplicate sheet", () => duplicate(sheet)));
  btns.appendChild(iconBtn("×", "close sheet", () => closeSheet(sheet)));
  hd.appendChild(btns);

  const path = document.createElement("div");
  path.className = "path";
  (doc.path || []).forEach((c, i) => {
    if (i) { const s = document.createElement("span"); s.className = "sep"; s.textContent = " › "; path.appendChild(s); }
    if (c.loc) {
      const a = document.createElement("a"); a.className = "crumb"; a.textContent = c.label;
      bindLink(a, sheet, c.loc);
      path.appendChild(a);
    } else {
      const s = document.createElement("span"); s.className = "crumb cur"; s.textContent = c.label;
      path.appendChild(s);
    }
  });
  hd.appendChild(path);
  content.appendChild(hd);

  const body = document.createElement("div");
  body.className = "sheet-body";
  const ctr = { n: 0 };
  for (const block of doc.blocks) body.appendChild(renderBlock(block, sheet, ctr));
  content.appendChild(body);
}

// ── block rendering ─────────────────────────────────────────────────────────
function spansEl(spans, sheet) {
  const f = document.createElement("span");
  (spans || []).forEach(s => {
    if (s.br) { f.appendChild(document.createElement("br")); return; }
    let node;
    if (s.loc) {
      node = document.createElement("a");
      node.className = "ilink " + (s.cls || "");
      bindLink(node, sheet, s.loc);
    } else {
      node = document.createElement("span");
      node.className = s.cls || "";
    }
    node.textContent = s.text;
    f.appendChild(node);
  });
  return f;
}

function renderBlock(block, sheet, ctr) {
  const d = document.createElement("div");
  switch (block.t) {
    case "head":
      d.className = "b-head";
      d.innerHTML = `<h2>${esc(block.text)}</h2>` +
        (block.sub ? `<div class="sub">${esc(block.sub)}</div>` : "");
      break;
    case "sub":
      d.className = "b-sub";
      d.appendChild(spansEl(block.spans, sheet));
      break;
    case "note":
      d.className = "b-note"; d.textContent = block.text;
      break;
    case "rule":
      d.className = "b-rule";
      break;
    case "lines":
      d.className = "b-lines" + (block.muted ? " muted" : "");
      d.innerHTML = block.items.map(l => `<div>${esc(l)}</div>`).join("");
      break;
    case "chant":
      d.className = "b-chant";
      block.hemistichs.forEach(h => {
        const hemi = document.createElement("div");
        hemi.className = "chant-hemi";
        const txt = document.createElement("div");
        txt.className = "chant-text"; txt.textContent = h.text;
        hemi.appendChild(txt);
        const staff = document.createElement("div");
        staff.className = "chant-staff";
        h.cols.forEach(c => {
          const col = document.createElement("div");
          col.className = "syl";
          col.innerHTML =
            `<span class="r top">${esc(c.top || "")}</span>` +
            `<span class="r mid">${esc(c.mid || "")}</span>` +
            `<span class="r bot">${esc(c.bot || "")}</span>` +
            `<span class="seg">${esc(c.seg)}</span>`;
          staff.appendChild(col);
        });
        hemi.appendChild(staff);
        d.appendChild(hemi);
      });
      break;
    case "prose":
      d.className = "b-prose";
      if (block.label) {
        const lab = document.createElement("span");
        lab.className = "plabel"; lab.textContent = block.label;
        d.appendChild(lab);
      }
      d.appendChild(spansEl(block.spans, sheet));
      break;
    case "tokens":
      d.className = "b-tokens";
      block.items.forEach(it => {
        ctr.n++;
        const a = document.createElement("a");
        a.className = "token"; a.title = it.feat || "";
        a.innerHTML = `<span class="tnum">${ctr.n}</span>` +
          `<span class="tsurf">${esc(it.surface)}</span>` +
          `<span class="tlem">${esc(it.lemma || "")}</span>`;
        bindLink(a, sheet, it.loc);
        d.appendChild(a);
      });
      break;
    case "nav":
      d.className = "b-nav";
      block.items.forEach((it, i) => {
        if (i) {
          const s = document.createElement("span");
          s.className = "nsep"; s.textContent = "·"; d.appendChild(s);
        }
        const a = document.createElement("a");
        a.className = "nlink"; a.textContent = it.label;
        bindLink(a, sheet, it.loc);
        d.appendChild(a);
      });
      break;
    case "links":
      d.className = "b-links" + (block.wrap ? " wrap" : "");
      block.items.forEach(it => {
        ctr.n++;
        const a = document.createElement("a");
        a.className = "lnk";
        let h = `<span class="lnum">${ctr.n}.</span>`;
        if (it.bar != null) {
          const w = Math.max(2, Math.round(it.bar * 36));
          h += `<span class="bar" style="width:${w}px"></span>`;
        }
        h += `<span class="ltext">${esc(it.label || "")}</span>`;
        if (it.tag)  h += `<span class="ltag">${esc(it.tag)}</span>`;
        if (it.note) h += `<span class="lnote">${esc(it.note).replace(/\n/g, "<br>")}</span>`;
        a.innerHTML = h;
        bindLink(a, sheet, it.loc);
        d.appendChild(a);
      });
      break;
    case "grid":
      d.className = "b-grid";
      if (block.caption) {
        const c = document.createElement("div");
        c.className = "gcap"; c.textContent = block.caption;
        d.appendChild(c);
      }
      const t = document.createElement("table");
      if (block.head) {
        const tr = document.createElement("tr");
        block.head.forEach((hc, i) => {
          const th = document.createElement("th");
          th.textContent = hc; if (i === 0) th.className = "rh";
          tr.appendChild(th);
        });
        t.appendChild(tr);
      }
      block.rows.forEach(row => {
        const tr = document.createElement("tr");
        row.forEach((cell, i) => {
          const td = document.createElement(i === 0 ? "th" : "td");
          if (i === 0) td.className = "rh";
          td.textContent = cell;
          tr.appendChild(td);
        });
        t.appendChild(tr);
      });
      d.appendChild(t);
      break;
    default:
      d.textContent = JSON.stringify(block);
  }
  return d;
}

// ── sidebar: index ──────────────────────────────────────────────────────────
function sideOpen(loc) {
  const sheet = sheets.find(s => s.id === activeId);
  if (sheet) { navigate(sheet, loc); setActive(sheet.id); }
  else openSheet(loc);
}

function renderIndex() {
  const nav = $("#index");
  nav.innerHTML = "";
  const add = (label, loc, sub) => {
    const a = document.createElement("a");
    a.className = "side-link" + (sub ? " sub" : "");
    a.textContent = label;
    a.addEventListener("click", () => sideOpen(loc));
    nav.appendChild(a);
  };
  add("Ṛgveda", { kind: "index" });
  for (let n = 1; n <= 10; n++) add("RV " + n, { kind: "mandala", book: n }, true);
  add("stem classes", { kind: "stems" });
}

// ── sidebar: inventory ──────────────────────────────────────────────────────
async function renderInv() {
  const inv = await invGet();
  const nav = $("#inv");
  nav.innerHTML = "";
  const names = Object.keys(inv);
  if (!names.length) { nav.innerHTML = '<div class="empty">empty — use ＋ on a sheet</div>'; return; }
  names.forEach(name => {
    const row = document.createElement("div"); row.className = "inv-row";
    const a = document.createElement("a"); a.className = "side-link";
    a.textContent = name;
    a.addEventListener("click", () => sideOpen(inv[name]));
    const x = document.createElement("button"); x.className = "inv-x";
    x.textContent = "×"; x.title = "drop";
    x.addEventListener("click", async e => {
      e.stopPropagation();
      await invSet("drop", name);
      renderInv();
    });
    row.appendChild(a); row.appendChild(x); nav.appendChild(row);
  });
}

async function keepSheet(sheet) {
  const name = prompt("save this sheet as:", sheet.doc?.title || "");
  if (!name) return;
  await invSet("save", name, sheet.loc);
  renderInv();
}

// ── search + keys ───────────────────────────────────────────────────────────
$("#search").addEventListener("keydown", e => {
  if (e.key === "Enter") {
    const q = e.target.value.trim();
    if (q) sideOpen({ kind: "search", q });
  }
});
document.addEventListener("keydown", e => {
  if (e.key === "/" && document.activeElement !== $("#search")) {
    e.preventDefault(); $("#search").focus();
  }
});

// ── boot ────────────────────────────────────────────────────────────────────
function bootLoc() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h) { try { return JSON.parse(h); } catch (e) {} }
  return { kind: "index" };
}
renderIndex();
renderInv();
openSheet(bootLoc());
