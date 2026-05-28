#!/usr/bin/env python3
"""
与 cloudflare_temp_email 兼容的轻量临时邮箱 API（供 VPS + Postfix 使用）。
"""

import email
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from email import policy
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt

# 配置（可由环境变量覆盖）
DOMAIN = os.environ.get("EMAIL_DOMAIN", "metoolbot.top")
JWT_SECRET = os.environ.get("EMAIL_JWT_SECRET", "")
DB_PATH = Path(os.environ.get("EMAIL_DB_PATH", "/opt/aws-builder-id/data/email.db"))
HOST = os.environ.get("EMAIL_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMAIL_API_PORT", "18787"))
STATIC_DIR = Path(__file__).resolve().parent / "static"


def get_secret():
    """读取或生成 JWT 密钥。"""
    global JWT_SECRET
    secret_file = DB_PATH.parent / ".email_jwt_secret"
    if JWT_SECRET:
        return JWT_SECRET
    if secret_file.exists():
        JWT_SECRET = secret_file.read_text(encoding="utf-8").strip()
        return JWT_SECRET
    JWT_SECRET = os.urandom(32).hex()
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(JWT_SECRET, encoding="utf-8")
    os.chmod(secret_file, 0o600)
    return JWT_SECRET


def init_db():
    """初始化 SQLite 数据库。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_part TEXT NOT NULL,
            full_address TEXT NOT NULL UNIQUE,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mails (
            id TEXT PRIMARY KEY,
            full_address TEXT NOT NULL,
            raw TEXT NOT NULL,
            subject TEXT,
            sender TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mails_addr ON mails(full_address);
        """
    )
    conn.commit()
    conn.close()


def db_conn():
    """获取数据库连接。"""
    return sqlite3.connect(DB_PATH)


def create_address(local_part: str):
    """
    创建邮箱地址并签发 JWT。
    返回: (address, jwt_token)
    """
    local_part = re.sub(r"[^a-z0-9._-]", "", local_part.lower())[:64] or uuid.uuid4().hex[:10]
    full = f"{local_part}@{DOMAIN}"
    conn = db_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO addresses (local_part, full_address, created_at) VALUES (?,?,?)",
            (local_part, full, time.time()),
        )
        conn.commit()
    finally:
        conn.close()
    token = jwt.encode({"addr": full, "sub": local_part}, get_secret(), algorithm="HS256")
    return full, token


def decode_token(token: str):
    """解析 JWT，返回邮箱地址。"""
    payload = jwt.decode(token, get_secret(), algorithms=["HS256"])
    return payload.get("addr") or f"{payload.get('sub')}@{DOMAIN}"


def store_incoming(recipient: str, raw_bytes: bytes):
    """
    保存入站邮件（由 Postfix 管道脚本调用）。
    """
    recipient = recipient.strip().lower()
    if "@" not in recipient:
        recipient = f"{recipient}@{DOMAIN}"
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)
    mail_id = str(uuid.uuid4())
    conn = db_conn()
    try:
        conn.execute(
            "INSERT INTO mails (id, full_address, raw, subject, sender, created_at) VALUES (?,?,?,?,?,?)",
            (
                mail_id,
                recipient,
                raw_bytes.decode("utf-8", errors="replace"),
                msg.get("Subject", ""),
                msg.get("From", ""),
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return mail_id


def list_mails(full_address: str, limit: int = 20, offset: int = 0):
    """列出某邮箱的邮件。"""
    conn = db_conn()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, raw, subject, sender, created_at FROM mails WHERE full_address=? "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (full_address.lower(), limit, offset),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "raw": r["raw"],
                "subject": r["subject"],
                "from": r["sender"],
                "source": r["sender"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_mail(mail_id: str, full_address: str):
    """获取单封邮件详情。"""
    conn = db_conn()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, raw, subject, sender FROM mails WHERE id=? AND full_address=?",
            (mail_id, full_address.lower()),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "raw": row["raw"],
            "subject": row["subject"],
            "from": row["sender"],
            "text": row["raw"],
        }
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    """HTTP API 与 Web 收件箱处理器。"""

    def log_message(self, fmt, *args):
        print(f"[email-api] {self.address_string()} - {fmt % args}")

    def _html(self, code, body: bytes, content_type="text/html; charset=utf-8"):
        """返回 HTML 页面。"""
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, name: str):
        """提供 static/ 目录下的静态文件。"""
        path = (STATIC_DIR / name).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())):
            self.send_error(403)
            return
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        ctype = "text/html; charset=utf-8" if path.suffix == ".html" else "application/octet-stream"
        self._html(200, body, ctype)

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _bearer(self):
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""

    def do_POST(self):
        if self.path.rstrip("/") == "/api/new_address":
            data = self._read_json()
            name = str(data.get("name", "")).strip()
            address, token = create_address(name)
            self._json(200, {"jwt": token, "address": address})
            return
        self.send_error(404)

    def do_HEAD(self):
        """支持 HEAD（Nginx/健康检查常用）。"""
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            path = (STATIC_DIR / "index.html").resolve()
            if path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                return
        if parsed.path == "/api/health":
            body = json.dumps({"ok": True, "domain": DOMAIN}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if parsed.path == "/api/health":
            self._json(200, {"ok": True, "domain": DOMAIN})
            return
        token = self._bearer()
        if not token:
            self.send_error(401)
            return
        try:
            addr = decode_token(token)
        except Exception:
            self.send_error(401)
            return
        if parsed.path == "/api/mails":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            offset = int(qs.get("offset", ["0"])[0])
            self._json(200, list_mails(addr, limit, offset))
            return
        m = re.match(r"^/api/mails/([^/]+)$", parsed.path)
        if m:
            detail = get_mail(m.group(1), addr)
            if detail:
                self._json(200, detail)
            else:
                self.send_error(404)
            return
        self.send_error(404)


def main():
    """启动 HTTP 服务。"""
    init_db()
    get_secret()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"临时邮箱 API 监听 http://{HOST}:{PORT}  域名={DOMAIN}  DB={DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "store":
        recipient = sys.argv[2] if len(sys.argv) > 2 else ""
        raw = sys.stdin.buffer.read()
        store_incoming(recipient, raw)
        print("stored")
    else:
        main()
