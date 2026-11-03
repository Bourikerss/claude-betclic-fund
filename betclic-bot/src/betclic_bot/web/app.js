// Fonds Claude — rendu de la page à partir des données injectées par build_web.py.
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("fund-data").textContent);
  const M = D.metrics;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = (x) => (x == null ? "—" : x.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €");
  const signed = (x) => (x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + eur(Math.abs(x)));
  const pct = (x, d = 1) => (x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x * 100).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }) + " %");
  const plainPct = (x) => (x == null ? "—" : (x * 100).toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " %");
  const odd = (x) => x.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const tone = (x) => (x > 0 ? "gain" : x < 0 ? "loss" : "");
  const STATUS = { GAGNE: ["won", "Gagné"], PERDU: ["lost", "Perdu"], REMBOURSE: ["void", "Remboursé"], EN_ATTENTE: ["open", "En cours"] };

  // --- En-tête ------------------------------------------------------------------------
  $("dateline").textContent = "Mis à jour le " + D.generated_at;
  $("started").textContent = D.started;
  $("equity").textContent = eur(M.equity);
  $("delta").innerHTML = `<span class="${tone(M.profit)}">${signed(M.profit)} · ${pct(M.profit_pct)}</span> depuis 10,00 €`;
  const fig = (label, value, cls = "", sub = "") => `<div><dt>${label}</dt><dd class="${cls}">${value}${sub ? ` <small>${sub}</small>` : ""}</dd></div>`;
  $("figures").innerHTML = [
    fig("Disponible", eur(M.balance), "", M.exposure ? `${eur(M.exposure)} engagés` : ""),
    fig("ROI", pct(M.roi), tone(M.roi)),
    fig("Rendement (yield)", M.won + M.lost ? pct(M.yield) : "—", tone(M.yield)),
    fig("Réussite", plainPct(M.winrate), "", `${M.won} G · ${M.lost} P${M.void ? ` · ${M.void} R` : ""}`),
    fig("Engagé aujourd'hui", eur(M.staked_today), M.staked_today ? "open" : "", `max ${plainPct(M.daily_cap)}`),
    fig("Drawdown max", M.max_drawdown ? "−" + eur(M.max_drawdown) : eur(0), M.max_drawdown ? "loss" : "", M.max_drawdown ? pct(-M.max_drawdown_pct) : ""),
  ].join("");
  $("stake-rule").textContent = Object.entries(D.rules.stake_pct).map(([k, v]) => `${k} ${plainPct(v)}`).join(", ") + " du solde";

  // --- Courbe du capital ---------------------------------------------------------------
  function drawChart() {
    const box = $("chart");
    const tip = $("tip");
    box.querySelectorAll("svg").forEach((s) => s.remove());
    const W = box.clientWidth, H = box.clientHeight;
    const pad = { l: 46, r: 14, t: 16, b: 26 };
    const pts = D.equity;
    const vals = pts.map((p) => p.v).concat([M.initial]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const span = Math.max(hi - lo, 1);
    lo -= span * 0.15; hi += span * 0.15;
    const n = Math.max(pts.length - 1, 1);
    const x = (i) => pad.l + (W - pad.l - pad.r) * (pts.length === 1 ? 0.5 : i / n);
    const y = (v) => pad.t + (H - pad.t - pad.b) * (1 - (v - lo) / (hi - lo));
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ticks = 4;
    let grid = "", axis = "";
    for (let k = 0; k <= ticks; k++) {
      const v = lo + ((hi - lo) * k) / ticks, yy = y(v);
      grid += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${yy}" y2="${yy}"/>`;
      axis += `<text x="${pad.l - 8}" y="${yy + 3}" text-anchor="end">${v.toFixed(2).replace(".", ",")}</text>`;
    }
    const first = pts[0], last = pts[pts.length - 1];
    axis += `<text x="${pad.l}" y="${H - 8}">${esc(first.t.slice(0, 5))}</text>`;
    if (pts.length > 1) axis += `<text x="${W - pad.r}" y="${H - 8}" text-anchor="end">${esc(last.t.slice(0, 5))}</text>`;
    const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    const area = `${path}L${x(pts.length - 1).toFixed(1)},${y(lo)}L${x(0).toFixed(1)},${y(lo)}Z`;
    const color = last.v >= M.initial ? "var(--gain)" : "var(--loss)";
    const dots = pts.map((p, i) => {
      const c = p.status === "GAGNE" ? "var(--gain)" : p.status === "PERDU" ? "var(--loss)" : "var(--ink)";
      return `<circle class="dot" cx="${x(i)}" cy="${y(p.v)}" r="${pts.length > 60 ? 2.5 : 4}" fill="${c}"/>`;
    }).join("");
    svg.innerHTML = `<g class="grid">${grid}</g><g class="axis">${axis}</g>
      <line class="base" x1="${pad.l}" x2="${W - pad.r}" y1="${y(M.initial)}" y2="${y(M.initial)}"/>
      <path class="area" d="${area}" fill="${color}"/><path class="line" d="${path}"/>
      <line class="cursor" id="cursor" y1="${pad.t}" y2="${H - pad.b}" visibility="hidden"/>${dots}`;
    box.insertBefore(svg, tip);

    const cursor = svg.querySelector("#cursor");
    const show = (clientX) => {
      const r = svg.getBoundingClientRect();
      const px = clientX - r.left;
      let i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * n);
      i = Math.max(0, Math.min(pts.length - 1, pts.length === 1 ? 0 : i));
      const p = pts[i];
      cursor.setAttribute("x1", x(i)); cursor.setAttribute("x2", x(i)); cursor.setAttribute("visibility", "visible");
      const st = p.status ? STATUS[p.status] : null;
      tip.innerHTML = `<div class="t">${esc(p.t)}</div><div class="v">${eur(p.v)}</div>
        <div>${esc(p.label)}</div>${st ? `<div><span class="pill ${st[0]}">${st[1]}</span> <span class="mono ${tone(p.net)}">${signed(p.net)}</span>${p.score ? ` · <span class="mono">${esc(p.score)}</span>` : ""}</div>` : ""}`;
      tip.hidden = false;
      const left = Math.min(Math.max(x(i) - 90, 8), W - tip.offsetWidth - 8);
      tip.style.left = left + "px";
    };
    const hide = () => { tip.hidden = true; cursor.setAttribute("visibility", "hidden"); };
    svg.addEventListener("pointermove", (e) => show(e.clientX));
    svg.addEventListener("pointerdown", (e) => show(e.clientX));
    svg.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hide(); });
  }
  drawChart();
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawChart, 120); });

  // --- Positions du jour ----------------------------------------------------------------
  const positions = D.positions;
  $("positions-note").textContent = positions.length
    ? `${positions.length} position${positions.length > 1 ? "s" : ""} ouverte${positions.length > 1 ? "s" : ""} · ${eur(M.exposure)} engagés`
    : "Aucune position ouverte.";
  $("positions").innerHTML = positions.map((b) => {
    const kind = b.kind === "COMBINE" ? "Combiné du jour" : b.kind === "FUN" ? "Pari fun" : b.profile_name;
    const body = b.kind === "COMBINE"
      ? `<div class="t-match">Combiné · ${b.legs.length} sélections</div>
         <ul class="t-legs">${b.legs.map((l) => `<li><span>${esc(l.selection)}<small>${esc(l.match)} · ${esc(l.kickoff)}</small></span><span>${odd(l.odd)}</span></li>`).join("")}</ul>`
      : `<div><div class="t-match">${esc(b.match)}</div><div class="t-meta">${esc(b.competition)} · ${esc(b.kickoff)} · ${esc(b.market)}</div></div>
         <div class="t-bet">${esc(b.selection)}</div>`;
    return `<article class="ticket" data-profile="${esc(b.profile)}">
      <div class="t-top"><span>${esc(kind)}</span><span class="conf">confiance ${b.confidence}/100</span></div>
      ${body}
      <div class="t-figs"><div>Cote<b>${odd(b.odd)}</b></div><div>Mise<b>${eur(b.stake)}</b></div><div>Gain potentiel<b>${eur(b.potential)}</b></div></div>
      ${b.headline ? `<p class="t-why">${esc(b.headline)}</p>` : ""}
    </article>`;
  }).join("");

  // --- Grand livre ------------------------------------------------------------------------
  const FILTERS = {
    all: () => true, won: (b) => b.status === "GAGNE", lost: (b) => b.status === "PERDU",
    open: (b) => b.status === "EN_ATTENTE", single: (b) => b.kind !== "COMBINE", combo: (b) => b.kind === "COMBINE",
  };
  function renderBook(f) {
    const rows = D.bets.filter(FILTERS[f]);
    $("book-empty").hidden = rows.length > 0;
    document.querySelector("#book tbody").innerHTML = rows.map((b) => {
      const st = STATUS[b.status] || ["", b.status];
      const legs = b.kind === "COMBINE" ? `<small>${b.legs.map((l) => esc(l.match)).join(" + ")}</small>` : "";
      return `<tr>
        <td class="mono nowrap">${esc(b.placed)}</td>
        <td>${esc(b.competition)}</td>
        <td class="match">${b.kind === "COMBINE" ? "Combiné du jour" + legs : esc(b.match)}</td>
        <td class="bet">${esc(b.selection)}<small>${esc(b.market)} · <span class="pill ${st[0]}">${st[1]}</span></small></td>
        <td class="num">${odd(b.odd)}</td>
        <td class="num">−${eur(b.stake)}</td>
        <td class="mono nowrap">${esc(b.score || "—")}</td>
        <td class="num ${tone(b.net)}">${b.net == null ? "—" : signed(b.net)}</td>
        <td class="num">${eur(b.balance)}</td>
      </tr>`;
    }).join("");
  }
  document.querySelectorAll("#filters button").forEach((btn) => btn.addEventListener("click", () => {
    document.querySelectorAll("#filters button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    renderBook(btn.dataset.f);
  }));
  renderBook("all");

  // --- Analytique -------------------------------------------------------------------------
  function renderGroup(id, rows) {
    const head = `<thead><tr><th></th><th class="num">Paris</th><th class="num">Réussite</th><th class="num">Misé</th><th class="num">Net</th><th class="num">Yield</th></tr></thead>`;
    const body = rows.length ? rows.map((r) => `<tr><td>${esc(r.name)}</td><td class="num">${r.count}${r.settled < r.count ? `<small>${r.count - r.settled} en cours</small>` : ""}</td>
      <td class="num">${plainPct(r.winrate)}</td><td class="num">${eur(r.staked)}</td>
      <td class="num ${tone(r.net)}">${r.settled ? signed(r.net) : "—"}</td><td class="num ${tone(r.yield)}">${r.yield == null ? "—" : pct(r.yield)}</td></tr>`).join("")
      : `<tr><td colspan="6" class="empty">Pas encore de pari.</td></tr>`;
    $(id).innerHTML = head + `<tbody>${body}</tbody>`;
  }
  renderGroup("by-profile", D.analytics.by_profile);
  renderGroup("by-market", D.analytics.by_market);
})();
