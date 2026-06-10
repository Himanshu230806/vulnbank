# VulnBank — Deliberately Vulnerable Demo App

> ⚠️ FOR EDUCATIONAL / SECURITY DEMO PURPOSES ONLY. Never deploy in production.

A fake banking application with intentional vulnerabilities to demonstrate
how web-vuln-scanner detects real security issues.

## Vulnerabilities included

| # | Vulnerability | Where to find it |
|---|---|---|
| 1 | SQL Injection | /login — try `admin'--` as username |
| 2 | Reflected XSS | /search — try `<script>alert('XSS')</script>` |
| 3 | Stored XSS | /messages — post `<img src=x onerror=alert(1)>` |
| 4 | CSRF | /transfer — no CSRF token on form |
| 5 | IDOR | /profile?id=1 → change id to 2,3 |
| 6 | SSRF | /fetch — try `http://169.254.169.254/latest/meta-data/` |
| 7 | Directory Traversal | /files?file=../../../etc/passwd |
| 8 | Open Redirect | /redirect?url=https://evil.com |
| 9 | No Security Headers | Inspect any response — no CSP/HSTS/X-Frame |
| 10 | Info Disclosure | /crash — full stack trace exposed |
| 11 | Broken Access Control | /admin — no login required |
| 12 | Password Exposure | /profile?id=1 — plaintext passwords shown |

## Run locally
```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:8080
```

## Deploy to Render
1. Push this folder to a new GitHub repo
2. Connect the repo on render.com
3. It uses render.yaml automatically
