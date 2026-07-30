"""Build script for docs/visualization/taxonomy_chain.html.

Reads case1 data + CSF 2.0 catalogue and emits a single self-contained HTML
with embedded JSON data and 4 ECharts visualisations.

Run: python3 docs/visualization/build.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE1 = ROOT / "cases/case1-tinytask/data/phase1"
CSF_JSON = ROOT / "preproc_out/global/NIST_CSF_2.0_subcategories.json"
OUT = ROOT / "docs/visualization/taxonomy_chain.html"


REG_COLORS = {
    "GDPR": "#FF6B6B",
    "CRA": "#4ECDC4",
    "NIS2": "#FFD93D",
    "DORA": "#6C5CE7",
    "AIACT": "#A8E6CF",
}


def load_regulations() -> list[dict]:
    regs = []
    with open(CASE1 / "00_regulations.csv") as f:
        for r in csv.DictReader(f):
            regs.append(
                {
                    "id": r["regulationId"],
                    "name": r["fullName"],
                    "shortName": r["shortName"],
                    "type": r["type"],
                    "effectiveDate": r["effectiveDate"],
                    "primaryFocus": r["primaryFocus"],
                    "color": REG_COLORS.get(r["regulationId"], "#888"),
                }
            )
    return regs


def load_domains() -> list[dict]:
    domains = []
    with open(CASE1 / "01_domains.csv") as f:
        for r in csv.DictReader(f):
            domains.append(
                {
                    "id": r["domainId"],
                    "name": r["name"],
                    "description": r["description"],
                    "primaryRegulatoryDriver": r["primaryRegulatoryDriver"],
                }
            )
    return domains


def load_subdomains() -> list[dict]:
    subs = []
    with open(CASE1 / "02_subdomains.csv") as f:
        for r in csv.DictReader(f):
            subs.append(
                {
                    "id": r["subDomainId"],
                    "domainId": r["domainId"],
                    "name": r["name"],
                    "description": r["description"],
                    "keywords": r["keywords"],
                    "examples": r["examples"],
                    "soleAuthority": r["soleAuthority"],
                    "gapRisk": r["gapRisk"],
                }
            )
    return subs


def load_clauses_and_mappings() -> list[dict]:
    """Load the 150 case1-mapped clauses with summaries."""
    with open(CASE1 / "04_clauses.csv") as f:
        clauses_by_id = {c["clauseId"]: c for c in csv.DictReader(f)}
    mappings = []
    with open(CASE1 / "07_clause_subdomain_mapping.csv") as f:
        for m in csv.DictReader(f):
            cid = m["clauseId"]
            clause = clauses_by_id.get(cid, {})
            reg_id = cid.split("-")[0]
            mappings.append(
                {
                    "id": cid,
                    "regulationId": reg_id,
                    "subdomainId": m["subDomainId"],
                    "summary": clause.get("summary", "")[:120],
                    "weight": float(m["weight"]),
                }
            )
    return mappings


def load_csf() -> tuple[list[dict], dict[str, list[str]]]:
    """Returns (csf_subcategories, subdomain->csf_ids map)."""
    with open(CSF_JSON) as f:
        csf = json.load(f)
    subs = [
        {
            "id": s["id"],
            "function": s["function"],
            "functionName": s["function_name"],
            "categoryId": s["category_id"],
            "categoryName": s["category_name"],
            "title": s["title"],
            "withdrawn": s["withdrawn"],
        }
        for s in csf["subcategories"]
    ]
    sd_map = {}
    for row in csf["cross_reference_aegis_subdomains"]["rows"]:
        sd_map[row["aegis_subdomain"]] = row["csf_ids"]
    return subs, sd_map


def main() -> None:
    regulations = load_regulations()
    domains = load_domains()
    subdomains = load_subdomains()
    clauses = load_clauses_and_mappings()
    csf_subs, sd_csf_map = load_csf()

    data = {
        "regulations": regulations,
        "domains": domains,
        "subdomains": subdomains,
        "clauses": clauses,
        "csfSubcategories": csf_subs,
        "subdomainCsfMap": sd_csf_map,
        "stats": {
            "regulations": len(regulations),
            "domains": len(domains),
            "subdomains": len(subdomains),
            "mappedClauses": len(clauses),
            "csfSubcategories": len([s for s in csf_subs if not s["withdrawn"]]),
            "mappedCsf": len({c for cs in sd_csf_map.values() for c in cs}),
        },
    }

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB)")
    print(f"  Regulations: {len(regulations)}")
    print(f"  Domains: {len(domains)}")
    print(f"  Subdomains: {len(subdomains)}")
    print(f"  Mapped clauses: {len(clauses)}")
    print(f"  CSF subcategories: {len(csf_subs)}")
    print(f"  Subdomain->CSF mappings: {sum(len(v) for v in sd_csf_map.values())} links")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AEGIS-KG — Taxonomy Chain Viewer (case1)</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@6.1/dist/echarts.min.js"></script>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a1f2e;
      --panel-2: #242b3d;
      --border: #2d3548;
      --fg: #e1e7f0;
      --fg-dim: #8b95a7;
      --accent: #4ecdc4;
      --accent-2: #6c5ce7;
      --warn: #ffd93d;
      --danger: #ff6b6b;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--fg);
    }
    body { display: flex; flex-direction: column; }
    header {
      padding: 12px 24px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 12px;
    }
    header h1 {
      margin: 0; font-size: 18px; font-weight: 600; letter-spacing: 0.3px;
    }
    header h1 small { color: var(--fg-dim); font-weight: 400; font-size: 12px; margin-left: 8px; }
    .tabs {
      display: flex; gap: 4px; background: var(--panel-2); padding: 4px; border-radius: 8px;
    }
    .tab {
      padding: 6px 14px; border: none; background: transparent; color: var(--fg-dim);
      font-size: 13px; cursor: pointer; border-radius: 6px; transition: all 0.15s;
    }
    .tab:hover { color: var(--fg); }
    .tab.active { background: var(--accent); color: var(--bg); font-weight: 600; }

    main {
      flex: 1; display: grid; grid-template-columns: 220px 1fr 320px;
      gap: 1px; background: var(--border); min-height: 0;
    }
    aside, section, .detail {
      background: var(--panel); padding: 16px; overflow-y: auto;
    }
    aside h3, .detail h3 {
      margin: 0 0 12px 0; font-size: 12px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 1px; color: var(--fg-dim);
    }
    .filter-group { margin-bottom: 20px; }
    .filter-group label {
      display: flex; align-items: center; gap: 8px; padding: 4px 0;
      font-size: 13px; cursor: pointer; user-select: none;
    }
    .filter-group input[type=checkbox] { accent-color: var(--accent); }
    .filter-group .count { color: var(--fg-dim); font-size: 11px; margin-left: auto; }
    .filter-group .swatch {
      display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    }
    input[type=search] {
      width: 100%; padding: 6px 10px; background: var(--panel-2); border: 1px solid var(--border);
      color: var(--fg); border-radius: 6px; font-size: 13px; outline: none;
    }
    input[type=search]:focus { border-color: var(--accent); }
    .stats {
      margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border);
      font-size: 12px; color: var(--fg-dim); line-height: 1.7;
    }
    .stats strong { color: var(--fg); font-weight: 600; }

    #viz { width: 100%; height: 100%; min-height: 500px; }

    .detail { font-size: 13px; line-height: 1.5; }
    .detail .empty { color: var(--fg-dim); font-style: italic; padding: 20px 0; text-align: center; }
    .detail h2 { margin: 0 0 8px 0; font-size: 14px; color: var(--accent); }
    .detail .meta { color: var(--fg-dim); font-size: 11px; margin-bottom: 12px; }
    .detail .meta span { margin-right: 12px; }
    .detail .chain { margin: 12px 0; }
    .detail .chain-step {
      display: inline-block; padding: 3px 8px; background: var(--panel-2);
      border-radius: 4px; margin: 2px; font-size: 11px; color: var(--fg);
    }
    .detail .chain-arrow { color: var(--fg-dim); margin: 0 4px; }
    .detail .related { margin-top: 12px; }
    .detail .related h4 {
      margin: 8px 0 4px 0; font-size: 11px; text-transform: uppercase;
      letter-spacing: 1px; color: var(--fg-dim);
    }
    .detail .related ul { margin: 0; padding-left: 18px; }
    .detail .related li { margin: 2px 0; cursor: pointer; color: var(--accent); }
    .detail .related li:hover { text-decoration: underline; }
    .detail p { margin: 8px 0; }

    footer {
      padding: 8px 24px; background: var(--panel); border-top: 1px solid var(--border);
      font-size: 11px; color: var(--fg-dim); display: flex; justify-content: space-between;
    }
  </style>
</head>
<body>
  <header>
    <h1>AEGIS-KG — Taxonomy Chain Viewer <small>case1 · 5 regs → 38 subs → 106 CSF</small></h1>
    <div class="tabs" id="mode-tabs">
      <button class="tab active" data-mode="sankey">Sankey</button>
      <button class="tab" data-mode="tree">Tree</button>
      <button class="tab" data-mode="heatmap">Heatmap</button>
      <button class="tab" data-mode="sunburst">Sunburst</button>
    </div>
  </header>

  <main>
    <aside>
      <h3>Filters</h3>
      <div class="filter-group" id="reg-filter"></div>
      <h3>Search</h3>
      <input type="search" id="search" placeholder="Search subdomains, clauses, CSF..." />

      <div class="stats" id="stats"></div>
    </aside>

    <section><div id="viz"></div></section>

    <div class="detail" id="detail">
      <div class="empty">Click a node in the visualization to inspect its details, upstream regulations, and downstream CSF mappings.</div>
    </div>
  </main>

  <footer>
    <span>Library: Apache ECharts v6.1 · Data: case1 (150 mapped clauses) · Generated 2026-07-29</span>
    <span id="footer-info"></span>
  </footer>

  <script id="app-data" type="application/json">__DATA_JSON__</script>
  <script>
  (function () {
    const DATA = JSON.parse(document.getElementById('app-data').textContent);
    const STATE = {
      mode: 'sankey',
      activeRegs: new Set(DATA.regulations.map(r => r.id)),
      search: '',
      selectedNode: null,
      chart: null,
    };

    // ---- Filters ----
    const regFilterEl = document.getElementById('reg-filter');
    function renderFilters() {
      regFilterEl.innerHTML = '<label><strong style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--fg-dim);">Regulations</strong></label>';
      DATA.regulations.forEach(r => {
        const clauseCount = DATA.clauses.filter(c => c.regulationId === r.id).length;
        const label = document.createElement('label');
        label.innerHTML = `
          <input type="checkbox" data-reg="${r.id}" ${STATE.activeRegs.has(r.id) ? 'checked' : ''} />
          <span class="swatch" style="background:${r.color}"></span>
          <span>${r.shortName}</span>
          <span class="count">${clauseCount}</span>`;
        regFilterEl.appendChild(label);
      });
      regFilterEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.addEventListener('change', e => {
          const regId = e.target.dataset.reg;
          if (e.target.checked) STATE.activeRegs.add(regId);
          else STATE.activeRegs.delete(regId);
          render();
        });
      });
    }

    // ---- Stats ----
    function renderStats() {
      const s = DATA.stats;
      const mappedCsfPct = Math.round(100 * s.mappedCsf / s.csfSubcategories);
      document.getElementById('stats').innerHTML = `
        <strong>5</strong> regulations in scope<br/>
        <strong>${s.domains}</strong> domains · <strong>${s.subdomains}</strong> sub-domains<br/>
        <strong>${s.mappedClauses}</strong> mapped clauses (case1)<br/>
        <strong>${s.mappedCsf}/${s.csfSubcategories}</strong> CSF controls driven (${mappedCsfPct}%)
      `;
    }

    // ---- Helpers ----
    function visibleClauses() {
      return DATA.clauses.filter(c => STATE.activeRegs.has(c.regulationId));
    }
    function visibleSubdomains() {
      const sdIds = new Set(visibleClauses().map(c => c.subdomainId));
      return DATA.subdomains.filter(sd => sdIds.has(sd.id));
    }
    function matchesSearch(text) {
      if (!STATE.search) return true;
      const q = STATE.search.toLowerCase();
      return text.toLowerCase().includes(q);
    }

    // ---- Sankey: Reg → Subdomain → CSF ----
    function renderSankey() {
      const clauses = visibleClauses();
      const visibleSdIds = new Set(clauses.map(c => c.subdomainId));

      const reg2sd = {};
      clauses.forEach(c => {
        const k = `${c.regulationId}|||${c.subdomainId}`;
        reg2sd[k] = (reg2sd[k] || 0) + 1;
      });

      const sd2csf = {};
      Object.keys(DATA.subdomainCsfMap).forEach(sdId => {
        if (!visibleSdIds.has(sdId)) return;
        DATA.subdomainCsfMap[sdId].forEach(csfId => {
          sd2csf[`${sdId}|||${csfId}`] = 1;
        });
      });

      const regNames = {};
      const sdNames = {};
      const csfNames = {};
      DATA.regulations.forEach(r => regNames[r.id] = r.shortName);
      DATA.subdomains.forEach(sd => sdNames[sd.id] = `${sd.id} ${sd.name}`);
      const csfById = Object.fromEntries(DATA.csfSubcategories.map(s => [s.id, s]));

      const nodes = [];
      const nodeIdx = {};
      function addNode(name, depth, itemStyle) {
        if (nodeIdx[name] !== undefined) return;
        nodeIdx[name] = nodes.length;
        nodes.push({ name, depth, itemStyle });
      }
      DATA.regulations.filter(r => STATE.activeRegs.has(r.id)).forEach(r => {
        addNode(regNames[r.id], 0, { color: r.color, borderColor: r.color });
      });
      DATA.subdomains.filter(sd => visibleSdIds.has(sd.id)).forEach(sd => {
        addNode(sdNames[sd.id], 1, { color: '#6c5ce7', borderColor: '#6c5ce7' });
      });
      const visibleCsfIds = new Set(Object.keys(sd2csf).map(k => k.split('|||')[1]));
      DATA.csfSubcategories.filter(s => visibleCsfIds.has(s.id)).forEach(s => {
        addNode(s.id, 2, { color: '#4ecdc4', borderColor: '#4ecdc4' });
      });

      const links = [];
      Object.entries(reg2sd).forEach(([k, v]) => {
        const [reg, sd] = k.split('|||');
        links.push({ source: regNames[reg], target: sdNames[sd], value: v });
      });
      Object.entries(sd2csf).forEach(([k]) => {
        const [sd, csf] = k.split('|||');
        links.push({ source: sdNames[sd], target: csf, value: 1 });
      });

      return {
        tooltip: { trigger: 'item', triggerOn: 'mousemove',
          formatter: p => {
            if (p.dataType === 'edge') {
              return `<b>${p.data.source}</b> → <b>${p.data.target}</b><br/>Weight: ${p.data.value}`;
            }
            const reg = DATA.regulations.find(r => regNames[r.id] === p.name);
            if (reg) return `<b>${reg.shortName}</b><br/>${reg.name}<br/><i>${reg.primaryFocus}</i>`;
            const sd = DATA.subdomains.find(s => sdNames[s.id] === p.name);
            if (sd) return `<b>${sd.id}</b> ${sd.name}<br/><i>${sd.description}</i>`;
            const csf = csfById[p.name];
            if (csf) return `<b>${csf.id}</b><br/>${csf.title}<br/><i>${csf.functionName} / ${csf.categoryName}</i>`;
            return p.name;
          }
        },
        series: [{
          type: 'sankey',
          left: 20, right: 220, top: 20, bottom: 20,
          data: nodes, links,
          emphasis: { focus: 'adjacency' },
          lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.45 },
          label: { fontSize: 10, color: '#e1e7f0' },
          nodeWidth: 14, nodeGap: 8,
        }],
      };
    }

    // ---- Tree: Domain → Subdomain → CSF ----
    function renderTree() {
      const visibleSdIds = new Set(visibleClauses().map(c => c.subdomainId));
      const tree = [];
      DATA.domains.forEach(d => {
        const sdList = DATA.subdomains.filter(sd => sd.domainId === d.id && visibleSdIds.has(sd.id));
        if (!sdList.length) return;
        const domainNode = { name: d.name, children: [] };
        sdList.forEach(sd => {
          const csfList = (DATA.subdomainCsfMap[sd.id] || [])
            .map(id => csfById(id)).filter(Boolean)
            .filter(csf => matchesSearch(csf.title) || matchesSearch(csf.id));
          const filteredCsfList = csfList.length ? csfList : [{ id: '—', title: '(no CSF mapped)', functionName: '' }];
          domainNode.children.push({
            name: `${sd.id} ${sd.name}`,
            children: filteredCsfList.map(csf => ({ name: csf.id, value: csf.title }))
          });
        });
        tree.push(domainNode);
      });
      function csfById(id) { return DATA.csfSubcategories.find(s => s.id === id); }

      return {
        tooltip: { trigger: 'item', triggerOn: 'mousemove',
          formatter: p => {
            if (!p.data) return '';
            const csf = csfById(p.name);
            if (csf) return `<b>${csf.id}</b><br/>${csf.title}`;
            const sd = DATA.subdomains.find(s => `${s.id} ${s.name}` === p.name);
            if (sd) return `<b>${sd.id}</b> ${sd.name}<br/><i>${sd.description}</i>`;
            return p.name;
          }
        },
        series: [{
          type: 'tree',
          data: tree,
          left: 20, right: 20, top: 20, bottom: 20,
          symbol: 'emptyCircle', symbolSize: 7,
          orient: 'LR', expandAndCollapse: true,
          initialTreeDepth: 2,
          label: { position: 'left', verticalAlign: 'middle', align: 'right',
                   fontSize: 11, color: '#e1e7f0', formatter: '{b}' },
          leaves: { label: { position: 'right', align: 'left' } },
          lineStyle: { color: '#4ecdc4', curveness: 0.5, width: 1, opacity: 0.6 },
          itemStyle: { color: '#6c5ce7', borderColor: '#4ecdc4' },
          emphasis: { focus: 'descendant', itemStyle: { color: '#4ecdc4' } },
        }],
      };
    }

    // ---- Heatmap: Reg × Subdomain (clause count) ----
    function renderHeatmap() {
      const visibleSdIds = new Set(visibleClauses().map(c => c.subdomainId));
      const xAxis = DATA.subdomains.filter(sd => visibleSdIds.has(sd.id)).map(sd => sd.id);
      const yAxis = DATA.regulations.filter(r => STATE.activeRegs.has(r.id)).map(r => r.shortName);

      const data = [];
      yAxis.forEach((regName, yi) => {
        const regId = DATA.regulations.find(r => r.shortName === regName).id;
        xAxis.forEach((sdId, xi) => {
          const count = visibleClauses().filter(c => c.regulationId === regId && c.subdomainId === sdId).length;
          if (count > 0) data.push([xi, yi, count]);
        });
      });

      return {
        tooltip: { position: 'top',
          formatter: p => {
            const sdId = xAxis[p.data[0]];
            const regName = yAxis[p.data[1]];
            const sd = DATA.subdomains.find(s => s.id === sdId);
            return `<b>${regName}</b> → <b>${sdId}</b> ${sd ? sd.name : ''}<br/>${p.data[2]} clause(s) mapped`;
          }
        },
        grid: { left: 80, right: 20, top: 30, bottom: 80 },
        xAxis: { type: 'category', data: xAxis, axisLabel: { rotate: 70, fontSize: 10, color: '#e1e7f0' },
                 splitArea: { show: true } },
        yAxis: { type: 'category', data: yAxis, axisLabel: { fontSize: 11, color: '#e1e7f0' },
                 splitArea: { show: true } },
        visualMap: { min: 0, max: 8, calculable: true, orient: 'horizontal',
                     left: 'center', bottom: 5, textStyle: { color: '#e1e7f0' },
                     inRange: { color: ['#1a1f2e', '#4ecdc4', '#ffd93d', '#ff6b6b'] } },
        series: [{ type: 'heatmap', data,
          label: { show: true, color: '#0f1419', fontSize: 10, fontWeight: 'bold' },
          itemStyle: { borderColor: '#0f1419', borderWidth: 1 },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(78,205,196,0.5)' } } }],
      };
    }

    // ---- Sunburst: Reg → Domain → Subdomain → CSF Function ----
    function renderSunburst() {
      const visibleSdIds = new Set(visibleClauses().map(c => c.subdomainId));
      const regById = Object.fromEntries(DATA.regulations.map(r => [r.id, r]));
      const clausesBySd = {};
      visibleClauses().forEach(c => {
        clausesBySd[c.subdomainId] = (clausesBySd[c.subdomainId] || 0) + 1;
      });

      const data = DATA.regulations.filter(r => STATE.activeRegs.has(r.id)).map(r => {
        const domainChildren = DATA.domains.map(d => {
          const sdList = DATA.subdomains.filter(sd => sd.domainId === d.id && visibleSdIds.has(sd.id));
          if (!sdList.length) return null;
          const subdChildren = sdList.map(sd => {
            const csfIds = (DATA.subdomainCsfMap[sd.id] || []);
            const csfFns = {};
            csfIds.forEach(id => {
              const csf = DATA.csfSubcategories.find(s => s.id === id);
              if (!csf) return;
              csfFns[csf.function] = (csfFns[csf.function] || 0) + 1;
            });
            const fnChildren = Object.entries(csfFns).map(([fn, n]) => ({ name: fn, value: n }));
            return { name: sd.id, value: clausesBySd[sd.id] || 1, children: fnChildren };
          }).filter(Boolean);
          if (!subdChildren.length) return null;
          return { name: d.name, children: subdChildren };
        }).filter(Boolean);
        return { name: r.shortName, itemStyle: { color: r.color }, children: domainChildren };
      }).filter(d => d.children && d.children.length);

      return {
        tooltip: { trigger: 'item',
          formatter: p => `<b>${p.name}</b><br/>${p.value || 0} item(s)` },
        series: [{
          type: 'sunburst',
          data, radius: ['8%', '92%'],
          sort: undefined, emphasis: { focus: 'ancestor' },
          label: { color: '#0f1419', fontSize: 10, fontWeight: 'bold',
                   rotate: 'tangential' },
          itemStyle: { borderRadius: 4, borderColor: '#0f1419', borderWidth: 1 },
          levels: [
            {}, // root
            { r0: '8%', r: '25%', label: { fontSize: 13 } },
            { r0: '25%', r: '55%', label: { fontSize: 11 } },
            { r0: '55%', r: '78%', label: { fontSize: 9 } },
            { r0: '78%', r: '92%', label: { fontSize: 9 } },
          ],
        }],
      };
    }

    // ---- Detail panel ----
    function renderDetail(nodeId, nodeLabel) {
      const el = document.getElementById('detail');
      if (!nodeId) {
        el.innerHTML = '<div class="empty">Click a node in the visualization to inspect its details, upstream regulations, and downstream CSF mappings.</div>';
        return;
      }
      const reg = DATA.regulations.find(r => r.id === nodeId || r.shortName === nodeId);
      if (reg) {
        const sd = DATA.subdomains.filter(s => {
          const cs = visibleClauses().filter(c => c.subdomainId === s.id && c.regulationId === reg.id);
          return cs.length > 0;
        });
        el.innerHTML = `
          <h2>${reg.shortName}</h2>
          <div class="meta"><span>${reg.name}</span></div>
          <p>${reg.primaryFocus}</p>
          <p><strong>Type:</strong> ${reg.type} · <strong>Effective:</strong> ${reg.effectiveDate}</p>
          <div class="chain"><span class="chain-step">${reg.shortName}</span><span class="chain-arrow">→</span><span class="chain-step">${visibleClauses().filter(c => c.regulationId === reg.id).length} clauses</span><span class="chain-arrow">→</span><span class="chain-step">${sd.length} sub-domains</span></div>
          <div class="related"><h4>Sub-domains driven by ${reg.shortName} (${sd.length})</h4><ul>${sd.map(s => `<li data-sd="${s.id}">${s.id} — ${s.name}</li>`).join('')}</ul></div>
        `;
        el.querySelectorAll('li[data-sd]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sd);
        });
        return;
      }
      const sd = DATA.subdomains.find(s => s.id === nodeId);
      if (sd) {
        const cs = visibleClauses().filter(c => c.subdomainId === sd.id);
        const csfIds = DATA.subdomainCsfMap[sd.id] || [];
        const csfList = csfIds.map(id => DATA.csfSubcategories.find(s => s.id === id)).filter(Boolean);
        const drivers = [...new Set(cs.map(c => c.regulationId))];
        el.innerHTML = `
          <h2>${sd.id} — ${sd.name}</h2>
          <div class="meta"><span>${sd.domainId} ${DATA.domains.find(d => d.id === sd.domainId)?.name || ''}</span></div>
          <p>${sd.description}</p>
          <p><strong>Keywords:</strong> ${sd.keywords}</p>
          <p><strong>Sole authority:</strong> ${sd.soleAuthority} · <strong>Gap risk:</strong> ${sd.gapRisk}</p>
          <div class="chain">
            <span class="chain-step">${drivers.map(d => DATA.regulations.find(r => r.id === d)?.shortName).join(' + ')}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${cs.length} clauses</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sd.id}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csfList.length} CSF controls</span>
          </div>
          <div class="related">
            <h4>CSF 2.0 Controls (${csfList.length})</h4>
            <ul>${csfList.map(c => `<li title="${c.title}">${c.id} <span style="color:var(--fg-dim)">— ${c.title.slice(0,60)}${c.title.length>60?'…':''}</span></li>`).join('')}</ul>
            <h4>Sample clauses (${Math.min(cs.length, 5)} of ${cs.length})</h4>
            <ul>${cs.slice(0, 5).map(c => `<li><b>${c.id}</b> — ${c.summary}</li>`).join('')}</ul>
          </div>
        `;
        return;
      }
      const csf = DATA.csfSubcategories.find(s => s.id === nodeId);
      if (csf) {
        const sdIds = Object.keys(DATA.subdomainCsfMap).filter(k => DATA.subdomainCsfMap[k].includes(csf.id));
        const sds = sdIds.map(id => DATA.subdomains.find(s => s.id === id)).filter(Boolean);
        const drivers = [...new Set(visibleClauses().filter(c => sdIds.includes(c.subdomainId)).map(c => c.regulationId))];
        el.innerHTML = `
          <h2>${csf.id}</h2>
          <div class="meta"><span>${csf.functionName} / ${csf.categoryName}</span></div>
          <p>${csf.title}</p>
          <div class="chain">
            <span class="chain-step">${drivers.map(d => DATA.regulations.find(r => r.id === d)?.shortName).join(' + ')}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sds.length} sub-domains</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csf.id}</span>
          </div>
          <div class="related">
            <h4>AEGIS Sub-domains driving this control (${sds.length})</h4>
            <ul>${sds.map(sd => `<li data-sd="${sd.id}">${sd.id} — ${sd.name}</li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sd]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sd);
        });
        return;
      }
      el.innerHTML = `<div class="empty">Node "${nodeLabel || nodeId}" not found in detail index.</div>`;
    }

    // ---- Click handling ----
    function attachClickHandler() {
      STATE.chart.on('click', params => {
        if (!params.name) return;
        let nodeId = null;
        const reg = DATA.regulations.find(r => r.shortName === params.name);
        if (reg) nodeId = reg.id;
        else if (DATA.subdomains.some(s => `${s.id} ${s.name}` === params.name)) {
          nodeId = DATA.subdomains.find(s => `${s.id} ${s.name}` === params.name).id;
        } else if (DATA.csfSubcategories.some(s => s.id === params.name)) {
          nodeId = params.name;
        }
        if (nodeId) renderDetail(nodeId, params.name);
      });
    }

    // ---- Mode switch ----
    function setMode(mode) {
      STATE.mode = mode;
      document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.dataset.mode === mode);
      });
      render();
    }
    document.getElementById('mode-tabs').addEventListener('click', e => {
      if (e.target.dataset.mode) setMode(e.target.dataset.mode);
    });

    // ---- Search ----
    document.getElementById('search').addEventListener('input', e => {
      STATE.search = e.target.value.trim();
      render();
    });

    // ---- Render ----
    function render() {
      let option;
      switch (STATE.mode) {
        case 'tree': option = renderTree(); break;
        case 'heatmap': option = renderHeatmap(); break;
        case 'sunburst': option = renderSunburst(); break;
        default: option = renderSankey();
      }
      STATE.chart.setOption(option, true);
      document.getElementById('footer-info').textContent =
        `Mode: ${STATE.mode} · Active regs: ${STATE.activeRegs.size}/5 · Search: "${STATE.search || '∅'}"`;
    }

    // ---- Init ----
    STATE.chart = echarts.init(document.getElementById('viz'), null, { renderer: 'canvas' });
    window.addEventListener('resize', () => STATE.chart.resize());
    STATE.chart.on('click', attachClickHandler);
    STATE.chart.on('click', params => {
      let nodeId = null;
      const reg = DATA.regulations.find(r => r.shortName === params.name);
      if (reg) nodeId = reg.id;
      else {
        const sd = DATA.subdomains.find(s => `${s.id} ${s.name}` === params.name);
        if (sd) nodeId = sd.id;
        else if (DATA.csfSubcategories.some(s => s.id === params.name)) nodeId = params.name;
      }
      if (nodeId) renderDetail(nodeId, params.name);
    });
    renderFilters();
    renderStats();
    render();
  })();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
