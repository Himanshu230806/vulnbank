#!/usr/bin/env python3
"""
VulnBank - Deliberately Vulnerable Web Application
FOR EDUCATIONAL / DEMONSTRATION PURPOSES ONLY
Contains: SQLi, XSS, CSRF, Open Redirect, Directory Traversal,
          SSRF, IDOR, Security Headers missing, Info Disclosure
"""

import os
import sqlite3
import subprocess
from flask import Flask, request, render_template_string, redirect, make_response, send_file
import requests as req

app = Flask(__name__)
app.secret_key = "supersecretkey123"  # Hardcoded secret - vulnerability

DB = "vulnbank.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            email TEXT,
            balance REAL,
            role TEXT DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            sender TEXT,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO users VALUES (1,'admin','admin123','admin@vulnbank.com',99999.0,'admin');
        INSERT OR IGNORE INTO users VALUES (2,'alice','alice123','alice@vulnbank.com',5000.0,'user');
        INSERT OR IGNORE INTO users VALUES (3,'bob','bob456','bob@vulnbank.com',1200.0,'user');
        INSERT OR IGNORE INTO messages VALUES (1,'admin','Welcome to VulnBank! Your account is ready.', datetime('now'));
    """)
    conn.commit()
    conn.close()

BASE_STYLE = """
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Segoe UI', sans-serif; background:#0d1117; color:#e6edf3; min-height:100vh; }
.navbar { background:#161b22; border-bottom:1px solid #30363d; padding:14px 32px; display:flex; justify-content:space-between; align-items:center; }
.navbar .logo { color:#58a6ff; font-size:1.3em; font-weight:700; text-decoration:none; }
.navbar a { color:#8b949e; text-decoration:none; margin-left:20px; font-size:14px; }
.navbar a:hover { color:#e6edf3; }
.container { max-width:900px; margin:40px auto; padding:0 20px; }
.card { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:28px; margin-bottom:20px; }
.card h2 { color:#58a6ff; margin-bottom:18px; font-size:1.1em; }
input, textarea, select { width:100%; padding:10px 12px; background:#0d1117; border:1px solid #30363d;
    border-radius:6px; color:#e6edf3; font-size:14px; margin:6px 0 14px; }
input:focus, textarea:focus { outline:none; border-color:#58a6ff; }
.btn { padding:10px 20px; border:none; border-radius:6px; cursor:pointer; font-size:14px; font-weight:600; }
.btn-primary { background:#238636; color:#fff; }
.btn-danger { background:#da3633; color:#fff; }
.btn-blue { background:#1f6feb; color:#fff; }
.alert { padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:14px; }
.alert-success { background:#1a3a2a; border:1px solid #238636; color:#3fb950; }
.alert-danger  { background:#3a1a1a; border:1px solid #da3633; color:#f85149; }
.alert-info    { background:#1a2a3a; border:1px solid #1f6feb; color:#58a6ff; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th { background:#21262d; color:#8b949e; padding:10px 12px; text-align:left; }
td { padding:10px 12px; border-top:1px solid #21262d; }
.badge { padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; }
.badge-admin { background:#6e40c9; color:#d2a8ff; }
.badge-user  { background:#21262d; color:#8b949e; }
label { font-size:13px; color:#8b949e; }
</style>
"""

NAV = """
<nav class="navbar">
  <a class="logo" href="/">🏦 VulnBank</a>
  <div>
    <a href="/">Home</a>
    <a href="/login">Login</a>
    <a href="/search">Search</a>
    <a href="/transfer">Transfer</a>
    <a href="/messages">Messages</a>
    <a href="/profile">Profile</a>
    <a href="/admin">Admin</a>
    <a href="/fetch">Fetch URL</a>
    <a href="/files">Files</a>
  </div>
</nav>
"""

# ─────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(BASE_STYLE + NAV + """
<div class="container">
  <div class="card" style="text-align:center;padding:48px">
    <h1 style="color:#58a6ff;font-size:2em;margin-bottom:12px">🏦 VulnBank</h1>
    <p style="color:#8b949e;margin-bottom:28px">Intentionally Vulnerable Demo Application<br>
    <span style="color:#f85149;font-size:12px">⚠️ FOR SECURITY TESTING DEMO ONLY — DO NOT USE IN PRODUCTION</span></p>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;text-align:left">
      <div class="card"><b style="color:#f85149">SQL Injection</b><br><small style="color:#8b949e">Login & search bypass</small></div>
      <div class="card"><b style="color:#f85149">XSS</b><br><small style="color:#8b949e">Stored & reflected</small></div>
      <div class="card"><b style="color:#f85149">CSRF</b><br><small style="color:#8b949e">No token on transfer</small></div>
      <div class="card"><b style="color:#f85149">IDOR</b><br><small style="color:#8b949e">Access any profile by ID</small></div>
      <div class="card"><b style="color:#f85149">SSRF</b><br><small style="color:#8b949e">Internal URL fetcher</small></div>
      <div class="card"><b style="color:#f85149">Dir Traversal</b><br><small style="color:#8b949e">Read server files</small></div>
      <div class="card"><b style="color:#f85149">Open Redirect</b><br><small style="color:#8b949e">Unvalidated redirects</small></div>
      <div class="card"><b style="color:#f85149">Security Headers</b><br><small style="color:#8b949e">No CSP / HSTS</small></div>
      <div class="card"><b style="color:#f85149">Info Disclosure</b><br><small style="color:#8b949e">Stack traces exposed</small></div>
    </div>
  </div>
</div>
""")

# ─────────────────────────────────────────────────────────────
# LOGIN — SQL INJECTION
# ─────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    hint = "Try: <code style='color:#f85149'>admin'--</code> as username (SQLi bypass)"
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        conn = sqlite3.connect(DB)
        # VULNERABLE: raw string interpolation → SQL injection
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        try:
            row = conn.execute(query).fetchone()
            if row:
                msg = f'<div class="alert alert-success">✅ Logged in as <b>{row[1]}</b> (role: {row[5]}) — Balance: ${row[4]:,.2f}</div>'
            else:
                msg = '<div class="alert alert-danger">❌ Invalid credentials</div>'
        except Exception as e:
            # VULNERABLE: full error exposed to user
            msg = f'<div class="alert alert-danger">DB Error: {e}<br><small>Query: {query}</small></div>'
        conn.close()
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>🔑 Login</h2>
  <div class="alert alert-info">{hint}</div>
  {msg}
  <form method="POST">
    <label>Username</label><input name="username" placeholder="Try: admin'--">
    <label>Password</label><input name="password" type="password" placeholder="anything">
    <button class="btn btn-primary">Login</button>
  </form>
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# SEARCH — REFLECTED XSS + SQL INJECTION
# ─────────────────────────────────────────────────────────────
@app.route("/search")
def search():
    q = request.args.get("q","")
    results = ""
    hint = "Try: <code style='color:#f85149'>&lt;script&gt;alert('XSS')&lt;/script&gt;</code> in the search box"
    if q:
        conn = sqlite3.connect(DB)
        # VULNERABLE: raw interpolation in SQL
        try:
            rows = conn.execute(f"SELECT id,username,email,role FROM users WHERE username LIKE '%{q}%'").fetchall()
            if rows:
                results = "<table><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th></tr>"
                for r in rows:
                    results += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"
                results += "</table>"
            else:
                results = f"<p style='color:#8b949e'>No results for: {q}</p>"  # VULNERABLE: unescaped reflection
        except Exception as e:
            results = f"<p style='color:#f85149'>Error: {e}</p>"
        conn.close()
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>🔍 User Search</h2>
  <div class="alert alert-info">{hint}</div>
  <form>
    <label>Search username</label>
    <input name="q" value="{q}" placeholder="Search...">
    <button class="btn btn-blue">Search</button>
  </form>
  {results}
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# MESSAGES — STORED XSS
# ─────────────────────────────────────────────────────────────
@app.route("/messages", methods=["GET","POST"])
def messages():
    hint = "Try posting: <code style='color:#f85149'>&lt;img src=x onerror=alert('StoredXSS')&gt;</code>"
    if request.method == "POST":
        sender = request.form.get("sender","Anonymous")
        content = request.form.get("content","")
        conn = sqlite3.connect(DB)
        # VULNERABLE: stores raw HTML/JS without sanitisation
        conn.execute("INSERT INTO messages (sender,content) VALUES (?,?)", (sender, content))
        conn.commit()
        conn.close()

    conn = sqlite3.connect(DB)
    msgs = conn.execute("SELECT sender,content,created_at FROM messages ORDER BY id DESC").fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{m[0]}</td><td>{m[1]}</td><td style='color:#8b949e;font-size:12px'>{m[2]}</td></tr>"
        for m in msgs
    )
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>💬 Message Board</h2>
  <div class="alert alert-info">{hint}</div>
  <form method="POST" style="margin-bottom:20px">
    <label>Your name</label><input name="sender" placeholder="Name">
    <label>Message</label><textarea name="content" rows="3" placeholder="Type your message..."></textarea>
    <button class="btn btn-primary">Post Message</button>
  </form>
  <table>
    <tr><th>Sender</th><th>Message</th><th>Time</th></tr>
    {rows}
  </table>
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# TRANSFER — CSRF (no token)
# ─────────────────────────────────────────────────────────────
@app.route("/transfer", methods=["GET","POST"])
def transfer():
    msg = ""
    hint = "No CSRF token on this form — any external site can POST here silently"
    if request.method == "POST":
        to_user = request.form.get("to","")
        amount  = request.form.get("amount","0")
        note    = request.form.get("note","")
        # VULNERABLE: no CSRF token, no auth check
        conn = sqlite3.connect(DB)
        conn.execute("INSERT INTO transactions (user_id,amount,note) VALUES (1,?,?)", (amount, note))
        conn.commit()
        conn.close()
        msg = f'<div class="alert alert-success">✅ Transferred ${amount} to {to_user}</div>'
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>💸 Transfer Funds</h2>
  <div class="alert alert-info">{hint}</div>
  {msg}
  <form method="POST">
    <label>Recipient username</label><input name="to" placeholder="alice">
    <label>Amount ($)</label><input name="amount" type="number" placeholder="100">
    <label>Note</label><input name="note" placeholder="Payment note">
    <button class="btn btn-primary">Transfer</button>
  </form>
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# PROFILE — IDOR (access any user by ?id=)
# ─────────────────────────────────────────────────────────────
@app.route("/profile")
def profile():
    uid = request.args.get("id","1")
    hint = "Change <code style='color:#f85149'>?id=1</code> to <code style='color:#f85149'>?id=2</code> or <code style='color:#f85149'>?id=3</code> — no auth check"
    conn = sqlite3.connect(DB)
    # VULNERABLE: no session/ownership check
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not row:
        return render_template_string(BASE_STYLE + NAV + '<div class="container"><div class="card"><p>User not found</p></div></div>')
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>👤 User Profile</h2>
  <div class="alert alert-info">{hint}</div>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>ID</td><td>{row[0]}</td></tr>
    <tr><td>Username</td><td>{row[1]}</td></tr>
    <tr><td>Password</td><td><span style="color:#f85149">{row[2]}</span> ⚠️ exposed!</td></tr>
    <tr><td>Email</td><td>{row[3]}</td></tr>
    <tr><td>Balance</td><td>${row[4]:,.2f}</td></tr>
    <tr><td>Role</td><td><span class="badge badge-{'admin' if row[5]=='admin' else 'user'}">{row[5]}</span></td></tr>
  </table>
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# FETCH URL — SSRF
# ─────────────────────────────────────────────────────────────
@app.route("/fetch", methods=["GET","POST"])
def fetch_url():
    result = ""
    hint = "Try: <code style='color:#f85149'>http://169.254.169.254/latest/meta-data/</code> or <code style='color:#f85149'>http://localhost/admin</code>"
    if request.method == "POST":
        url = request.form.get("url","")
        try:
            # VULNERABLE: fetches any URL including internal/metadata endpoints
            r = req.get(url, timeout=5, verify=False)
            result = f'<div class="alert alert-success">Status: {r.status_code}<br><pre style="margin-top:10px;overflow:auto;max-height:300px;font-size:12px;color:#3fb950">{r.text[:3000]}</pre></div>'
        except Exception as e:
            result = f'<div class="alert alert-danger">Error: {e}</div>'
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>🌐 Internal URL Fetcher</h2>
  <div class="alert alert-info">{hint}</div>
  <form method="POST">
    <label>URL to fetch</label>
    <input name="url" placeholder="http://example.com">
    <button class="btn btn-blue">Fetch</button>
  </form>
  {result}
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# FILES — DIRECTORY TRAVERSAL
# ─────────────────────────────────────────────────────────────
@app.route("/files")
def files():
    filename = request.args.get("file","welcome.txt")
    hint = "Try: <code style='color:#f85149'>?file=../../../etc/passwd</code> or <code style='color:#f85149'>?file=../app.py</code>"
    content = ""
    try:
        # VULNERABLE: no path sanitisation
        base_dir = os.path.join(os.path.dirname(__file__), "static_files")
        full_path = os.path.join(base_dir, filename)
        with open(full_path, "r", errors="replace") as f:
            content = f.read()
        result = f'<pre style="background:#0d1117;padding:16px;border-radius:6px;overflow:auto;max-height:400px;font-size:12px;color:#3fb950;border:1px solid #30363d">{content}</pre>'
    except Exception as e:
        result = f'<div class="alert alert-danger">Error reading file: {e}<br><small>Attempted path: {os.path.join("static_files", filename)}</small></div>'
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>📁 File Viewer</h2>
  <div class="alert alert-info">{hint}</div>
  <form style="margin-bottom:16px">
    <label>Filename</label>
    <input name="file" value="{filename}">
    <button class="btn btn-blue">View File</button>
  </form>
  {result}
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# REDIRECT — OPEN REDIRECT
# ─────────────────────────────────────────────────────────────
@app.route("/redirect")
def open_redirect():
    url = request.args.get("url","https://vulnbank.com")
    hint = "Try: <code style='color:#f85149'>/redirect?url=https://evil.com</code>"
    # VULNERABLE: no validation of redirect target
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container"><div class="card">
  <h2>↗️ Open Redirect Demo</h2>
  <div class="alert alert-info">{hint}</div>
  <p style="margin-bottom:16px;color:#8b949e">You will be redirected to: <b style="color:#f85149">{url}</b></p>
  <a href="/redirect?url={url}" onclick="window.location='{url}';return false;" class="btn btn-danger">Follow Redirect →</a>
  <br><br>
  <form style="margin-top:16px">
    <label>Redirect to URL</label>
    <input name="url" value="{url}">
    <button class="btn btn-blue">Test Redirect</button>
  </form>
</div></div>
""")

# ─────────────────────────────────────────────────────────────
# ADMIN — No auth check
# ─────────────────────────────────────────────────────────────
@app.route("/admin")
def admin():
    hint = "No authentication required to access this admin panel"
    conn = sqlite3.connect(DB)
    users = conn.execute("SELECT id,username,email,balance,role FROM users").fetchall()
    txns  = conn.execute("SELECT id,user_id,amount,note,created_at FROM transactions ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    user_rows = "".join(
        f"<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td><td>${u[3]:,.2f}</td>"
        f"<td><span class='badge badge-{'admin' if u[4]=='admin' else 'user'}'>{u[4]}</span></td></tr>"
        for u in users
    )
    txn_rows = "".join(
        f"<tr><td>{t[0]}</td><td>{t[1]}</td><td>${t[2]}</td><td>{t[3]}</td><td style='font-size:12px;color:#8b949e'>{t[4]}</td></tr>"
        for t in txns
    )
    return render_template_string(BASE_STYLE + NAV + f"""
<div class="container">
  <div class="alert alert-danger" style="margin-bottom:16px">⚠️ {hint}</div>
  <div class="card">
    <h2>👥 All Users (including passwords visible at /profile?id=N)</h2>
    <table><tr><th>ID</th><th>Username</th><th>Email</th><th>Balance</th><th>Role</th></tr>{user_rows}</table>
  </div>
  <div class="card">
    <h2>💳 Recent Transactions</h2>
    <table><tr><th>ID</th><th>User</th><th>Amount</th><th>Note</th><th>Time</th></tr>{txn_rows}</table>
  </div>
</div>
""")

# ─────────────────────────────────────────────────────────────
# ERROR HANDLER — Stack trace exposed (A09)
# ─────────────────────────────────────────────────────────────
@app.route("/crash")
def crash():
    # VULNERABLE: triggers unhandled exception → exposes stack trace
    raise Exception("Internal server error — stack trace exposed to user!")

# No security headers set anywhere (A05)
# No @app.after_request to add CSP, HSTS, X-Frame-Options etc.

if __name__ == "__main__":
    init_db()
    os.makedirs("static_files", exist_ok=True)
    with open("static_files/welcome.txt","w") as f:
        f.write("Welcome to VulnBank!\nThis is a demo file.\nTry path traversal to read other files.")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
