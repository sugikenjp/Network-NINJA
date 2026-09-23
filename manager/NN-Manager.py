#!/usr/bin/env python3
"""
Network-NINJA Manager Server
Web UI + REST API + Syslog receiver
"""

import os
import re
import json
import sqlite3
import threading
import socketserver
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "/data/ninja.db")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id          TEXT PRIMARY KEY,
                label       TEXT,
                ip          TEXT,
                last_seen   TEXT,
                status      TEXT DEFAULT 'unknown'
            );
            CREATE TABLE IF NOT EXISTS syslogs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT,
                source_ip   TEXT,
                message     TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            INSERT OR IGNORE INTO settings (key, value) VALUES (
                'filters',
                '{"icmp":true,"tcp80":false,"tcp443":false,"tcp445":false}'
            );
            CREATE TABLE IF NOT EXISTS source_ips (
                ip         TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen  TEXT,
                count      INTEGER DEFAULT 1
            );
        """)

# ---------------------------------------------------------------------------
# Syslog UDP receiver (RFC3164)
# ---------------------------------------------------------------------------

class SyslogHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, _ = self.request
        msg = data.decode("utf-8", errors="replace").strip()
        source_ip = self.client_address[0]
        received_at = datetime.utcnow().isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO syslogs (received_at, source_ip, message) VALUES (?,?,?)",
                (received_at, source_ip, msg)
            )
            conn.execute(
                """INSERT INTO nodes (id, label, ip, last_seen, status)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, status='online'""",
                (source_ip, source_ip, source_ip, received_at, "online")
            )
            # syslog メッセージ中の "from <IP>" を抽出して source_ips に記録
            m = re.search(r'from\s+(\d{1,3}(?:\.\d{1,3}){3})', msg)
            if m:
                observed_ip = m.group(1)
                conn.execute(
                    """INSERT INTO source_ips (ip, first_seen, last_seen, count)
                       VALUES (?, ?, ?, 1)
                       ON CONFLICT(ip) DO UPDATE SET
                         last_seen = excluded.last_seen,
                         count     = count + 1""",
                    (observed_ip, received_at, received_at)
                )

def start_syslog_server():
    port = int(os.environ.get("SYSLOG_PORT", 514))
    try:
        server = socketserver.UDPServer(("0.0.0.0", port), SyslogHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logging.info(f"Syslog UDP server listening on :{port}")
    except PermissionError:
        logging.warning(f"Cannot bind to port {port}. Try 5514 or run as root.")

# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    """Agent calls this every 30s to report liveness."""
    data = request.get_json(silent=True) or {}
    node_id = data.get("node_id") or request.remote_addr
    label   = data.get("label", node_id)
    ip      = data.get("ip", request.remote_addr)
    now     = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO nodes (id, label, ip, last_seen, status)
               VALUES (?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 label=excluded.label,
                 ip=excluded.ip,
                 last_seen=excluded.last_seen,
                 status='online'""",
            (node_id, label, ip, now, "online")
        )
    return jsonify({"status": "ok"})

@app.route("/api/nodes", methods=["GET"])
def list_nodes():
    threshold = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT *, CASE WHEN last_seen >= ? THEN 'online' ELSE 'offline' END AS computed_status FROM nodes",
            (threshold,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/nodes/<node_id>", methods=["DELETE"])
def delete_node(node_id):
    with get_db() as conn:
        conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
    return jsonify({"status": "deleted"})

@app.route("/api/filter", methods=["GET"])
def get_filter():
    """Return the current capture filter configuration."""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='filters'").fetchone()
    if row:
        return jsonify(json.loads(row["value"]))
    return jsonify({"icmp": True, "tcp80": False, "tcp443": False, "tcp445": False})

@app.route("/api/filter", methods=["POST"])
def set_filter():
    """Update the capture filter configuration."""
    data = request.get_json(silent=True) or {}
    filters = {
        "icmp":   bool(data.get("icmp",   True)),
        "tcp80":  bool(data.get("tcp80",  False)),
        "tcp443": bool(data.get("tcp443", False)),
        "tcp445": bool(data.get("tcp445", False)),
    }
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('filters', ?)",
            (json.dumps(filters),)
        )
    return jsonify({"status": "ok"})

@app.route("/api/config/<node_id>", methods=["GET"])
def get_config(node_id):
    """Agent polls this endpoint to receive current filter config."""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='filters'").fetchone()
    filters = json.loads(row["value"]) if row else \
              {"icmp": True, "tcp80": False, "tcp443": False, "tcp445": False}
    return jsonify({"filters": filters})

@app.route("/api/syslogs", methods=["GET"])
def list_syslogs():
    limit  = int(request.args.get("limit", 200))
    search = request.args.get("q", "")
    source = request.args.get("source", "")
    with get_db() as conn:
        query  = "SELECT * FROM syslogs WHERE 1=1"
        params = []
        if search:
            query += " AND message LIKE ?"
            params.append(f"%{search}%")
        if source:
            query += " AND source_ip=?"
            params.append(source)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/syslogs/count", methods=["GET"])
def syslog_count():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM syslogs").fetchone()[0]
    return jsonify({"total": total})

@app.route("/api/source_ips", methods=["GET"])
def list_source_ips():
    """syslog から抽出した送信元 IP 一覧を返す（JSON）。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM source_ips ORDER BY last_seen DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/ipaddress", methods=["GET"])
def ipaddress_text():
    """送信元 IP 一覧をプレーンテキスト（1 行 1 IP）で返す。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ip FROM source_ips ORDER BY last_seen DESC"
        ).fetchall()
    body = "\n".join(r["ip"] for r in rows)
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}

# ---------------------------------------------------------------------------
# Web UI (single-page, served from Flask)
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Network-NINJA Manager</title>
<style>
  :root {
    --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
    --border: #30363d; --text: #e6edf3; --muted: #8b949e;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --blue: #58a6ff; --purple: #bc8cff;
    --font: 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font); font-size: 13px; }

  /* Layout */
  header { background: var(--bg2); border-bottom: 1px solid var(--border);
           padding: 12px 24px; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 15px; font-weight: bold; color: var(--blue); letter-spacing: 2px; }
  header .subtitle { color: var(--muted); font-size: 11px; }
  .badge { background: var(--bg3); border: 1px solid var(--border);
           border-radius: 4px; padding: 2px 8px; font-size: 11px; }
  .badge.live { border-color: var(--green); color: var(--green); }

  nav { background: var(--bg2); border-bottom: 1px solid var(--border);
        display: flex; gap: 0; }
  nav button { background: none; border: none; color: var(--muted); cursor: pointer;
               padding: 10px 20px; font: inherit; font-size: 12px; letter-spacing: 1px;
               border-bottom: 2px solid transparent; transition: all .15s; }
  nav button:hover { color: var(--text); }
  nav button.active { color: var(--blue); border-bottom-color: var(--blue); }

  main { padding: 20px 24px; max-width: 1200px; }

  /* Cards */
  .card { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px;
          padding: 16px; margin-bottom: 16px; }
  .card-title { font-size: 11px; color: var(--muted); letter-spacing: 1px;
                text-transform: uppercase; margin-bottom: 12px; }

  /* Stats bar */
  .stats { display: flex; gap: 16px; margin-bottom: 20px; }
  .stat { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px;
          padding: 12px 20px; flex: 1; }
  .stat .val { font-size: 28px; font-weight: bold; color: var(--blue); }
  .stat .lbl { font-size: 10px; color: var(--muted); margin-top: 2px; }

  /* Table */
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 10px; color: var(--muted); letter-spacing: 1px;
       text-transform: uppercase; padding: 8px 10px; border-bottom: 1px solid var(--border); }
  td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--bg3); }

  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot.online  { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .dot.offline { background: var(--red); }
  .dot.unknown { background: var(--yellow); }

  /* Log stream */
  .log-stream { background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
                height: 420px; overflow-y: auto; padding: 8px; font-size: 12px; }
  .log-line { padding: 3px 0; border-bottom: 1px solid var(--bg3); display: flex; gap: 10px; }
  .log-time { color: var(--muted); min-width: 170px; }
  .log-src  { color: var(--purple); min-width: 120px; }
  .log-msg  { color: var(--text); word-break: break-all; }
  .log-msg .highlight { background: var(--yellow); color: var(--bg); border-radius: 2px; padding: 0 2px; }

  /* Forms */
  .form-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  input, select { background: var(--bg3); border: 1px solid var(--border); color: var(--text);
                  padding: 6px 10px; border-radius: 4px; font: inherit; font-size: 12px; }
  input:focus, select:focus { outline: none; border-color: var(--blue); }
  input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: var(--blue); }

  .btn { border: none; border-radius: 4px; padding: 6px 14px; cursor: pointer;
         font: inherit; font-size: 12px; font-weight: bold; letter-spacing: 1px; transition: opacity .15s; }
  .btn:hover { opacity: .8; }
  .btn-blue   { background: var(--blue);   color: var(--bg); }
  .btn-red    { background: var(--red);    color: #fff; }
  .btn-green  { background: var(--green);  color: var(--bg); }
  .btn-ghost  { background: var(--bg3); color: var(--text); border: 1px solid var(--border); }

  .tag { display: inline-block; background: var(--bg3); border: 1px solid var(--border);
         border-radius: 3px; padding: 1px 6px; font-size: 10px; }

  /* Filter checkboxes */
  .filter-row {
    display: flex; align-items: center; gap: 12px; padding: 10px 14px;
    border: 1px solid var(--border); border-radius: 4px; cursor: pointer;
    transition: border-color .15s;
  }
  .filter-row:hover { border-color: var(--blue); }
  .filter-row.active { border-color: var(--blue); background: rgba(88,166,255,.06); }
  .filter-row .proto-tag {
    display: inline-block; min-width: 90px; text-align: center;
    background: var(--bg3); border: 1px solid var(--border);
    border-radius: 3px; padding: 3px 10px; font-size: 12px; font-weight: bold;
    color: var(--blue);
  }
  .filter-row .proto-desc { color: var(--muted); font-size: 12px; }

  .filter-expr {
    background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
    padding: 12px 14px; font-size: 12px; color: var(--blue);
    font-family: monospace; word-break: break-all; min-height: 40px;
  }

  #toast { position: fixed; bottom: 20px; right: 20px; background: var(--bg2);
           border: 1px solid var(--green); color: var(--green); padding: 10px 18px;
           border-radius: 6px; font-size: 12px; opacity: 0; transition: opacity .3s;
           pointer-events: none; z-index: 999; }
  #toast.show { opacity: 1; }

  .page { display: none; }
  .page.active { display: block; }
</style>
</head>
<body>

<header>
  <h1>◆ NETWORK-NINJA</h1>
  <span class="subtitle">Manager Console</span>
  <span class="badge live" id="hdr-online">● 0 ONLINE</span>
  <span class="badge" id="hdr-logs">0 LOGS</span>
  <span style="margin-left:auto;color:var(--muted);font-size:11px" id="clock"></span>
</header>

<nav>
  <button class="active" onclick="showPage('nodes',this)">[ NODES ]</button>
  <button onclick="showPage('logs',this)">[ SYSLOG ]</button>
  <button onclick="showPage('ips',this)">[ SOURCE IPs ]</button>
  <button onclick="showPage('filter',this)">[ FILTER CONFIG ]</button>
</nav>

<main>

<!-- NODES PAGE -->
<div class="page active" id="page-nodes">
  <div class="stats">
    <div class="stat"><div class="val" id="s-total">0</div><div class="lbl">TOTAL NODES</div></div>
    <div class="stat"><div class="val" style="color:var(--green)" id="s-online">0</div><div class="lbl">ONLINE</div></div>
    <div class="stat"><div class="val" style="color:var(--red)"   id="s-offline">0</div><div class="lbl">OFFLINE</div></div>
    <div class="stat"><div class="val" style="color:var(--purple)" id="s-logs">0</div><div class="lbl">TOTAL LOGS</div></div>
  </div>
  <div class="card">
    <div class="card-title">Registered Nodes</div>
    <table>
      <thead><tr>
        <th>Status</th><th>Node ID</th><th>Label</th><th>IP</th>
        <th>Last Seen (UTC)</th><th>Action</th>
      </tr></thead>
      <tbody id="node-table"></tbody>
    </table>
  </div>
</div>

<!-- SYSLOG PAGE -->
<div class="page" id="page-logs">
  <div class="card">
    <div class="form-row">
      <input id="log-search" placeholder="Search messages..." style="flex:1" oninput="fetchLogs()">
      <input id="log-source" placeholder="Source IP filter" style="width:160px" oninput="fetchLogs()">
      <select id="log-limit" onchange="fetchLogs()">
        <option value="100">100 lines</option>
        <option value="200" selected>200 lines</option>
        <option value="500">500 lines</option>
      </select>
      <button class="btn btn-ghost" onclick="fetchLogs()">↻ Refresh</button>
      <button class="btn btn-blue"  onclick="toggleAutoRefresh()">AUTO</button>
    </div>
    <div class="log-stream" id="log-stream"></div>
  </div>
</div>

<!-- SOURCE IPs PAGE -->
<div class="page" id="page-ips">
  <div class="card">
    <div class="card-title">Observed Source IP Addresses</div>
    <div class="form-row" style="margin-bottom:12px">
      <button class="btn btn-ghost" onclick="fetchSourceIPs()">↻ Refresh</button>
      <span style="color:var(--muted);font-size:11px;margin-left:6px">
        syslog メッセージ中の <span style="color:var(--blue)">"from &lt;IP&gt;"</span> を自動抽出して記録 &nbsp;|&nbsp;
        テキスト形式:
        <a href="/ipaddress" target="_blank" style="color:var(--blue);text-decoration:none">
          /ipaddress
        </a>
      </span>
    </div>
    <table>
      <thead><tr>
        <th>Source IP</th>
        <th>First Seen (UTC)</th>
        <th>Last Seen (UTC)</th>
        <th>Count</th>
      </tr></thead>
      <tbody id="ips-table"></tbody>
    </table>
  </div>
</div>

<!-- FILTER CONFIG PAGE -->
<div class="page" id="page-filter">
  <div class="card">
    <div class="card-title">Capture Filter — applies to all agents</div>
    <div style="color:var(--muted);font-size:12px;margin-bottom:16px;line-height:1.7">
      選択したプロトコルを全 Agent の tcpdump フィルタに追加します。<br>
      変更は Agent が次回ポーリング（60 秒以内）した際に反映されます。
    </div>

    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px">
      <label class="filter-row" id="row-icmp">
        <input type="checkbox" id="f-icmp" onchange="onFilterChange('row-icmp','f-icmp')">
        <span class="proto-tag">ICMP</span>
        <span class="proto-desc">Ping &nbsp;（Echo Request / Echo Reply）</span>
      </label>
      <label class="filter-row" id="row-tcp80">
        <input type="checkbox" id="f-tcp80" onchange="onFilterChange('row-tcp80','f-tcp80')">
        <span class="proto-tag">80 / tcp</span>
        <span class="proto-desc">HTTP</span>
      </label>
      <label class="filter-row" id="row-tcp443">
        <input type="checkbox" id="f-tcp443" onchange="onFilterChange('row-tcp443','f-tcp443')">
        <span class="proto-tag">443 / tcp</span>
        <span class="proto-desc">HTTPS</span>
      </label>
      <label class="filter-row" id="row-tcp445">
        <input type="checkbox" id="f-tcp445" onchange="onFilterChange('row-tcp445','f-tcp445')">
        <span class="proto-tag">445 / tcp</span>
        <span class="proto-desc">SMB</span>
      </label>
    </div>

    <button class="btn btn-blue" onclick="saveFilter()">▶ Apply to All Agents</button>
  </div>

  <div class="card">
    <div class="card-title">Generated tcpdump Filter Expression</div>
    <div class="filter-expr" id="filter-preview">(none)</div>
    <div style="color:var(--muted);font-size:11px;margin-top:10px;line-height:1.7">
      Agent は <span style="color:var(--blue)">GET /api/config/&lt;node_id&gt;</span> を 60 秒ごとにポーリングし、<br>
      フィルタ変更を検知した場合は tcpdump を新しいフィルタで再起動します。
    </div>
  </div>
</div>

</main>

<div id="toast"></div>

<script>
let autoRefresh = false;
let arTimer = null;

function showPage(name, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
  if (name === 'logs')   fetchLogs();
  if (name === 'ips')    fetchSourceIPs();
  if (name === 'filter') fetchFilter();
}

function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'var(--green)' : 'var(--red)';
  t.style.color = ok ? 'var(--green)' : 'var(--red)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Nodes ──────────────────────────────────────────────
async function fetchNodes() {
  const res = await fetch('/api/nodes');
  const nodes = await res.json();
  const tbody = document.getElementById('node-table');
  tbody.innerHTML = '';
  let on = 0, off = 0;
  nodes.forEach(n => {
    const status = n.computed_status || n.status;
    if (status === 'online') on++; else off++;
    const tr = document.createElement('tr');
    const last = n.last_seen ? n.last_seen.replace('T',' ').slice(0,19) : '-';
    tr.innerHTML = `
      <td><span class="dot ${status}"></span>${status.toUpperCase()}</td>
      <td><span class="tag">${n.id}</span></td>
      <td>${n.label || '-'}</td>
      <td>${n.ip || '-'}</td>
      <td style="color:var(--muted)">${last}</td>
      <td><button class="btn btn-red" style="padding:3px 8px;font-size:11px" onclick="deleteNode('${n.id}')">✕</button></td>
    `;
    tbody.appendChild(tr);
  });
  document.getElementById('s-total').textContent   = nodes.length;
  document.getElementById('s-online').textContent  = on;
  document.getElementById('s-offline').textContent = off;
  document.getElementById('hdr-online').textContent = `● ${on} ONLINE`;
}

async function deleteNode(id) {
  if (!confirm(`Delete node ${id}?`)) return;
  await fetch('/api/nodes/' + encodeURIComponent(id), {method:'DELETE'});
  toast('Node removed');
  fetchNodes();
}

// ── Logs ──────────────────────────────────────────────
function hl(text, q) {
  if (!q) return text;
  return text.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi'),
    m => `<span class="highlight">${m}</span>`);
}

async function fetchLogs() {
  const q     = document.getElementById('log-search').value;
  const src   = document.getElementById('log-source').value;
  const limit = document.getElementById('log-limit').value;
  const params = new URLSearchParams({limit, q, source: src});
  const [logsRes, cntRes] = await Promise.all([
    fetch('/api/syslogs?' + params),
    fetch('/api/syslogs/count')
  ]);
  const logs = await logsRes.json();
  const {total} = await cntRes.json();
  document.getElementById('s-logs').textContent   = total;
  document.getElementById('hdr-logs').textContent = total + ' LOGS';
  const stream = document.getElementById('log-stream');
  stream.innerHTML = '';
  logs.forEach(l => {
    const div = document.createElement('div');
    div.className = 'log-line';
    const t = (l.received_at||'').replace('T',' ').slice(0,19);
    div.innerHTML = `
      <span class="log-time">${t}</span>
      <span class="log-src">${l.source_ip}</span>
      <span class="log-msg">${hl(l.message||'', q)}</span>`;
    stream.appendChild(div);
  });
}

function toggleAutoRefresh() {
  autoRefresh = !autoRefresh;
  const btn = event.target;
  if (autoRefresh) {
    btn.style.background = 'var(--green)';
    btn.style.color      = 'var(--bg)';
    arTimer = setInterval(fetchLogs, 3000);
    toast('Auto-refresh ON (3s)');
  } else {
    btn.style.background = '';
    btn.style.color      = '';
    clearInterval(arTimer);
    toast('Auto-refresh OFF');
  }
}

// ── Source IPs ──────────────────────────────────────────
async function fetchSourceIPs() {
  const res   = await fetch('/api/source_ips');
  const ips   = await res.json();
  const tbody = document.getElementById('ips-table');
  tbody.innerHTML = '';
  if (!ips.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center">No data yet</td></tr>';
    return;
  }
  ips.forEach(r => {
    const tr    = document.createElement('tr');
    const first = (r.first_seen || '').replace('T',' ').slice(0,19);
    const last  = (r.last_seen  || '').replace('T',' ').slice(0,19);
    tr.innerHTML = `
      <td style="color:var(--blue);font-family:monospace">${r.ip}</td>
      <td style="color:var(--muted)">${first || '-'}</td>
      <td style="color:var(--muted)">${last  || '-'}</td>
      <td>${r.count}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Filter Config ──────────────────────────────────────
async function fetchFilter() {
  const res  = await fetch('/api/filter');
  const data = await res.json();
  const map = {icmp: 'f-icmp', tcp80: 'f-tcp80', tcp443: 'f-tcp443', tcp445: 'f-tcp445'};
  const rows = {icmp: 'row-icmp', tcp80: 'row-tcp80', tcp443: 'row-tcp443', tcp445: 'row-tcp445'};
  for (const [key, cbId] of Object.entries(map)) {
    const cb = document.getElementById(cbId);
    cb.checked = !!data[key];
    document.getElementById(rows[key]).classList.toggle('active', cb.checked);
  }
  updateFilterPreview();
}

function onFilterChange(rowId, cbId) {
  document.getElementById(rowId).classList.toggle('active',
    document.getElementById(cbId).checked);
  updateFilterPreview();
}

function updateFilterPreview() {
  const parts = [];
  if (document.getElementById('f-icmp').checked)   parts.push('(icmp[0] = 8 or icmp[0] = 0)');
  if (document.getElementById('f-tcp80').checked)  parts.push('tcp port 80');
  if (document.getElementById('f-tcp443').checked) parts.push('tcp port 443');
  if (document.getElementById('f-tcp445').checked) parts.push('tcp port 445');
  document.getElementById('filter-preview').textContent =
    parts.length ? parts.join(' or ') : '(none selected — agents will use default ICMP filter)';
}

async function saveFilter() {
  const payload = {
    icmp:   document.getElementById('f-icmp').checked,
    tcp80:  document.getElementById('f-tcp80').checked,
    tcp443: document.getElementById('f-tcp443').checked,
    tcp445: document.getElementById('f-tcp445').checked,
  };
  const res = await fetch('/api/filter', {
    method:  'POST',
    headers: {'Content-Type': 'application/json'},
    body:    JSON.stringify(payload),
  });
  toast(res.ok ? 'Filter saved — agents will update within 60 s' : 'Save failed', res.ok);
}

// ── Clock + polling ──────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent = new Date().toUTCString().slice(0,25);
}
setInterval(updateClock, 1000);
updateClock();
setInterval(fetchNodes, 15000);
fetchNodes();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    start_syslog_server()
    port = int(os.environ.get("WEB_PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
