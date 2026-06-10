#!/usr/bin/env python3
"""
VulnBank v3 — Deliberately Vulnerable Web Application
All 9 scanner modules will fire:
  SQLi, XSS (reflected+stored), CSRF, Open Redirect,
  Directory Traversal, Security Headers, SSRF, XXE, IDOR
KEY FIX: Every vulnerability is also exposed via GET ?param= URLs
so the crawler discovers and tests them automatically.
"""

import os, sqlite3, lxml.etree as ET
from flask import Flask, request, render_template_string, redirect, make_response
import requests as req

app = Flask(__name__)
app.secret_key = "vulnbank-hardcoded-secret"
DB = os.environ.get("DB_PATH", "vulnbank.db")

# ── DB ────────────────────────────────────────────────────────────────────────
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
            from_user TEXT, to_user TEXT, amount REAL,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO users VALUES(1,'admin','Admin@123','admin@vulnbank.io',99999,'admin');
        INSERT OR IGNORE INTO users VALUES(2,'alice','Alice@456','alice@vulnbank.io',5000,'user');
        INSERT OR IGNORE INTO users VALUES(3,'bob','Bob@789','bob@vulnbank.io',1200,'user');
        INSERT OR IGNORE INTO users VALUES(4,'charlie','Charlie@000','charlie@vulnbank.io',300,'user');
        INSERT OR IGNORE INTO messages(author,body) VALUES('admin','Welcome to VulnBank!');
    """)
    conn.commit(); conn.close()
    os.makedirs("userfiles", exist_ok=True)
    with open("userfiles/readme.txt","w") as f:
        f.write("VulnBank user files.\nTry: ?file=../app.py or ?file=../../../etc/passwd")

# ── LAYOUT ────────────────────────────────────────────────────────────────────
CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
nav{background:#161b22;border-bottom:1px solid #30363d;padding:12px 28px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.logo{color:#58a6ff;font-weight:700;font-size:1.2em;text-decoration:none}
nav a{color:#8b949e;text-decoration:none;font-size:13px;margin-left:12px}
nav a:hover,nav a.active{color:#e6edf3}
.wrap{max-width:940px;margin:28px auto;padding:0 18px}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:24px;margin-bottom:18px}
.card h2{color:#58a6ff;margin-bottom:14px;font-size:1.05em}
label{font-size:12px;color:#8b949e;display:block;margin-bottom:3px}
input,textarea,select{width:100%;padding:9px 11px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:13px;margin-bottom:11px}
input:focus,textarea:focus{outline:none;border-color:#58a6ff}
.btn{padding:9px 18px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}
.g{background:#238636;color:#fff}.b{background:#1f6feb;color:#fff}.r{background:#da3633;color:#fff}
.ok{background:#1a3a2a;border:1px solid #238636;color:#3fb950;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px}
.er{background:#3a1a1a;border:1px solid #da3633;color:#f85149;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px}
.inf{background:#1a2a3a;border:1px solid #1f6feb;color:#58a6ff;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px}
.wr{background:#2a2200;border:1px solid #d29922;color:#e3b341;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#21262d;color:#8b949e;padding:9px 11px;text-align:left}
td{padding:9px 11px;border-top:1px solid #21262d}
code{background:#21262d;padding:1px 6px;border-radius:4px;font-size:12px;color:#f85149}
pre{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:14px;overflow:auto;max-height:340px;font-size:12px;color:#3fb950;white-space:pre-wrap;word-break:break-all}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.vbadge{background:#21262d;border:1px solid #30363d;border-radius:8px;padding:14px}
.vbadge b{color:#f85149;display:block;margin-bottom:4px;font-size:13px}
.vbadge span{color:#8b949e;font-size:12px}
a.btn-link{color:#58a6ff;font-size:12px;text-decoration:none;margin-right:8px}
a.btn-link:hover{text-decoration:underline}
</style>"""

LINKS = [
    ("/","Home"),("/login","Login"),("/search","Search"),
    ("/messages","Messages"),("/transfer","Transfer"),
    ("/profile","Profile"),("/fetch","Fetch URL"),
    ("/files","Files"),("/api/xml","XML API"),
    ("/redirect","Redirect"),("/admin","Admin"),
]

def nav_html(active=""):
    items = "".join(f'<a href="{u}"{"class=\"active\"" if u==active else ""}>{n}</a>' for u,n in LINKS)
    return f'<nav><a class="logo" href="/">🏦 VulnBank</a><div>{items}</div></nav>'

def page(body, active=""):
    return CSS + nav_html(active) + f'<div class="wrap">{body}</div>'

# ── HOME ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    vulns = [
        ("SQL Injection",        "/login — try admin'--  |  /search?username=admin"),
        ("Reflected XSS",        "/search?q=<script>alert(1)</script>"),
        ("Stored XSS",           "/messages — post <img src=x onerror=alert(1)>"),
        ("CSRF",                 "/transfer — no CSRF token on form"),
        ("IDOR",                 "/profile?id=2  /profile?id=3"),
        ("SSRF",                 "/fetch?url=http://169.254.169.254/latest/meta-data/"),
        ("Directory Traversal",  "/files?file=../../../etc/passwd"),
        ("XXE Injection",        "/api/xml — POST application/xml"),
        ("Open Redirect",        "/redirect?url=https://evil.com"),
        ("No Security Headers",  "CSP, HSTS, X-Frame-Options all missing"),
    ]
    cards = "".join(f'<div class="vbadge"><b>{v}</b><span>{w}</span></div>' for v,w in vulns)
    # expose ALL vuln URLs as clickable links so crawler finds them
    crawler_links = """
    <a href="/search?q=test" class="btn-link">search?q</a>
    <a href="/search?username=admin" class="btn-link">search?username</a>
    <a href="/login?username=admin&amp;password=x" class="btn-link">login params</a>
    <a href="/profile?id=1" class="btn-link">profile?id=1</a>
    <a href="/profile?id=2" class="btn-link">profile?id=2</a>
    <a href="/profile?id=3" class="btn-link">profile?id=3</a>
    <a href="/fetch?url=http://127.0.0.1/" class="btn-link">fetch?url</a>
    <a href="/files?file=readme.txt" class="btn-link">files?file</a>
    <a href="/redirect?url=https://example.com" class="btn-link">redirect?url</a>
    <a href="/messages?author=test&amp;body=hi" class="btn-link">messages?author</a>
    <a href="/transfer?from_user=alice&amp;to_user=bob&amp;amount=1" class="btn-link">transfer params</a>
    <a href="/api/xml" class="btn-link">api/xml</a>
    <a href="/admin" class="btn-link">admin</a>
    """
    body = f"""
    <div class="card" style="text-align:center;padding:40px 24px">
      <div style="font-size:2.2em;margin-bottom:8px">🏦</div>
      <h1 style="color:#58a6ff;font-size:1.7em;margin-bottom:6px">VulnBank Demo</h1>
      <p style="color:#8b949e;margin-bottom:4px">Intentionally Vulnerable Application — Security Scanner Demo</p>
      <p style="color:#f85149;font-size:12px;margin-bottom:24px">⚠️ FOR EDUCATIONAL USE ONLY</p>
      <div class="grid3" style="text-align:left">{cards}</div>
    </div>
    <div class="card">
      <h2>🔗 All Vulnerable Endpoints (crawler entry points)</h2>
      <div style="line-height:2">{crawler_links}</div>
    </div>"""
    return page(body, "/")

# ── LOGIN — SQL INJECTION via GET + POST ──────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    # Accept params via GET too so scanner URL-param tests fire
    u = request.values.get("username","")
    p = request.values.get("password","")
    msg = ""
    if u or request.method == "POST":
        conn = get_db()
        # VULN: raw f-string → SQLi
        q = f"SELECT * FROM users WHERE username='{u}' AND password='{p}'"
        try:
            row = conn.execute(q).fetchone()
            if row:
                msg = f'<div class="ok">✅ Logged in as <b>{row["username"]}</b> | Role: {row["role"]} | Balance: ${row["balance"]:,.2f}</div>'
            else:
                msg = '<div class="er">❌ Wrong credentials</div>'
        except Exception as e:
            # VULN: full error + raw query exposed (info disclosure)
            msg = f'<div class="er">DB Error: {e}<br><small>Query: <code>{q}</code></small></div>'
        conn.close()
    body = f"""
    <div class="card">
      <h2>🔑 Login</h2>
      <div class="inf">💡 SQLi: username = <code>admin'--</code> &nbsp;|&nbsp; Also test via GET: <code>/login?username=admin'--&amp;password=x</code></div>
      {msg}
      <form method="POST">
        <label>Username</label><input name="username" value="{u}" placeholder="admin'--">
        <label>Password</label><input name="password" type="password" placeholder="anything">
        <button class="btn g">Login</button>
      </form>
    </div>"""
    return page(body, "/login")

# ── SEARCH — SQLi + REFLECTED XSS via GET params ─────────────────────────────
@app.route("/search")
def search():
    # VULN: both ?q= and ?username= are raw interpolated
    q        = request.args.get("q","")
    username = request.args.get("username","")
    results  = ""
    search_val = q or username
    if search_val:
        conn = get_db()
        try:
            # VULN: raw SQLi
            rows = conn.execute(
                f"SELECT id,username,email,role FROM users WHERE username LIKE '%{search_val}%'"
            ).fetchall()
            if rows:
                trs = "".join(f"<tr><td>{r['id']}</td><td>{r['username']}</td><td>{r['email']}</td><td>{r['role']}</td></tr>" for r in rows)
                results = f"<table><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th></tr>{trs}</table>"
            else:
                # VULN: search_val echoed unescaped → reflected XSS
                results = f"<div class='wr'>No results for: {search_val}</div>"
        except Exception as e:
            results = f"<div class='er'>DB Error: {e}</div>"
        conn.close()
    body = f"""
    <div class="card">
      <h2>🔍 Search Users</h2>
      <div class="inf">💡 Reflected XSS: search <code>&lt;script&gt;alert('XSS')&lt;/script&gt;</code><br>
           SQLi: search <code>' OR 1=1--</code></div>
      <form>
        <label>Search by username</label>
        <input name="q" value="{q}" placeholder="Try XSS or SQLi payload">
        <button class="btn b">Search</button>
      </form>
      {results}
    </div>"""
    return page(body, "/search")

# ── MESSAGES — STORED XSS via GET + POST ─────────────────────────────────────
@app.route("/messages", methods=["GET","POST"])
def messages():
    # Accept via GET params too so scanner can test without form submission
    author = request.values.get("author","")
    body_  = request.values.get("body","")
    if author and body_:
        conn = get_db()
        # VULN: raw HTML stored without sanitisation
        conn.execute("INSERT INTO messages(author,body) VALUES(?,?)", (author, body_))
        conn.commit(); conn.close()
    conn = get_db()
    msgs = conn.execute("SELECT author,body,ts FROM messages ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    # VULN: body rendered unescaped → stored XSS
    rows = "".join(
        f"<tr><td style='width:120px'>{m['author']}</td><td>{m['body']}</td>"
        f"<td style='color:#8b949e;font-size:11px;white-space:nowrap'>{m['ts']}</td></tr>"
        for m in msgs
    )
    body = f"""
    <div class="card">
      <h2>💬 Message Board</h2>
      <div class="inf">💡 Stored XSS: post <code>&lt;img src=x onerror=alert('StoredXSS')&gt;</code></div>
      <form method="POST" style="margin-bottom:16px">
        <label>Name</label><input name="author" placeholder="Your name">
        <label>Message (HTML allowed!)</label>
        <textarea name="body" rows="3" placeholder="<img src=x onerror=alert(1)>"></textarea>
        <button class="btn g">Post</button>
      </form>
      <table><tr><th>Author</th><th>Message</th><th>Time</th></tr>{rows}</table>
    </div>"""
    return page(body, "/messages")

# ── TRANSFER — CSRF (no token, also GET-accessible) ───────────────────────────
@app.route("/transfer", methods=["GET","POST"])
def transfer():
    msg = ""
    # VULN: no CSRF token; also accepts GET so crawler/scanner can reach it
    from_u = request.values.get("from_user","")
    to_u   = request.values.get("to_user","")
    amount = request.values.get("amount","")
    if from_u and to_u and amount:
        conn = get_db()
        conn.execute("INSERT INTO transfers(from_user,to_user,amount) VALUES(?,?,?)",
                     (from_u, to_u, amount))
        conn.commit(); conn.close()
        msg = f'<div class="ok">✅ Transferred ${amount} from {from_u} to {to_u}</div>'
    conn = get_db()
    recent = conn.execute("SELECT from_user,to_user,amount,ts FROM transfers ORDER BY id DESC LIMIT 8").fetchall()
    conn.close()
    rows = "".join(
        f"<tr><td>{r['from_user']}</td><td>{r['to_user']}</td><td>${r['amount']}</td>"
        f"<td style='font-size:11px;color:#8b949e'>{r['ts']}</td></tr>"
        for r in recent
    )
    body = f"""
    <div class="card">
      <h2>💸 Fund Transfer</h2>
      <div class="wr">⚠️ CSRF: no CSRF token — any external site can POST this form silently</div>
      {msg}
      <form method="POST">
        <label>From account</label><input name="from_user" value="{from_u or 'alice'}">
        <label>To account</label><input name="to_user" value="{to_u}" placeholder="bob">
        <label>Amount ($)</label><input name="amount" type="number" value="{amount}" placeholder="100">
        <button class="btn g">Transfer</button>
      </form>
    </div>
    <div class="card">
      <h2>Recent Transfers</h2>
      <table><tr><th>From</th><th>To</th><th>Amount</th><th>Time</th></tr>{rows}</table>
    </div>"""
    return page(body, "/transfer")

# ── PROFILE — IDOR ─────────────────────────────────────────────────────────────
@app.route("/profile")
def profile():
    uid = request.args.get("id","1")
    conn = get_db()
    # VULN: no session check — any id= value returns that user's full record
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not user:
        return page('<div class="card"><div class="er">User not found. Try ?id=1 to 4</div></div>', "/profile")
    nav_btns = " ".join(
        f'<a href="/profile?id={i}" class="btn-link">User {i}</a>' for i in range(1,5)
    )
    body = f"""
    <div class="card">
      <h2>👤 User Profile — IDOR Demo</h2>
      <div class="wr">⚠️ IDOR: no authentication — change ?id= to access any account</div>
      <div style="margin-bottom:14px">{nav_btns}</div>
      <table>
        <tr><th>Field</th><th>Value</th></tr>
        <tr><td>ID</td><td>{user['id']}</td></tr>
        <tr><td>Username</td><td>{user['username']}</td></tr>
        <tr><td>Password</td><td><span style="color:#f85149">{user['password']}</span> ← plaintext exposed!</td></tr>
        <tr><td>Email</td><td>{user['email']}</td></tr>
        <tr><td>Balance</td><td>${user['balance']:,.2f}</td></tr>
        <tr><td>Role</td><td>{user['role']}</td></tr>
      </table>
    </div>"""
    return page(body, "/profile")

# ── FETCH URL — SSRF (GET ?url= + POST) ───────────────────────────────────────
@app.route("/fetch", methods=["GET","POST"])
def fetch_url():
    result = ""
    # VULN: ?url= accepted via GET so scanner URL-param tester fires
    url_val = request.values.get("url","")
    if url_val:
        try:
            r = req.get(url_val, timeout=6, verify=False,
                        headers={"Metadata":"true",
                                 "X-aws-ec2-metadata-token-ttl-seconds":"21600"})
            result = (f'<div class="ok">Status: {r.status_code} | '
                      f'Content-Type: {r.headers.get("Content-Type","?")}</div>'
                      f'<pre>{r.text[:4000]}</pre>')
        except Exception as e:
            result = f'<div class="er">Request failed: {e}</div>'
    body = f"""
    <div class="card">
      <h2>🌐 Internal URL Fetcher — SSRF</h2>
      <div class="wr">⚠️ SSRF: fetches any URL with no validation</div>
      <div class="inf">💡 Try:<br>
        <code>http://169.254.169.254/latest/meta-data/</code> (AWS metadata)<br>
        <code>http://127.0.0.1/admin</code> (internal loopback)<br>
        <code>http://0.0.0.0/</code>
      </div>
      <form method="POST">
        <label>URL to fetch</label>
        <input name="url" value="{url_val}" placeholder="http://169.254.169.254/latest/meta-data/">
        <button class="btn b">Fetch</button>
      </form>
      {result}
    </div>"""
    return page(body, "/fetch")

# ── FILES — DIRECTORY TRAVERSAL ───────────────────────────────────────────────
@app.route("/files")
def files():
    filename = request.args.get("file","readme.txt")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "userfiles")
    # VULN: no containment check
    full_path = os.path.join(base, filename)
    try:
        with open(full_path,"r",errors="replace") as f:
            content = f.read(8000)
        result = f'<div class="ok">Reading: <code>{full_path}</code></div><pre>{content}</pre>'
    except Exception as e:
        result = f'<div class="er">Cannot read: {e}<br>Path tried: <code>{full_path}</code></div>'
    body = f"""
    <div class="card">
      <h2>📁 File Viewer — Directory Traversal</h2>
      <div class="wr">⚠️ No path sanitisation — traverse outside root</div>
      <div class="inf">💡 Try: <code>../app.py</code> &nbsp;|&nbsp; <code>../../../etc/passwd</code> &nbsp;|&nbsp; <code>../vulnbank.db</code></div>
      <form style="margin-bottom:14px">
        <label>Filename</label>
        <input name="file" value="{filename}">
        <button class="btn b">View</button>
      </form>
      {result}
    </div>"""
    return page(body, "/files")

# ── XML API — XXE ─────────────────────────────────────────────────────────────
@app.route("/api/xml", methods=["GET","POST","OPTIONS"])
def xml_api():
    # OPTIONS tells scanner: POST is allowed → it will try XXE payloads
    if request.method == "OPTIONS":
        resp = make_response("", 200)
        resp.headers["Allow"]        = "GET, POST, OPTIONS"
        resp.headers["Content-Type"] = "application/xml"
        return resp

    result = ""
    if request.method == "POST":
        raw = request.data
        if not raw:
            raw = request.form.get("xml","").encode()
        if raw:
            try:
                # VULN: external entities enabled → XXE
                parser = ET.XMLParser(resolve_entities=True, load_dtd=True, no_network=False)
                tree   = ET.fromstring(raw, parser)
                text   = ET.tostring(tree, encoding="unicode")
                result = f'<div class="ok">Parsed OK</div><pre>{text[:3000]}</pre>'
            except ET.XMLSyntaxError as e:
                # VULN: error may contain entity expansion content
                result = f'<div class="er">XML Error: {e}</div>'
            except Exception as e:
                result = f'<div class="er">Error: {e}</div>'

    xxe_demo = (
        "&lt;?xml version=\"1.0\"?&gt;\n"
        "&lt;!DOCTYPE foo [&lt;!ENTITY xxe SYSTEM \"file:///etc/passwd\"&gt;]&gt;\n"
        "&lt;user&gt;&amp;xxe;&lt;/user&gt;"
    )
    body = f"""
    <div class="card">
      <h2>📡 XML API — XXE Injection</h2>
      <div class="wr">⚠️ lxml parses with resolve_entities=True — external entities enabled</div>
      <div class="inf">💡 POST <code>Content-Type: application/xml</code> payload:<br>
        <pre style="margin-top:8px">{xxe_demo}</pre>
      </div>
      <form method="POST">
        <label>XML Payload</label>
        <textarea name="xml" rows="5">&lt;?xml version="1.0"?&gt;
&lt;!DOCTYPE foo [&lt;!ENTITY xxe SYSTEM "file:///etc/passwd"&gt;]&gt;
&lt;user&gt;&amp;xxe;&lt;/user&gt;</textarea>
        <button class="btn b">Submit XML</button>
      </form>
      {result}
    </div>"""
    resp = make_response(page(body, "/api/xml"))
    resp.headers["Allow"]        = "GET, POST, OPTIONS"
    resp.headers["Content-Type"] = "text/html"
    return resp

# ── REDIRECT — OPEN REDIRECT ──────────────────────────────────────────────────
@app.route("/redirect")
def open_redirect():
    url = request.args.get("url","")
    if url:
        # VULN: no destination validation
        resp = make_response("", 302)
        resp.headers["Location"] = url
        return resp
    body = """
    <div class="card">
      <h2>↗️ Open Redirect</h2>
      <div class="wr">⚠️ No validation on redirect target</div>
      <div class="inf">💡 Try: <code>/redirect?url=https://evil.com</code></div>
      <form>
        <label>Redirect destination</label>
        <input name="url" placeholder="https://evil.com">
        <button class="btn r">Redirect</button>
      </form>
    </div>"""
    return page(body, "/redirect")

# ── ADMIN — No auth check ─────────────────────────────────────────────────────
@app.route("/admin")
def admin():
    conn = get_db()
    users = conn.execute("SELECT id,username,email,balance,role FROM users").fetchall()
    txns  = conn.execute("SELECT from_user,to_user,amount,ts FROM transfers ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    u_rows = "".join(
        f"<tr><td><a href='/profile?id={u['id']}' style='color:#58a6ff'>{u['id']}</a></td>"
        f"<td>{u['username']}</td><td>{u['email']}</td><td>${u['balance']:,.2f}</td><td>{u['role']}</td></tr>"
        for u in users
    )
    t_rows = "".join(
        f"<tr><td>{t['from_user']}</td><td>{t['to_user']}</td><td>${t['amount']}</td>"
        f"<td style='font-size:11px;color:#8b949e'>{t['ts']}</td></tr>"
        for t in txns
    ) or "<tr><td colspan='4' style='color:#8b949e'>No transfers yet</td></tr>"
    body = f"""
    <div class="er" style="margin-bottom:14px">⚠️ Broken Access Control: no login required to reach this admin panel</div>
    <div class="card">
      <h2>👥 All Users</h2>
      <table><tr><th>ID</th><th>Username</th><th>Email</th><th>Balance</th><th>Role</th></tr>{u_rows}</table>
    </div>
    <div class="card">
      <h2>💳 Transfers</h2>
      <table><tr><th>From</th><th>To</th><th>Amount</th><th>Time</th></tr>{t_rows}</table>
    </div>"""
    return page(body, "/admin")

# ── MISSING SECURITY HEADERS (intentional) ───────────────────────────────────
@app.after_request
def leak_headers(resp):
    # Expose tech stack for info disclosure
    resp.headers["X-Powered-By"] = "VulnBank/3.0 Python/3.11 Flask"
    resp.headers["Server"]       = "VulnBank-Server/3.0"
    # Deliberately NOT setting: CSP, HSTS, X-Frame-Options,
    # X-Content-Type-Options, Referrer-Policy, Permissions-Policy
    # The scanner's SecurityHeadersDetector will flag ALL of these.
    return resp

# ── STARTUP ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
