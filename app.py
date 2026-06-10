#!/usr/bin/env python3
"""
VulnBank v2 — Deliberately Vulnerable Web Application
Covers ALL 9 scanner modules:
  SQLi, XSS (reflected+stored), CSRF, Open Redirect,
  Directory Traversal, Security Headers, SSRF, XXE, IDOR
FOR EDUCATIONAL / DEMO PURPOSES ONLY
"""

import os, sqlite3, lxml.etree as ET
from flask import Flask, request, render_template_string, redirect, make_response
import requests as req

app = Flask(__name__)
app.secret_key = "vulnbank-hardcoded-secret"

DB = os.environ.get("DB_PATH", "vulnbank.db")

# ─── DB SETUP ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            balance REAL DEFAULT 1000.0,
            role TEXT DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT,
            body TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_user TEXT,
            amount REAL,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO users VALUES(1,'admin','Admin@123','admin@vulnbank.io',99999,'admin');
        INSERT OR IGNORE INTO users VALUES(2,'alice','Alice@456','alice@vulnbank.io',5000,'user');
        INSERT OR IGNORE INTO users VALUES(3,'bob','Bob@789','bob@vulnbank.io',1200,'user');
        INSERT OR IGNORE INTO users VALUES(4,'charlie','Charlie@000','charlie@vulnbank.io',300,'user');
        INSERT OR IGNORE INTO messages(author,body) VALUES('admin','Welcome to VulnBank! Your account is active.');
    """)
    conn.commit()
    conn.close()
    os.makedirs("userfiles", exist_ok=True)
    with open("userfiles/readme.txt","w") as f:
        f.write("VulnBank user files directory.\nTry: ?file=../app.py or ?file=../../../etc/passwd")

# ─── SHARED LAYOUT ────────────────────────────────────────────────────────────
CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
nav{background:#161b22;border-bottom:1px solid #30363d;padding:12px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.logo{color:#58a6ff;font-weight:700;font-size:1.2em;text-decoration:none}
nav a{color:#8b949e;text-decoration:none;font-size:13px;margin-left:14px}
nav a:hover{color:#e6edf3}
.wrap{max-width:920px;margin:32px auto;padding:0 18px}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:26px;margin-bottom:20px}
.card h2{color:#58a6ff;margin-bottom:16px;font-size:1.05em;font-weight:600}
label{font-size:12px;color:#8b949e;display:block;margin-bottom:4px}
input,textarea,select{width:100%;padding:9px 11px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:13px;margin-bottom:12px}
input:focus,textarea:focus{outline:none;border-color:#58a6ff}
.btn{padding:9px 18px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;display:inline-block;text-decoration:none}
.btn-g{background:#238636;color:#fff} .btn-b{background:#1f6feb;color:#fff} .btn-r{background:#da3633;color:#fff}
.ok{background:#1a3a2a;border:1px solid #238636;color:#3fb950;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:13px}
.err{background:#3a1a1a;border:1px solid #da3633;color:#f85149;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:13px}
.info{background:#1a2a3a;border:1px solid #1f6feb;color:#58a6ff;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:13px}
.warn{background:#2a2200;border:1px solid #d29922;color:#e3b341;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#21262d;color:#8b949e;padding:9px 11px;text-align:left;font-weight:500}
td{padding:9px 11px;border-top:1px solid #21262d}
code{background:#21262d;padding:1px 6px;border-radius:4px;font-size:12px;color:#f85149}
pre{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:14px;overflow:auto;max-height:320px;font-size:12px;color:#3fb950;white-space:pre-wrap;word-break:break-all}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.vuln-badge{background:#3a1a1a;border:1px solid #da3633;border-radius:6px;padding:12px;font-size:12px}
.vuln-badge b{color:#f85149;display:block;margin-bottom:4px}
.vuln-badge span{color:#8b949e}
</style>
"""

def nav(active=""):
    links = [
        ("/","Home"),("/login","Login"),("/search","Search Users"),
        ("/messages","Messages"),("/transfer","Transfer"),
        ("/profile","Profile"),("/fetch","Fetch URL"),
        ("/files","File Viewer"),("/api/xml","XML API"),
        ("/redirect","Redirect"),("/admin","Admin"),
    ]
    items = "".join(f'<a href="{u}" style="{"color:#e6edf3" if active==u else ""}">{n}</a>' for u,n in links)
    return f'<nav><a class="logo" href="/">🏦 VulnBank</a><div>{items}</div></nav>'

def page(body, title="VulnBank", active=""):
    return CSS + nav(active) + f'<div class="wrap">{body}</div>'

# ─── HOME ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    vulns = [
        ("SQL Injection", "/login — try admin'--"),
        ("Reflected XSS", "/search?q=<script>alert(1)</script>"),
        ("Stored XSS", "/messages — post <img src=x onerror=alert(1)>"),
        ("CSRF", "/transfer — no token on form"),
        ("IDOR", "/profile?id=2 — no auth check"),
        ("SSRF", "/fetch?url=http://169.254.169.254/latest/meta-data/"),
        ("Directory Traversal", "/files?file=../../../etc/passwd"),
        ("XXE Injection", "/api/xml — POST application/xml"),
        ("Open Redirect", "/redirect?url=https://evil.com"),
        ("No Security Headers", "Inspect any response — no CSP/HSTS/X-Frame"),
    ]
    cards = "".join(f'<div class="vuln-badge"><b>{v[0]}</b><span>{v[1]}</span></div>' for v in vulns)
    body = f"""
    <div class="card" style="text-align:center;padding:44px 28px">
      <div style="font-size:2.4em;margin-bottom:10px">🏦</div>
      <h1 style="color:#58a6ff;font-size:1.8em;margin-bottom:8px">VulnBank Demo</h1>
      <p style="color:#8b949e;margin-bottom:6px">Intentionally Vulnerable Web Application</p>
      <p style="color:#f85149;font-size:12px;margin-bottom:28px">⚠️ FOR SECURITY SCANNER DEMO ONLY — NEVER USE IN PRODUCTION</p>
      <div class="grid">{cards}</div>
    </div>"""
    return page(body, active="/")

# ─── LOGIN — SQL INJECTION ─────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username","")
        p = request.form.get("password","")
        conn = get_db()
        # VULN: raw string interpolation → SQLi
        q = f"SELECT * FROM users WHERE username='{u}' AND password='{p}'"
        try:
            row = conn.execute(q).fetchone()
            if row:
                msg = f'<div class="ok">✅ Logged in as <b>{row["username"]}</b> | Role: {row["role"]} | Balance: ${row["balance"]:,.2f}</div>'
            else:
                msg = '<div class="err">❌ Wrong credentials</div>'
        except Exception as e:
            # VULN: full error + query shown to user (info disclosure)
            msg = f'<div class="err">DB Error: {e}<br><small>Query was: <code>{q}</code></small></div>'
        conn.close()
    body = f"""
    <div class="card">
      <h2>🔑 Login</h2>
      <div class="info">💡 SQLi hint: enter <code>admin'--</code> as username, any password</div>
      {msg}
      <form method="POST">
        <label>Username</label><input name="username" placeholder="admin'--">
        <label>Password</label><input name="password" type="password" placeholder="anything">
        <button class="btn btn-g">Login</button>
      </form>
    </div>"""
    return page(body, active="/login")

# ─── SEARCH — REFLECTED XSS + SQLi ────────────────────────────────────────────
@app.route("/search")
def search():
    q = request.args.get("q","")
    results = ""
    if q:
        conn = get_db()
        try:
            # VULN: SQLi via LIKE
            rows = conn.execute(f"SELECT id,username,email,role FROM users WHERE username LIKE '%{q}%'").fetchall()
            if rows:
                trs = "".join(f"<tr><td>{r['id']}</td><td>{r['username']}</td><td>{r['email']}</td><td>{r['role']}</td></tr>" for r in rows)
                results = f"<table><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th></tr>{trs}</table>"
            else:
                # VULN: q reflected without escaping → reflected XSS
                results = f"<div class='warn'>No results for: {q}</div>"
        except Exception as e:
            results = f"<div class='err'>Error: {e}</div>"
        conn.close()
    body = f"""
    <div class="card">
      <h2>🔍 Search Users</h2>
      <div class="info">💡 XSS hint: search for <code>&lt;script&gt;alert('XSS')&lt;/script&gt;</code></div>
      <form>
        <label>Search</label>
        <input name="q" value="{q}" placeholder="Try a username or XSS payload">
        <button class="btn btn-b">Search</button>
      </form>
      {results}
    </div>"""
    return page(body, active="/search")

# ─── MESSAGES — STORED XSS ────────────────────────────────────────────────────
@app.route("/messages", methods=["GET","POST"])
def messages():
    if request.method == "POST":
        author = request.form.get("author","Anonymous")
        body_  = request.form.get("body","")
        conn = get_db()
        # VULN: raw HTML stored without sanitisation → stored XSS
        conn.execute("INSERT INTO messages(author,body) VALUES(?,?)", (author, body_))
        conn.commit()
        conn.close()
    conn = get_db()
    msgs = conn.execute("SELECT author,body,ts FROM messages ORDER BY id DESC").fetchall()
    conn.close()
    # VULN: body rendered raw → stored XSS fires here
    rows = "".join(f"<tr><td>{m['author']}</td><td>{m['body']}</td><td style='color:#8b949e;font-size:11px'>{m['ts']}</td></tr>" for m in msgs)
    body = f"""
    <div class="card">
      <h2>💬 Message Board</h2>
      <div class="info">💡 Stored XSS hint: post <code>&lt;img src=x onerror=alert('StoredXSS')&gt;</code></div>
      <form method="POST" style="margin-bottom:18px">
        <label>Name</label><input name="author" placeholder="Your name">
        <label>Message</label><textarea name="body" rows="3" placeholder="Message — HTML allowed!"></textarea>
        <button class="btn btn-g">Post</button>
      </form>
      <table><tr><th>Author</th><th>Message</th><th>Time</th></tr>{rows}</table>
    </div>"""
    return page(body, active="/messages")

# ─── TRANSFER — CSRF (no token) ───────────────────────────────────────────────
@app.route("/transfer", methods=["GET","POST"])
def transfer():
    msg = ""
    if request.method == "POST":
        from_u = request.form.get("from_user","alice")
        to_u   = request.form.get("to_user","")
        amount = request.form.get("amount","0")
        # VULN: no CSRF token, no session check, any origin can POST
        conn = get_db()
        conn.execute("INSERT INTO transfers(from_user,to_user,amount) VALUES(?,?,?)", (from_u,to_u,amount))
        conn.commit()
        conn.close()
        msg = f'<div class="ok">✅ Transferred ${amount} from {from_u} to {to_u}</div>'
    conn = get_db()
    recent = conn.execute("SELECT from_user,to_user,amount,ts FROM transfers ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    rows = "".join(f"<tr><td>{r['from_user']}</td><td>{r['to_user']}</td><td>${r['amount']}</td><td style='font-size:11px;color:#8b949e'>{r['ts']}</td></tr>" for r in recent)
    body = f"""
    <div class="card">
      <h2>💸 Fund Transfer</h2>
      <div class="warn">⚠️ CSRF: no token on this form — any external website can silently POST here</div>
      {msg}
      <form method="POST">
        <label>From account</label><input name="from_user" value="alice">
        <label>To account</label><input name="to_user" placeholder="bob">
        <label>Amount ($)</label><input name="amount" type="number" placeholder="100">
        <button class="btn btn-g">Transfer</button>
      </form>
    </div>
    <div class="card">
      <h2>Recent Transfers</h2>
      <table><tr><th>From</th><th>To</th><th>Amount</th><th>Time</th></tr>{rows}</table>
    </div>"""
    return page(body, active="/transfer")

# ─── PROFILE — IDOR ───────────────────────────────────────────────────────────
@app.route("/profile")
def profile():
    uid = request.args.get("id","1")
    conn = get_db()
    # VULN: no session/ownership check → any user ID accessible
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not user:
        return page('<div class="card"><div class="err">User not found. Try id=1,2,3,4</div></div>', active="/profile")
    nav_ids = " ".join(f'<a href="/profile?id={i}" class="btn btn-b" style="padding:5px 10px;font-size:12px">User {i}</a>' for i in range(1,5))
    body = f"""
    <div class="card">
      <h2>👤 User Profile</h2>
      <div class="warn">⚠️ IDOR: no authentication check — change ?id= to view any account</div>
      <div style="margin-bottom:16px">{nav_ids}</div>
      <table>
        <tr><th>Field</th><th>Value</th></tr>
        <tr><td>ID</td><td>{user['id']}</td></tr>
        <tr><td>Username</td><td>{user['username']}</td></tr>
        <tr><td>Password</td><td><span style="color:#f85149">{user['password']}</span> ← plaintext!</td></tr>
        <tr><td>Email</td><td>{user['email']}</td></tr>
        <tr><td>Balance</td><td>${user['balance']:,.2f}</td></tr>
        <tr><td>Role</td><td>{user['role']}</td></tr>
      </table>
    </div>"""
    return page(body, active="/profile")

# ─── FETCH URL — SSRF ─────────────────────────────────────────────────────────
@app.route("/fetch", methods=["GET","POST"])
def fetch_url():
    result = ""
    # VULN: also accessible via GET ?url= so scanner can detect via URL param
    url_val = request.args.get("url","") or request.form.get("url","")
    if url_val:
        try:
            # VULN: fetches any URL including internal/metadata endpoints
            r = req.get(url_val, timeout=6, verify=False,
                        headers={"Metadata":"true","X-aws-ec2-metadata-token-ttl-seconds":"21600"})
            result = f'<div class="ok">Status: {r.status_code} | Content-Type: {r.headers.get("Content-Type","?")}</div><pre>{r.text[:4000]}</pre>'
        except Exception as e:
            result = f'<div class="err">Request failed: {e}</div>'
    body = f"""
    <div class="card">
      <h2>🌐 Internal URL Fetcher</h2>
      <div class="warn">⚠️ SSRF: fetches any URL with no validation</div>
      <div class="info">💡 Hints:<br>
        Cloud metadata: <code>http://169.254.169.254/latest/meta-data/</code><br>
        Loopback: <code>http://127.0.0.1/</code><br>
        Internal admin: <code>http://localhost:5000/admin</code>
      </div>
      <form method="POST">
        <label>URL to fetch</label>
        <input name="url" value="{url_val}" placeholder="http://169.254.169.254/latest/meta-data/">
        <button class="btn btn-b">Fetch</button>
      </form>
      {result}
    </div>"""
    resp = make_response(page(body, active="/fetch"))
    return resp

# ─── FILES — DIRECTORY TRAVERSAL ──────────────────────────────────────────────
@app.route("/files")
def files():
    filename = request.args.get("file","readme.txt")
    result = ""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "userfiles")
    # VULN: no path normalisation / containment check
    full_path = os.path.join(base, filename)
    try:
        with open(full_path, "r", errors="replace") as f:
            content = f.read(8000)
        result = f'<div class="ok">Reading: <code>{full_path}</code></div><pre>{content}</pre>'
    except Exception as e:
        result = f'<div class="err">Cannot read file: {e}<br>Attempted: <code>{full_path}</code></div>'
    body = f"""
    <div class="card">
      <h2>📁 File Viewer</h2>
      <div class="warn">⚠️ Directory traversal: no path sanitisation</div>
      <div class="info">💡 Try: <code>../app.py</code> &nbsp;|&nbsp; <code>../../../etc/passwd</code> &nbsp;|&nbsp; <code>../vulnbank.db</code></div>
      <form style="margin-bottom:16px">
        <label>Filename</label>
        <input name="file" value="{filename}">
        <button class="btn btn-b">View</button>
      </form>
      {result}
    </div>"""
    return page(body, active="/files")

# ─── XML API — XXE INJECTION ──────────────────────────────────────────────────
@app.route("/api/xml", methods=["GET","POST","OPTIONS"])
def xml_api():
    result = ""

    # OPTIONS — tell scanner this endpoint accepts POST + XML
    if request.method == "OPTIONS":
        resp = make_response("", 200)
        resp.headers["Allow"] = "GET, POST, OPTIONS"
        resp.headers["Content-Type"] = "application/xml"
        return resp

    if request.method == "POST":
        raw = request.data or request.form.get("xml","").encode()
        if raw:
            try:
                # VULN: lxml with resolve_entities=True → XXE
                parser = ET.XMLParser(resolve_entities=True, load_dtd=True, no_network=False)
                tree = ET.fromstring(raw, parser)
                # Return the parsed text — exposes any entity content
                text = ET.tostring(tree, encoding="unicode")
                result = f'<div class="ok">XML parsed successfully</div><pre>{text}</pre>'
            except ET.XMLSyntaxError as e:
                result = f'<div class="err">XML parse error: {e}</div>'
            except Exception as e:
                result = f'<div class="err">Error: {e}</div>'

    sample = """&lt;?xml version="1.0"?&gt;
&lt;!DOCTYPE foo [&lt;!ENTITY xxe SYSTEM "file:///etc/passwd"&gt;]&gt;
&lt;user&gt;&amp;xxe;&lt;/user&gt;"""

    body = f"""
    <div class="card">
      <h2>📡 XML API Endpoint</h2>
      <div class="warn">⚠️ XXE: XML parsed with external entity resolution enabled</div>
      <div class="info">💡 POST <code>application/xml</code> to this URL, or use the form below:<br>
        <pre style="margin-top:8px">{sample}</pre>
      </div>
      <form method="POST" enctype="text/plain">
        <label>XML Payload</label>
        <textarea name="xml" rows="6" placeholder="Paste XML here...">&lt;?xml version="1.0"?&gt;
&lt;!DOCTYPE foo [&lt;!ENTITY xxe SYSTEM "file:///etc/passwd"&gt;]&gt;
&lt;user&gt;&amp;xxe;&lt;/user&gt;</textarea>
        <button class="btn btn-b">Submit XML</button>
      </form>
      {result}
    </div>"""
    resp = make_response(page(body, active="/api/xml"))
    resp.headers["Content-Type"] = "text/html"
    resp.headers["Allow"] = "GET, POST, OPTIONS"
    return resp

# ─── REDIRECT — OPEN REDIRECT ─────────────────────────────────────────────────
@app.route("/redirect")
def open_redirect():
    url = request.args.get("url","")
    if url:
        # VULN: no validation of destination
        return redirect(url)
    body = """
    <div class="card">
      <h2>↗️ Open Redirect</h2>
      <div class="warn">⚠️ No URL validation — redirects to any external domain</div>
      <div class="info">💡 Try: <code>/redirect?url=https://evil.com</code></div>
      <form>
        <label>Redirect to</label>
        <input name="url" placeholder="https://evil.com">
        <button class="btn btn-r">Redirect</button>
      </form>
    </div>"""
    return page(body, active="/redirect")

# ─── ADMIN — No auth ──────────────────────────────────────────────────────────
@app.route("/admin")
def admin():
    conn = get_db()
    users     = conn.execute("SELECT id,username,email,balance,role FROM users").fetchall()
    transfers = conn.execute("SELECT * FROM transfers ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    u_rows = "".join(f"<tr><td><a href='/profile?id={u['id']}'>{u['id']}</a></td><td>{u['username']}</td><td>{u['email']}</td><td>${u['balance']:,.2f}</td><td>{u['role']}</td></tr>" for u in users)
    t_rows = "".join(f"<tr><td>{t['from_user']}</td><td>{t['to_user']}</td><td>${t['amount']}</td></tr>" for t in transfers)
    body = f"""
    <div class="err" style="margin-bottom:16px">⚠️ No authentication required to access this admin panel</div>
    <div class="card">
      <h2>👥 All Users</h2>
      <table><tr><th>ID</th><th>Username</th><th>Email</th><th>Balance</th><th>Role</th></tr>{u_rows}</table>
    </div>
    <div class="card">
      <h2>💳 Transfers</h2>
      <table><tr><th>From</th><th>To</th><th>Amount</th></tr>{t_rows}</table>
    </div>"""
    return page(body, active="/admin")

# ─── NO SECURITY HEADERS (intentional) ───────────────────────────────────────
# Flask does NOT add CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
# Referrer-Policy, or Permissions-Policy by default.
# The scanner's SecurityHeadersDetector will flag all of these.
# We also expose the Server / X-Powered-By headers:
@app.after_request
def add_info_disclosure_headers(resp):
    resp.headers["X-Powered-By"] = "VulnBank/2.0 Python/3.11 Flask"
    resp.headers["Server"]       = "VulnBank-Server/2.0"
    # Intentionally do NOT set: CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
    # Referrer-Policy, Permissions-Policy — these missing headers will be flagged.
    return resp

# ─── STARTUP ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
