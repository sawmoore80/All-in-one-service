import os, sqlite3, hashlib, hmac
from flask import Blueprint, request, session

bp = Blueprint("auth", __name__)

def db():
    con = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "admind.db"))
    con.row_factory = sqlite3.Row
    return con

def init():
    con=db(); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw_hash TEXT, created_at TEXT)""")
    con.commit(); con.close()

def _hash(pw:str)->str:
    salt = os.getenv("SECRET_KEY","salt").encode()
    return hashlib.sha256(salt + pw.encode()).hexdigest()

@bp.post("/api/register")
def register():
    init()
    j=request.get_json(silent=True) or {}
    email=(j.get("email") or "").strip().lower()
    pw=j.get("password") or ""
    if not email or not pw: return {"ok":False,"error":"missing email/password"},400
    try:
        con=db(); cur=con.cursor()
        cur.execute("INSERT INTO users(email,pw_hash,created_at) VALUES(?,?,datetime('now'))",(email,_hash(pw)))
        con.commit(); user_id=cur.lastrowid; con.close()
        session["uid"]=user_id; session["email"]=email
        return {"ok":True,"email":email}
    except Exception:
        return {"ok":False,"error":"email already registered"},409

@bp.post("/api/login")
def login():
    init()
    j=request.get_json(silent=True) or {}
    email=(j.get("email") or "").strip().lower()
    pw=j.get("password") or ""
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,pw_hash FROM users WHERE email=?",(email,))
    row=cur.fetchone(); con.close()
    if not row: return {"ok":False,"error":"not found"},404
    if not hmac.compare_digest(row["pw_hash"], _hash(pw)): return {"ok":False,"error":"bad password"},401
    session["uid"]=row["id"]; session["email"]=email
    return {"ok":True,"email":email}

@bp.post("/api/logout")
def logout():
    session.clear(); return {"ok":True}

@bp.get("/api/me")
def me():
    return {"ok":True, "auth": bool(session.get("uid")), "email": session.get("email")}
