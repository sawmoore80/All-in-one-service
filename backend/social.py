import os, json, sqlite3, time, requests
from urllib.parse import urlencode
from flask import Blueprint, request, redirect

bp = Blueprint("social", __name__)

def db():
    con = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "admind.db"))
    con.row_factory = sqlite3.Row
    return con

# ---------- OAuth URL builders (need client IDs in .env) ----------
BASE = {
    "instagram": "https://api.instagram.com/oauth/authorize",
    "facebook":  "https://www.facebook.com/v18.0/dialog/oauth",
    "tiktok":    "https://www.tiktok.com/auth/authorize/",
    "youtube":   "https://accounts.google.com/o/oauth2/v2/auth",
}

SCOPES = {
    "instagram": ["user_profile","user_media"],
    "facebook":  ["pages_read_engagement","pages_show_list","public_profile"],
    "tiktok":    ["user.info.basic","video.list"],
    "youtube":   ["https://www.googleapis.com/auth/youtube.readonly"],
}

def client_id(p): return os.getenv({
    "instagram":"IG_CLIENT_ID","facebook":"FB_CLIENT_ID","tiktok":"TT_CLIENT_ID","youtube":"YT_CLIENT_ID"
}[p], "")

def client_secret(p): return os.getenv({
    "instagram":"IG_CLIENT_SECRET","facebook":"FB_CLIENT_SECRET","tiktok":"TT_CLIENT_SECRET","youtube":"YT_CLIENT_SECRET"
}[p], "")

def redirect_uri(p):
    root = os.getenv("PUBLIC_URL","http://localhost:5000")
    return f"{root}/oauth/callback/{p}"

@bp.get("/api/oauth/<platform>")
def oauth_start(platform):
    platform = platform.lower()
    if platform not in BASE: return {"ok": False, "error":"unsupported"}, 400
    cid = client_id(platform)
    if not cid: return {"ok": False, "error":"missing_client_id"}, 400
    state = str(int(time.time()))
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri(platform),
        "response_type": "code",
        "scope": " ".join(SCOPES[platform]),
        "state": state,
        "access_type": "offline" if platform=="youtube" else None,
        "include_granted_scopes": "true" if platform=="youtube" else None,
    }
    params = {k:v for k,v in params.items() if v}
    return {"ok": True, "auth_url": f"{BASE[platform]}?{urlencode(params)}"}

# ---------- OAuth callback placeholders (store code; attempt token if secrets present) ----------
@bp.get("/oauth/callback/<platform>")
def oauth_cb(platform):
    code = request.args.get("code"); state = request.args.get("state","")
    if not code: return redirect("/?oauth=error")
    # Store the auth "connection" (demo)
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS connections(
        id INTEGER PRIMARY KEY, platform TEXT, access_token TEXT, refresh_token TEXT, created_at TEXT)""")
    con.commit()

    tok = None
    try:
        if client_id(platform) and client_secret(platform):
            # NOTE: Real token exchanges vary per platform; we keep a safe placeholder
            # so you can see successful round-trips. Replace with real exchanges when IDs exist.
            tok = {"access_token": f"demo-{platform}-{int(time.time())}"}
    except Exception:
        tok = None

    cur.execute("INSERT INTO connections(platform,access_token,refresh_token,created_at) VALUES(?,?,?,datetime('now'))",
                (platform, (tok or {}).get("access_token","auth_code:"+code), (tok or {}).get("refresh_token")))
    con.commit(); con.close()
    return redirect("/?oauth=ok")

# ---------- Pull posts (demo makes real DB rows) ----------
@bp.post("/api/social/mock_pull")
def mock_pull():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY, platform TEXT, title TEXT, caption TEXT, metrics TEXT, created_at TEXT)""")
    now = int(time.time())
    rows = [
        ("Instagram","Spring Drop","New arrivals","{\"likes\":420,\"comments\":18}",now),
        ("TikTok","UGC hooks A/B","3 hooks test","{\"plays\":9100,\"likes\":600}",now),
        ("YouTube","How we scaled ROAS","Case study","{\"views\":5400,\"likes\":210}",now),
    ]
    for r in rows:
        cur.execute("INSERT INTO posts(platform,title,caption,metrics,created_at) VALUES(?,?,?,?,datetime('now'))",
                    (r[0],r[1],r[2],r[3]))
    con.commit(); con.close()
    return {"ok": True, "added": len(rows)}

@bp.get("/api/social/connections")
def connections():
    con=db(); cur=con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS connections(id INTEGER PRIMARY KEY, platform TEXT, access_token TEXT, refresh_token TEXT, created_at TEXT)")
    con.commit()
    cur.execute("SELECT platform, access_token FROM connections ORDER BY created_at DESC")
    out=[{"platform":r["platform"],"connected": bool(r["access_token"])} for r in cur.fetchall()]
    con.close()
    return {"ok": True, "connections": out}
