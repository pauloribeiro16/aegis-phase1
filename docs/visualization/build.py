"""Build script for docs/visualization/taxonomy_chain.html.

Reads the AEGIS methodology (case-INDEPENDENT source of truth) and emits a
single self-contained HTML with embedded JSON data and 4 ECharts visualisations.

Sources:
  - methodology-00/PREPROCESSING/Regulation/{REG}/02_SecurityRules_NIST.md
    (5 files, 282 SecurityRules total — case-agnostic regulatory baseline)
  - preproc_out/global/NIST_CSF_2.0_subcategories.json (CSF 2.0 catalogue)
  - cases/*/data/phase1/{00_regulations,01_domains,02_subdomains}.csv
    (taxonomy metadata: 5 regs / 10 domains / 38 subdomains — case-independent)

Run: python3 docs/visualization/build.py
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METHODOLOGY_DIR = ROOT / "methodology-00/PREPROCESSING/Regulation"
CSF_JSON = ROOT / "preproc_out/global/NIST_CSF_2.0_subcategories.json"
OUT = ROOT / "docs/visualization/taxonomy_chain.html"


def _find_taxonomy_csv_dir() -> Path:
    """Locate the case folder containing the taxonomy CSVs (00_regulations.csv,
    01_domains.csv, 02_subdomains.csv) under <root>/cases/. The taxonomy is
    case-independent metadata, so any case folder with the standard structure
    is acceptable."""
    candidates = []
    cases_root = ROOT / "cases"
    if cases_root.exists():
        for case_dir in sorted(cases_root.iterdir()):
            phase1 = case_dir / "data" / "phase1"
            if (phase1 / "01_domains.csv").exists() and (phase1 / "02_subdomains.csv").exists():
                candidates.append(phase1)
    if not candidates:
        raise FileNotFoundError(
            "No case folder with data/phase1/{01_domains,02_subdomains}.csv found under cases/"
        )
    return candidates[0]


CASE_TAXONOMY = _find_taxonomy_csv_dir()

REGULATIONS = ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]

REG_COLORS = {
    "GDPR": "#FF6B6B",
    "CRA": "#4ECDC4",
    "NIS2": "#FFD93D",
    "DORA": "#6C5CE7",
    "AI_Act": "#A8E6CF",
}

CSV_REG_ID_MAP = {
    "GDPR": "GDPR",
    "CRA": "CRA",
    "NIS2": "NIS2",
    "DORA": "DORA",
    "AIACT": "AI_Act",
}


def load_regulations_data() -> list[dict]:
    regs = []
    with open(CASE_TAXONOMY / "00_regulations.csv") as f:
        for r in csv.DictReader(f):
            canonical = CSV_REG_ID_MAP.get(r["regulationId"], r["regulationId"])
            regs.append(
                {
                    "id": canonical,
                    "name": r["fullName"],
                    "shortName": r["shortName"],
                    "type": r["type"],
                    "effectiveDate": r["effectiveDate"],
                    "primaryFocus": r["primaryFocus"],
                    "color": REG_COLORS.get(canonical, "#888"),
                }
            )
    return regs


def load_domains() -> list[dict]:
    domains = []
    with open(CASE_TAXONOMY / "01_domains.csv") as f:
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
    with open(CASE_TAXONOMY / "02_subdomains.csv") as f:
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


def _extract_list(value: str) -> list[str]:
    """Extract bare identifiers from a YAML inline list like '[A, B, C]'."""
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,\s]+", value.strip("[]")) if item.strip()]


def _extract_article_ref(article_ref: str) -> str:
    """Pull the leading 'Art. X(Y)' prefix from a long article_ref string."""
    if not article_ref:
        return ""
    m = re.match(r"^(Art\.\s*\d+(?:\([\w\d()–\-]+\))*)", article_ref.strip())
    return m.group(1) if m else article_ref.strip()


def _parse_sr_block(block: str, regulation: str) -> dict | None:
    sr_id_match = re.search(r"sr_id:\s*(\S+)", block)
    if not sr_id_match:
        return None
    sr_id = sr_id_match.group(1)

    title_match = re.search(r'title:\s*"([^"]+)"', block)
    title = title_match.group(1) if title_match else ""

    if not title:
        title_match = re.search(r"title:\s*'([^']+)'", block)
        if title_match:
            title = title_match.group(1)

    clauses = re.findall(r"clause_id:\s*([^,\s]+),", block)
    article_refs_raw = re.findall(r'article_ref:\s*"([^"]+)"', block)
    article_refs = [_extract_article_ref(a) for a in article_refs_raw]

    sub_domain_match = re.search(r"sub_domain:\s*\[([^\]]+)\]", block)
    subdomains = _extract_list(sub_domain_match.group(1)) if sub_domain_match else []

    csf_ids: list[str] = []
    csf_section = re.search(
        r"nist_csf_mapping:\s*\n(.*?)(?=\n[a-z_]+\s*:|\Z)", block, re.DOTALL
    )
    if csf_section:
        csf_ids = re.findall(r"id:\s*([A-Z]+\.[A-Z]+-\d+),", csf_section.group(1))

    applies_match = re.search(r"applies_to_role:\s*\[([^\]]+)\]", block)
    applies_to = _extract_list(applies_match.group(1)) if applies_match else []

    obligation_match = re.search(r"obligation_type:\s*\[([^\]]+)\]", block)
    obligation_type = _extract_list(obligation_match.group(1)) if obligation_match else []

    return {
        "id": sr_id,
        "regulation": regulation,
        "title": title,
        "clauses": clauses,
        "articleRefs": article_refs,
        "subdomains": subdomains,
        "csfIds": csf_ids,
        "appliesTo": applies_to,
        "obligationType": obligation_type,
    }


def load_security_rules() -> list[dict]:
    """Load 282 SecurityRules from the 5 methodology SR files."""
    rules = []
    for reg in REGULATIONS:
        path = METHODOLOGY_DIR / reg / "02_SecurityRules_NIST.md"
        text = path.read_text(encoding="utf-8")
        blocks = re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL)
        for block in blocks:
            sr = _parse_sr_block(block, reg)
            if sr:
                rules.append(sr)
    return rules


def load_csf() -> list[dict]:
    with open(CSF_JSON) as f:
        csf = json.load(f)
    return [
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


def main() -> None:
    regulations = load_regulations_data()
    domains = load_domains()
    subdomains = load_subdomains()
    rules = load_security_rules()
    csf_subs = load_csf()

    csf_in_use = {c for r in rules for c in r["csfIds"]}

    data = {
        "regulations": regulations,
        "domains": domains,
        "subdomains": subdomains,
        "securityRules": rules,
        "csfSubcategories": csf_subs,
        "stats": {
            "regulations": len(regulations),
            "domains": len(domains),
            "subdomains": len(subdomains),
            "securityRules": len(rules),
            "aiActSRs": len([r for r in rules if r["regulation"] == "AI_Act"]),
            "csfSubcategories": len(csf_subs),
            "csfInUse": len(csf_in_use),
        },
        "buildMeta": {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "version": "case-independent",
            "source": "methodology-00/PREPROCESSING/Regulation/{REG}/02_SecurityRules_NIST.md (5 files, 282 SRs)",
            "notes": "Case-INDEPENDENT view (methodology regulatory baseline). AI Act reaches 36 distinct CSF controls per methodology; replaces the previous case-specific derived view.",
        },
    }

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"  Generated at: {data['buildMeta']['generatedAt']}  ({data['buildMeta']['version']})")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB)")
    print(f"  Regulations: {len(regulations)}")
    print(f"  Domains: {len(domains)}")
    print(f"  Subdomains: {len(subdomains)}")
    print(f"  SecurityRules: {len(rules)}")
    print(f"  AI Act SRs: {data['stats']['aiActSRs']}")
    print(f"  CSF subcategories: {len(csf_subs)}")
    print(f"  CSF in use: {data['stats']['csfInUse']}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AEGIS-KG — Taxonomy Chain Viewer (case-INDEPENDENT)</title>
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
    .filter-group .solo-btn {
      margin-left: 6px; padding: 2px 7px; font-size: 10px;
      background: transparent; color: var(--accent); border: 1px solid var(--accent);
      border-radius: 4px; cursor: pointer; opacity: 0.6;
      transition: opacity 0.15s;
    }
    .filter-group .solo-btn:hover { opacity: 1; background: var(--accent); color: var(--bg); }
    .filter-group label { justify-content: flex-start; }
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

    .build-banner {
      width: 100%; margin-top: 8px; padding: 6px 14px; font-size: 12px;
      background: rgba(78,205,196,0.12); border: 1px solid rgba(78,205,196,0.35);
      border-radius: 6px; color: var(--accent); font-weight: 600;
      display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    }
    .build-banner .badge {
      background: var(--accent); color: var(--bg); padding: 2px 8px;
      border-radius: 4px; font-size: 10px; letter-spacing: 0.5px;
    }
    .build-banner .meta { color: var(--fg-dim); font-weight: 400; font-size: 11px; }

    footer {
      padding: 8px 24px; background: var(--panel); border-top: 1px solid var(--border);
      font-size: 11px; color: var(--fg-dim); display: flex; justify-content: space-between;
    }

    #sunburst-nav {
      display: flex;
      align-items: center;
      padding: 8px 12px;
      background: var(--panel-2);
      border-bottom: 1px solid var(--border);
      min-height: 36px;
    }
    #sunburst-nav[hidden] { display: none; }
    .bc-item {
      cursor: pointer;
      color: var(--accent);
      padding: 2px 6px;
      border-radius: 4px;
      transition: background 0.15s;
    }
    .bc-item:hover {
      background: rgba(78, 205, 196, 0.15);
    }
    .bc-sep {
      color: var(--fg-dim);
      margin: 0 4px;
    }
    .bc-current {
      color: var(--fg);
      font-weight: 600;
      padding: 2px 6px;
    }
  </style>
</head>
<body>
  <header>
    <h1>AEGIS-KG — Taxonomy Chain Viewer <small>5 regs · 282 SRs · methodology</small></h1>
    <div class="tabs" id="mode-tabs">
      <button class="tab active" data-mode="sankey">Sankey</button>
      <button class="tab" data-mode="tree">Tree</button>
      <button class="tab" data-mode="heatmap">Heatmap</button>
      <button class="tab" data-mode="sunburst">Sunburst</button>
    </div>
    <div class="build-banner" id="build-banner"></div>
  </header>

  <main>
    <aside>
      <h3>Filters</h3>
      <div class="filter-group" id="reg-filter"></div>
      <h3>Search</h3>
      <input type="search" id="search" placeholder="Search subdomains, SRs, CSF..." />

      <div class="stats" id="stats"></div>
    </aside>

    <section>
      <div id="sunburst-nav" style="display:none; padding:8px 12px; background:var(--panel-2); border-bottom:1px solid var(--border);">
        <button id="sunburst-back" style="padding:4px 10px; background:var(--panel); color:var(--accent); border:1px solid var(--accent); border-radius:4px; cursor:pointer; font-size:12px;">← Back</button>
        <span id="sunburst-breadcrumb" style="margin-left:12px; font-size:13px;"></span>
        <span id="sunburst-hint" style="margin-left:16px; font-size:11px; color:var(--fg-dim);"></span>
      </div>
      <div id="viz"></div>
    </section>

    <div class="detail" id="detail">
      <div class="empty">Click a node in the visualization to inspect its details, upstream regulations, and downstream CSF mappings.</div>
    </div>
  </main>

  <footer>
    <span>Library: Apache ECharts v6.1 · Data: methodology regulatory baseline (282 SRs from 5 regulation SR files) · Case-INDEPENDENT</span>
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
      sunburstPath: [],   // ['GDPR', 'D-04', 'D-04.3'] — empty = Level 0 (5 regulations)
                         // Other modes force this to [] when switched
      chart: null,
    };

    const regFilterEl = document.getElementById('reg-filter');

    function renderBuildBanner() {
      const meta = DATA.buildMeta;
      if (!meta) return;
      const banner = document.getElementById('build-banner');
      banner.innerHTML = `
        <span class="badge">${meta.version || 'BUILT'}</span>
        <span>${meta.notes || 'Live build'}</span>
        <span class="meta">Generated: ${meta.generatedAt} · If you see old data, hard-refresh (Ctrl+Shift+R)</span>
      `;
    }

    function renderFilters() {
      regFilterEl.innerHTML = `
        <label><strong style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--fg-dim);">Regulations</strong></label>
        <button id="reset-regs" style="margin:4px 0 8px 0;padding:4px 8px;font-size:10px;background:var(--panel-2);color:var(--fg-dim);border:1px solid var(--border);border-radius:4px;cursor:pointer;">Reset filters</button>
      `;
      DATA.regulations.forEach(r => {
        const srCount = DATA.securityRules.filter(sr => sr.regulation === r.id).length;
        const label = document.createElement('label');
        label.innerHTML = `
          <input type="checkbox" data-reg="${r.id}" ${STATE.activeRegs.has(r.id) ? 'checked' : ''} />
          <span class="swatch" style="background:${r.color}"></span>
          <span>${r.shortName}</span>
          <span class="count">${srCount}</span>
          <button class="solo-btn" data-solo="${r.id}" title="Show only ${r.shortName}">solo</button>`;
        regFilterEl.appendChild(label);
      });
      regFilterEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.addEventListener('change', e => {
          const regId = e.target.dataset.reg;
          if (e.target.checked) STATE.activeRegs.add(regId);
          else STATE.activeRegs.delete(regId);
          renderFilters();
          // If we're in sunburst and the selected regulation is no longer active, reset
          if (STATE.mode === 'sunburst' && STATE.sunburstPath.length > 0) {
            const pathRegId = DATA.regulations.find(r => r.shortName === STATE.sunburstPath[0])?.id;
            if (!pathRegId || !STATE.activeRegs.has(pathRegId)) {
              STATE.sunburstPath = [];
            }
          }
          render();
        });
      });
      regFilterEl.querySelectorAll('.solo-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          e.preventDefault();
          const regId = btn.dataset.solo;
          STATE.activeRegs = new Set([regId]);
          renderFilters();
          render();
        });
      });
      document.getElementById('reset-regs').addEventListener('click', e => {
        STATE.activeRegs = new Set(DATA.regulations.map(r => r.id));
        renderFilters();
        render();
      });
    }

    function renderStats() {
      const s = DATA.stats;
      const byReg = {};
      DATA.securityRules.forEach(r => {
        byReg[r.regulation] = (byReg[r.regulation] || 0) + 1;
      });
      const regBreakdown = DATA.regulations
        .map(r => `${r.shortName}=${byReg[r.id] || 0}`)
        .join(' + ');
      const csfPct = Math.round(100 * s.csfInUse / s.csfSubcategories);
      document.getElementById('stats').innerHTML = `
        <strong>${s.regulations}</strong> regulations in scope (methodology baseline)<br/>
        <strong>${s.domains}</strong> domains · <strong>${s.subdomains}</strong> sub-domains<br/>
        <strong>${s.securityRules}</strong> SecurityRules (${regBreakdown})<br/>
        <strong>${s.csfInUse}/${s.csfSubcategories}</strong> CSF controls driven by SRs (${csfPct}%)
      `;
    }

    function visibleRules() {
      return DATA.securityRules.filter(r => STATE.activeRegs.has(r.regulation));
    }

    function visibleSdIds() {
      const ids = new Set();
      visibleRules().forEach(r => r.subdomains.forEach(sd => ids.add(sd)));
      return ids;
    }

    function matchesSearch(text) {
      if (!STATE.search) return true;
      const q = STATE.search.toLowerCase();
      return text.toLowerCase().includes(q);
    }

    // Natural sort for D-XX.Y style IDs (D-01.1 < D-01.2 < D-01.10 < D-02.1)
    function naturalIdSort(a, b) {
      return a.localeCompare(b, undefined, {numeric: true, sensitivity: 'base'});
    }

    // CSF Function order: GV, ID, PR, DE, RS, RC (per NIST CSF 2.0 official ordering)
    const FUNCTION_ORDER = {GV: 0, ID: 1, PR: 2, DE: 3, RS: 4, RC: 5};

    // CSF color by Function (6 distinct colors for instant visual recognition)
    const CSF_COLOR = {
      GV: '#4ecdc4',  // teal
      ID: '#6c5ce7',  // lilac
      PR: '#ffd93d',  // amber
      DE: '#ff6b6b',  // coral
      RS: '#a8e6cf',  // mint
      RC: '#f9a8d4',  // pink
    };

    function csfOrderKey(c) {
      return [FUNCTION_ORDER[c.function] ?? 99, c.categoryId || '', c.id || ''];
    }
    function csfCompare(a, b) {
      const ka = csfOrderKey(a), kb = csfOrderKey(b);
      return (ka[0]-kb[0]) || ka[1].localeCompare(kb[1]) || ka[2].localeCompare(kb[2]);
    }

    function renderSankey() {
      const rules = visibleRules();
      const sdToDomain = {};
      DATA.subdomains.forEach(sd => { sdToDomain[sd.id] = sd.domainId; });

      const reg2dom = {};
      const dom2sd = {};
      const sd2csf = {};
      rules.forEach(r => {
        r.subdomains.forEach(sd => {
          const dom = sdToDomain[sd];
          if (!dom) return;
          const rdKey = `${r.regulation}|||${dom}`;
          reg2dom[rdKey] = (reg2dom[rdKey] || 0) + 1;
          const dsKey = `${dom}|||${sd}`;
          dom2sd[dsKey] = (dom2sd[dsKey] || 0) + 1;
        });
        r.subdomains.forEach(sd => {
          r.csfIds.forEach(csf => {
            const sdKey = `${sd}|||${csf}`;
            sd2csf[sdKey] = (sd2csf[sdKey] || 0) + 1;
          });
        });
      });

      const visibleDomIds = new Set(Object.keys(reg2dom).map(k => k.split('|||')[1]));
      const visibleSdIds = new Set(Object.keys(dom2sd).map(k => k.split('|||')[1]));
      const visibleCsfIds = new Set(Object.keys(sd2csf).map(k => k.split('|||')[1]));

      const regNames = {};
      const sdNames = {};
      const domNames = {};
      DATA.regulations.forEach(r => regNames[r.id] = r.shortName);
      DATA.subdomains.forEach(sd => sdNames[sd.id] = `${sd.id} ${sd.name}`);
      DATA.domains.forEach(d => domNames[d.id] = `${d.id} ${d.name}`);
      const csfById = Object.fromEntries(DATA.csfSubcategories.map(s => [s.id, s]));

      const regWeight = {};
      const domWeight = {};
      const sdWeight = {};
      const csfWeight = {};
      rules.forEach(r => {
        r.subdomains.forEach(sd => {
          const dom = sdToDomain[sd];
          if (!dom) return;
          regWeight[r.regulation] = (regWeight[r.regulation] || 0) + 1;
          domWeight[dom] = (domWeight[dom] || 0) + 1;
          sdWeight[sd] = (sdWeight[sd] || 0) + 1;
        });
        r.csfIds.forEach(csf => {
          csfWeight[csf] = (csfWeight[csf] || 0) + 1;
        });
      });

      const nodes = [];
      const nodeIdx = {};
      function addNode(name, depth, itemStyle, value) {
        if (nodeIdx[name] !== undefined) return;
        nodeIdx[name] = nodes.length;
        nodes.push({ name, depth, itemStyle, value });
      }
      DATA.regulations.filter(r => STATE.activeRegs.has(r.id)).forEach(r => {
        nodes.push({ name: regNames[r.id], depth: 0, itemStyle: { color: r.color, borderColor: r.color }, value: regWeight[r.id] || 0 });
      });
      DATA.domains
        .filter(d => visibleDomIds.has(d.id))
        .slice()
        .sort((a, b) => naturalIdSort(a.id, b.id))
        .forEach(d => {
          nodes.push({ name: domNames[d.id], depth: 1, itemStyle: { color: '#5a6378', borderColor: '#5a6378' }, value: domWeight[d.id] || 0 });
        });
      DATA.subdomains
        .filter(sd => visibleSdIds.has(sd.id))
        .slice()
        .sort((a, b) => naturalIdSort(a.id, b.id))
        .forEach(sd => {
          nodes.push({ name: sdNames[sd.id], depth: 2, itemStyle: { color: '#6c5ce7', borderColor: '#6c5ce7' }, value: sdWeight[sd.id] || 0 });
        });
      DATA.csfSubcategories
        .filter(s => visibleCsfIds.has(s.id))
        .slice()
        .sort(csfCompare)
        .forEach(s => {
          const color = CSF_COLOR[s.function] || '#4ecdc4';
          nodes.push({ name: s.id, depth: 3, itemStyle: { color, borderColor: color }, value: csfWeight[s.id] || 0 });
        });

      const links = [];
      Object.entries(reg2dom).forEach(([k, v]) => {
        const [reg, dom] = k.split('|||');
        links.push({ source: regNames[reg], target: domNames[dom], value: v });
      });
      Object.entries(dom2sd).forEach(([k, v]) => {
        const [dom, sd] = k.split('|||');
        links.push({ source: domNames[dom], target: sdNames[sd], value: v });
      });
      Object.entries(sd2csf).forEach(([k, v]) => {
        const [sd, csf] = k.split('|||');
        links.push({ source: sdNames[sd], target: csf, value: v });
      });

      return {
        tooltip: { trigger: 'item', triggerOn: 'mousemove',
          formatter: p => {
            if (p.dataType === 'edge') {
              return `<b>${p.data.source}</b> → <b>${p.data.target}</b><br/>Weight: ${p.data.value} SR(s)`;
            }
            const reg = DATA.regulations.find(r => regNames[r.id] === p.name);
            if (reg) return `<b>${reg.shortName}</b><br/>${reg.name}<br/><i>${reg.primaryFocus}</i>`;
            const dom = DATA.domains.find(d => domNames[d.id] === p.name);
            if (dom) {
              const regSet = new Set();
              rules.forEach(r => {
                if (r.subdomains.some(sd => sdToDomain[sd] === dom.id)) regSet.add(r.regulation);
              });
              const subInDom = DATA.subdomains
                .filter(sd => sd.domainId === dom.id && visibleSdIds.has(sd.id))
                .slice()
                .sort((a, b) => naturalIdSort(a.id, b.id));
              const regShorts = [...regSet].map(rid => DATA.regulations.find(r => r.id === rid)?.shortName).filter(Boolean);
              return `<b>${dom.id} ${dom.name}</b><br/><i>${dom.description}</i><br/>Regulations: ${regShorts.join(', ')}<br/>Active subdomains: ${subInDom.length}`;
            }
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
          layoutIterations: 32,
        }],
      };
    }

    function renderTree() {
      const rules = visibleRules();
      const sdIds = new Set();
      rules.forEach(r => r.subdomains.forEach(sd => sdIds.add(sd)));
      const csfById = Object.fromEntries(DATA.csfSubcategories.map(s => [s.id, s]));

      const tree = [];
      DATA.domains
        .slice()
        .sort((a, b) => naturalIdSort(a.id, b.id))
        .forEach(d => {
          const sdList = DATA.subdomains
            .filter(sd => sd.domainId === d.id && sdIds.has(sd.id))
            .slice()
            .sort((a, b) => naturalIdSort(a.id, b.id));
          if (!sdList.length) return;
          const domainNode = { name: d.name, children: [] };
          sdList.forEach(sd => {
            const srList = rules
              .filter(r => r.subdomains.includes(sd.id))
              .filter(r => matchesSearch(r.title) || matchesSearch(r.id))
              .slice()
              .sort((a, b) => a.id.localeCompare(b.id));
            const filtered = srList.length ? srList : [{ id: '—', title: '(no SR mapped)' }];
            domainNode.children.push({
              name: `${sd.id} ${sd.name}`,
              children: filtered.map(sr => ({ name: sr.id, value: sr.title }))
            });
          });
          tree.push(domainNode);
        });

      return {
        tooltip: { trigger: 'item', triggerOn: 'mousemove',
          formatter: p => {
            if (!p.data) return '';
            const sr = DATA.securityRules.find(s => s.id === p.name);
            if (sr) return `<b>${sr.id}</b><br/>${sr.title}<br/><i>${sr.regulation}</i>`;
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
          initialTreeDepth: 3,
          label: { position: 'left', verticalAlign: 'middle', align: 'right',
                   fontSize: 11, color: '#e1e7f0', formatter: '{b}' },
          leaves: { label: { position: 'right', align: 'left' } },
          lineStyle: { color: '#4ecdc4', curveness: 0.5, width: 1, opacity: 0.6 },
          itemStyle: { color: '#6c5ce7', borderColor: '#4ecdc4' },
          emphasis: { focus: 'descendant', itemStyle: { color: '#4ecdc4' } },
        }],
      };
    }

    function renderHeatmap() {
      const rules = visibleRules();
      const sdIds = new Set();
      rules.forEach(r => r.subdomains.forEach(sd => sdIds.add(sd)));
      const xAxis = DATA.subdomains
        .filter(sd => sdIds.has(sd.id))
        .slice()
        .sort((a, b) => naturalIdSort(a.id, b.id))
        .map(sd => sd.id);
      const yAxis = DATA.regulations.filter(r => STATE.activeRegs.has(r.id)).map(r => r.shortName);

      const data = [];
      yAxis.forEach((regName, yi) => {
        const regId = DATA.regulations.find(r => r.shortName === regName).id;
        xAxis.forEach((sdId, xi) => {
          const count = rules.filter(r => r.regulation === regId && r.subdomains.includes(sdId)).length;
          if (count > 0) data.push([xi, yi, count]);
        });
      });

      const maxVal = Math.max(1, ...data.map(d => d[2]));

      return {
        tooltip: { position: 'top',
          formatter: p => {
            const sdId = xAxis[p.data[0]];
            const regName = yAxis[p.data[1]];
            const sd = DATA.subdomains.find(s => s.id === sdId);
            return `<b>${regName}</b> → <b>${sdId}</b> ${sd ? sd.name : ''}<br/>${p.data[2]} SR(s) covering this pair`;
          }
        },
        grid: { left: 80, right: 20, top: 30, bottom: 80 },
        xAxis: { type: 'category', data: xAxis, axisLabel: { rotate: 70, fontSize: 10, color: '#e1e7f0' },
                 splitArea: { show: true } },
        yAxis: { type: 'category', data: yAxis, axisLabel: { fontSize: 11, color: '#e1e7f0' },
                 splitArea: { show: true } },
        visualMap: { min: 0, max: maxVal, calculable: true, orient: 'horizontal',
                     left: 'center', bottom: 5, textStyle: { color: '#e1e7f0' },
                     inRange: { color: ['#1a1f2e', '#4ecdc4', '#ffd93d', '#ff6b6b'] } },
        series: [{ type: 'heatmap', data,
          label: { show: true, color: '#0f1419', fontSize: 10, fontWeight: 'bold' },
          itemStyle: { borderColor: '#0f1419', borderWidth: 1 },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(78,205,196,0.5)' } } }],
      };
    }

    function renderSunburst() {
      // Show navigation bar only in sunburst mode
      const nav = document.getElementById('sunburst-nav');
      if (STATE.mode === 'sunburst') {
        nav.style.display = 'flex';
      } else {
        nav.style.display = 'none';
        return null; // hide via empty option
      }

      const path = STATE.sunburstPath;
      let data = [];
      let centerText = 'AEGIS-KG';
      let hintText = '';

      if (path.length === 0) {
        // Level 0: 5 regulations as base
        data = DATA.regulations
          .filter(r => STATE.activeRegs.has(r.id))
          .map(r => {
            // Count SRs per regulation (used for sizing)
            const srCount = DATA.securityRules.filter(s => s.regulation === r.id).length;
            return {
              name: r.shortName,
              value: srCount,
              itemStyle: { color: r.color, borderColor: r.color },
            };
          });
        centerText = 'AEGIS-KG';
        hintText = 'Click a regulation to drill down';
      } else if (path.length === 1) {
        // Level 1: domains under this regulation
        const regId = DATA.regulations.find(r => r.shortName === path[0])?.id;
        const reg = DATA.regulations.find(r => r.id === regId);
        if (!reg) { STATE.sunburstPath = []; return renderSunburst(); }
        centerText = `${reg.shortName} (${path[0]})`;
        hintText = 'Click a domain to drill down';

        // Find domains covered by this regulation (collect from SRs)
        const regSrs = DATA.securityRules.filter(s => s.regulation === regId);
        const domSrCount = {};
        regSrs.forEach(sr => {
          sr.subdomains.forEach(sdId => {
            const sdInfo = DATA.subdomains.find(x => x.id === sdId);
            if (!sdInfo) return;
            const domId = sdInfo.domainId;
            domSrCount[domId] = (domSrCount[domId] || 0) + 1;
          });
        });

        const sortedDomIds = Object.keys(domSrCount).sort(naturalIdSort);
        data = [{
          name: reg.shortName,
          itemStyle: { color: reg.color },
          children: sortedDomIds.map(domId => {
            const d = DATA.domains.find(x => x.id === domId);
            return {
              name: `${d.id} ${d.name}`,
              value: domSrCount[domId],
              itemStyle: { color: '#5a6378', borderColor: '#5a6378' },
            };
          }),
        }];
      } else if (path.length === 2) {
        // Level 2: subdomains under this (reg, domain)
        const regId = DATA.regulations.find(r => r.shortName === path[0])?.id;
        const dom = DATA.domains.find(d => d.id === path[1]);
        if (!regId || !dom) {
          STATE.sunburstPath = path.slice(0, 1);
          return renderSunburst();
        }
        centerText = `${path[0]} › ${dom.id}`;

        // Find subdomains of this domain covered by this regulation
        const regSrs = DATA.securityRules.filter(s => s.regulation === regId);
        const subSrCount = {};
        regSrs.forEach(sr => {
          sr.subdomains.forEach(sdId => {
            const sdInfo = DATA.subdomains.find(x => x.id === sdId);
            if (sdInfo && sdInfo.domainId === dom.id) {
              subSrCount[sdId] = (subSrCount[sdId] || 0) + 1;
            }
          });
        });

        const sortedSubIds = Object.keys(subSrCount).sort(naturalIdSort);
        data = [{
          name: dom.id,
          itemStyle: { color: '#5a6378' },
          children: sortedSubIds.map(sdId => {
            const sd = DATA.subdomains.find(x => x.id === sdId);
            return {
              name: `${sd.id} ${sd.name}`,
              value: subSrCount[sdId],
              itemStyle: { color: '#6c5ce7', borderColor: '#6c5ce7' },
            };
          }),
        }];
        hintText = 'Click a subdomain to see CSF mappings';
      } else if (path.length === 3) {
        // Level 3: CSF controls (grouped by Function) under this (reg, domain, subdomain)
        const regId = DATA.regulations.find(r => r.shortName === path[0])?.id;
        const dom = DATA.domains.find(d => d.id === path[1]);
        const sd = DATA.subdomains.find(x => x.id === path[2]);
        if (!regId || !dom || !sd) {
          STATE.sunburstPath = path.slice(0, 2);
          return renderSunburst();
        }
        centerText = `${sd.id} ${sd.name}`;

        // Find CSF counts via SRs covering (reg, sd)
        const regSrs = DATA.securityRules.filter(s => s.regulation === regId);
        const csfCount = {};
        regSrs.forEach(sr => {
          if (sr.subdomains.includes(sd.id)) {
            sr.csfIds.forEach(csfId => {
              const csf = DATA.csfSubcategories.find(c => c.id === csfId);
              if (csf) {
                const fn = csf.function;
                csfCount[fn] = (csfCount[fn] || 0) + 1;
              }
            });
          }
        });

        const sortedFns = Object.entries(csfCount)
          .sort((a, b) => (FUNCTION_ORDER[a[0]] ?? 99) - (FUNCTION_ORDER[b[0]] ?? 99))
          .map(([fn, n]) => ({
            name: fn,
            value: n,
            itemStyle: { color: CSF_COLOR[fn] || '#888', borderColor: CSF_COLOR[fn] || '#888' },
          }));

        data = [{
          name: sd.id,
          itemStyle: { color: '#6c5ce7' },
          children: sortedFns,
        }];
        hintText = 'CSF controls grouped by Function (GV→ID→PR→DE→RS→RC)';
      }

      // Render breadcrumb
      renderBreadcrumb();
      document.getElementById('sunburst-hint').textContent = hintText;

      return {
        tooltip: { trigger: 'item', formatter: p => `<b>${p.name}</b><br/>${p.value || 0} SR(s)` },
        series: [{
          type: 'sunburst',
          data,
          radius: ['12%', '92%'],
          sort: null,
          emphasis: { focus: 'ancestor' },
          label: {
            color: '#0f1419',
            fontSize: 10,
            fontWeight: 'bold',
            rotate: 'tangential',
            formatter: '{b}\n{c}'
          },
          itemStyle: { borderRadius: 4, borderColor: '#0f1419', borderWidth: 2 },
          levels: [
            {},
            { r0: '12%', r: '30%', label: { fontSize: 13 } },
            { r0: '30%', r: '60%', label: { fontSize: 11 } },
            { r0: '60%', r: '80%', label: { fontSize: 9 } },
            { r0: '80%', r: '92%', label: { fontSize: 9 } },
          ],
        }],
      };
    }

    function renderBreadcrumb() {
      const path = STATE.sunburstPath;
      const bc = document.getElementById('sunburst-breadcrumb');
      const back = document.getElementById('sunburst-back');
      if (!bc) return;

      if (path.length === 0) {
        bc.innerHTML = '<span style="color:var(--fg-dim);">Home (5 regulations)</span>';
        back.style.display = 'none';
        return;
      }

      back.style.display = '';
      const items = ['<span class="bc-item" data-level="0">Home</span>'];
      path.forEach((p, i) => {
        const isLast = (i === path.length - 1);
        items.push('<span class="bc-sep">›</span>');
        if (isLast) {
          items.push(`<span class="bc-current">${p}</span>`);
        } else {
          items.push(`<span class="bc-item" data-level="${i + 1}">${p}</span>`);
        }
      });
      bc.innerHTML = items.join('');

      bc.querySelectorAll('.bc-item').forEach(item => {
        item.onclick = () => {
          const target = parseInt(item.dataset.level);
          STATE.sunburstPath = STATE.sunburstPath.slice(0, target);
          render();
        };
      });

      back.onclick = () => {
        STATE.sunburstPath.pop();
        render();
      };
    }

function renderDetail(nodeId, nodeLabel) {
      const el = document.getElementById('detail');
      if (!nodeId) {
        el.innerHTML = '<div class="empty">Click a node in the visualization to inspect its details, upstream regulations, and downstream CSF mappings.</div>';
        return;
      }
      const reg = DATA.regulations.find(r => r.id === nodeId || r.shortName === nodeId);
      if (reg) {
        const srs = DATA.securityRules.filter(r => r.regulation === reg.id);
        const sdIds = new Set();
        srs.forEach(r => r.subdomains.forEach(sd => sdIds.add(sd)));
        const csfIds = new Set();
        srs.forEach(r => r.csfIds.forEach(c => csfIds.add(c)));
        el.innerHTML = `
          <h2>${reg.shortName}</h2>
          <div class="meta"><span>${reg.name}</span></div>
          <p>${reg.primaryFocus}</p>
          <p><strong>Type:</strong> ${reg.type} · <strong>Effective:</strong> ${reg.effectiveDate}</p>
          <div class="chain">
            <span class="chain-step">${reg.shortName}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${srs.length} SRs</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sdIds.size} subdomains</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csfIds.size} CSF controls</span>
          </div>
          <div class="related">
            <h4>SecurityRules under ${reg.shortName} (${srs.length})</h4>
            <ul>${srs.slice(0, 50).map(sr => `<li data-sr="${sr.id}">${sr.id} — ${sr.title}</li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sr]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sr);
        });
        return;
      }
      const dom = DATA.domains.find(d => d.id === nodeId);
      if (dom) {
        const subInDom = DATA.subdomains.filter(sd => sd.domainId === dom.id);
        const subIds = new Set(subInDom.map(sd => sd.id));
        const visibleSrs = DATA.securityRules.filter(r => STATE.activeRegs.has(r.regulation) && r.subdomains.some(sd => subIds.has(sd)));
        const srs = DATA.securityRules.filter(r => r.subdomains.some(sd => subIds.has(sd)));
        const drivers = [...new Set(srs.map(r => r.regulation))];
        const csfIds = new Set();
        visibleSrs.forEach(r => r.csfIds.forEach(c => csfIds.add(c)));
        const activeSdIds = new Set();
        visibleSrs.forEach(r => r.subdomains.forEach(sd => { if (subIds.has(sd)) activeSdIds.add(sd); }));
        const activeSdList = [...activeSdIds].sort(naturalIdSort);
        el.innerHTML = `
          <h2>${dom.id} — ${dom.name}</h2>
          <div class="meta"><span>Primary driver: ${dom.primaryRegulatoryDriver}</span></div>
          <p>${dom.description}</p>
          <div class="chain">
            <span class="chain-step">${drivers.map(d => DATA.regulations.find(r => r.id === d)?.shortName).join(' + ')}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${srs.length} SRs</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${activeSdList.length} active subdomains</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csfIds.size} CSF controls</span>
          </div>
          <div class="related">
            <h4>Active subdomains within ${dom.id} (${activeSdList.length})</h4>
            <ul>${activeSdList.map(id => {
              const sd = DATA.subdomains.find(s => s.id === id);
              return `<li data-sd="${id}">${id} — ${sd?.name || ''}</li>`;
            }).join('')}</ul>
            <h4>SecurityRules in this domain (${srs.length})</h4>
            <ul>${srs.slice(0, 50).map(sr => `<li data-sr="${sr.id}">${sr.id} — ${sr.title}</li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sd]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sd);
        });
        el.querySelectorAll('li[data-sr]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sr);
        });
        return;
      }
      const sr = DATA.securityRules.find(s => s.id === nodeId);
      if (sr) {
        const csfById = Object.fromEntries(DATA.csfSubcategories.map(s => [s.id, s]));
        const csfList = sr.csfIds.map(id => csfById[id]).filter(Boolean);
        const sdById = Object.fromEntries(DATA.subdomains.map(s => [s.id, s]));
        const sdList = sr.subdomains.map(id => sdById[id]).filter(Boolean);
        const regMeta = DATA.regulations.find(r => r.id === sr.regulation);
        el.innerHTML = `
          <h2>${sr.id}</h2>
          <div class="meta">
            <span><strong>${regMeta ? regMeta.shortName : sr.regulation}</strong></span>
            <span>${sr.appliesTo.join(', ') || '—'}</span>
            <span>${sr.obligationType.join(', ') || '—'}</span>
          </div>
          <p>${sr.title}</p>
          <div class="chain">
            <span class="chain-step">${regMeta ? regMeta.shortName : sr.regulation}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sr.id}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sr.subdomains.length} subdomain(s)</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sr.csfIds.length} CSF control(s)</span>
          </div>
          <div class="related">
            <h4>Source clauses (${sr.clauses.length})</h4>
            <ul>${sr.clauses.map((c, i) => `<li><b>${c}</b>${sr.articleRefs[i] ? ` — ${sr.articleRefs[i]}` : ''}</li>`).join('')}</ul>
            <h4>AEGIS Sub-domains (${sdList.length})</h4>
            <ul>${sdList.map(sd => `<li data-sd="${sd.id}">${sd.id} — ${sd.name}</li>`).join('')}</ul>
            <h4>NIST CSF 2.0 controls (${csfList.length})</h4>
            <ul>${csfList.map(c => `<li data-csf="${c.id}">${c.id} <span style="color:var(--fg-dim)">— ${c.title.slice(0,60)}${c.title.length>60?'…':''}</span></li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sd]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sd);
        });
        el.querySelectorAll('li[data-csf]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.csf);
        });
        return;
      }
      const sd = DATA.subdomains.find(s => s.id === nodeId);
      if (sd) {
        const srs = DATA.securityRules.filter(r => r.subdomains.includes(sd.id));
        const csfIds = new Set();
        srs.forEach(r => r.csfIds.forEach(c => csfIds.add(c)));
        const csfById = Object.fromEntries(DATA.csfSubcategories.map(s => [s.id, s]));
        const csfList = [...csfIds].map(id => csfById[id]).filter(Boolean);
        const drivers = [...new Set(srs.map(r => r.regulation))];
        el.innerHTML = `
          <h2>${sd.id} — ${sd.name}</h2>
          <div class="meta"><span>${sd.domainId} ${DATA.domains.find(d => d.id === sd.domainId)?.name || ''}</span></div>
          <p>${sd.description}</p>
          <p><strong>Keywords:</strong> ${sd.keywords}</p>
          <p><strong>Sole authority:</strong> ${sd.soleAuthority} · <strong>Gap risk:</strong> ${sd.gapRisk}</p>
          <div class="chain">
            <span class="chain-step">${drivers.map(d => DATA.regulations.find(r => r.id === d)?.shortName).join(' + ')}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${srs.length} SRs</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sd.id}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csfList.length} CSF controls</span>
          </div>
          <div class="related">
            <h4>SecurityRules covering this subdomain (${srs.length})</h4>
            <ul>${srs.map(sr => `<li data-sr="${sr.id}"><b>${sr.id}</b> — ${sr.title}</li>`).join('')}</ul>
            <h4>CSF 2.0 Controls (${csfList.length})</h4>
            <ul>${csfList.map(c => `<li data-csf="${c.id}">${c.id} <span style="color:var(--fg-dim)">— ${c.title.slice(0,60)}${c.title.length>60?'…':''}</span></li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sr]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sr);
        });
        el.querySelectorAll('li[data-csf]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.csf);
        });
        return;
      }
      const csf = DATA.csfSubcategories.find(s => s.id === nodeId);
      if (csf) {
        const srs = DATA.securityRules.filter(r => r.csfIds.includes(csf.id));
        const sdIds = new Set();
        srs.forEach(r => r.subdomains.forEach(sd => sdIds.add(sd)));
        const sds = [...sdIds].map(id => DATA.subdomains.find(s => s.id === id)).filter(Boolean);
        const drivers = [...new Set(srs.map(r => r.regulation))];
        el.innerHTML = `
          <h2>${csf.id}</h2>
          <div class="meta"><span>${csf.functionName} / ${csf.categoryName}</span></div>
          <p>${csf.title}</p>
          <div class="chain">
            <span class="chain-step">${drivers.map(d => DATA.regulations.find(r => r.id === d)?.shortName).join(' + ')}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${srs.length} SRs</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${sds.length} subdomains</span>
            <span class="chain-arrow">→</span>
            <span class="chain-step">${csf.id}</span>
          </div>
          <div class="related">
            <h4>SecurityRules mapping to this control (${srs.length})</h4>
            <ul>${srs.map(sr => `<li data-sr="${sr.id}"><b>${sr.id}</b> (${sr.regulation}) — ${sr.title}</li>`).join('')}</ul>
            <h4>AEGIS Sub-domains driving this control (${sds.length})</h4>
            <ul>${sds.map(sd => `<li data-sd="${sd.id}">${sd.id} — ${sd.name}</li>`).join('')}</ul>
          </div>
        `;
        el.querySelectorAll('li[data-sr]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sr);
        });
        el.querySelectorAll('li[data-sd]').forEach(li => {
          li.onclick = () => renderDetail(li.dataset.sd);
        });
        return;
      }
      el.innerHTML = `<div class="empty">Node "${nodeLabel || nodeId}" not found in detail index.</div>`;
    }

    function handleSunburstClick(params) {
      if (!params.name) return;
      const path = STATE.sunburstPath;

      if (path.length === 0) {
        // Level 0 → Level 1: clicked a regulation
        const clicked = DATA.regulations.find(r => r.shortName === params.name);
        if (clicked && STATE.activeRegs.has(clicked.id)) {
          STATE.sunburstPath = [clicked.shortName];
          render();
        }
      } else if (path.length === 1) {
        // Level 1 → Level 2: clicked a domain node (named like "D-04 Incident Response")
        const dom = DATA.domains.find(d => `${d.id} ${d.name}` === params.name);
        if (dom) {
          STATE.sunburstPath = [...path, dom.id];
          render();
        }
      } else if (path.length === 2) {
        // Level 2 → Level 3: clicked a subdomain node (named like "D-04.3 Notification")
        const sub = DATA.subdomains.find(s => `${s.id} ${s.name}` === params.name);
        if (sub) {
          STATE.sunburstPath = [...path, sub.id];
          render();
        }
      }
      // At Level 3 (CSF), no further drill-down; clicks there fall through to detail panel
    }

function attachClickHandler() {
      STATE.chart.on('click', params => {
        // If sunburst mode and path is being built, drill down instead of showing detail
        if (STATE.mode === 'sunburst' && STATE.sunburstPath.length < 3) {
          handleSunburstClick(params);
          return;
        }
        // Otherwise, existing detail handler
        if (!params.name) return;
        let nodeId = null;
        const dom = DATA.domains.find(d => `${d.id} ${d.name}` === params.name);
        if (dom) nodeId = dom.id;
        else {
          const reg = DATA.regulations.find(r => r.shortName === params.name);
          if (reg) nodeId = reg.id;
          else if (DATA.securityRules.some(sr => sr.id === params.name)) {
            nodeId = params.name;
          } else if (DATA.subdomains.some(s => `${s.id} ${s.name}` === params.name)) {
            nodeId = DATA.subdomains.find(s => `${s.id} ${s.name}` === params.name).id;
          } else if (DATA.csfSubcategories.some(s => s.id === params.name)) {
            nodeId = params.name;
          }
        }
        if (nodeId) renderDetail(nodeId, params.name);
      });
    }

    function setMode(mode) {
      STATE.mode = mode;
      // Reset sunburst navigation when leaving sunburst mode
      if (mode !== 'sunburst') {
        STATE.sunburstPath = [];
      }
      document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.dataset.mode === mode);
      });
      render();
    }
    document.getElementById('mode-tabs').addEventListener('click', e => {
      if (e.target.dataset.mode) setMode(e.target.dataset.mode);
    });

    document.getElementById('search').addEventListener('input', e => {
      STATE.search = e.target.value.trim();
      render();
    });

    function render() {
      let option;
      switch (STATE.mode) {
        case 'tree': option = renderTree(); break;
        case 'heatmap': option = renderHeatmap(); break;
        case 'sunburst':
          option = renderSunburst();
          // If sunburst returned null (mode mismatch), fall back to clear chart
          if (!option) { STATE.chart.clear(); return; }
          break;
        default: option = renderSankey();
      }
      STATE.chart.setOption(option, true);
      document.getElementById('footer-info').textContent =
        `Mode: ${STATE.mode} · Active regs: ${STATE.activeRegs.size}/5 · Search: "${STATE.search || '∅'}"`;
    }

    STATE.chart = echarts.init(document.getElementById('viz'), null, { renderer: 'canvas' });
    window.addEventListener('resize', () => STATE.chart.resize());
    attachClickHandler();
    renderFilters();
    renderStats();
    renderBuildBanner();
    render();
  })();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
