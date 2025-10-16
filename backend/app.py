import os, json, sqlite3, time, secrets
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from backend.oauth_providers import OAUTH

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP_DIR)
DB_PATH = os.path.join(ROOT, "admind.db")

app = Flask(__name__, static_folder=os.path.join(ROOT,"static"), static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev-secret")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE","0") == "1"

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tokens(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        platform TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at INTEGER,
        raw TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        platform TEXT,
        title TEXT,
        caption TEXT,
        metrics TEXT,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,email TEXT,company TEXT,phone TEXT,message TEXT,created_at TEXT
    )""")
    con.commit(); con.close()

init_db()

class User(UserMixin):
    def __init__(self, row): self.id=row["id"]; self.email=row["email"]

@login_manager.user_loader
def load_user(uid):
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,email FROM users WHERE id=?",(uid,))
    r=cur.fetchone(); con.close()
    return User(r) if r else None

def ok(**k): k.setdefault("ok",True); return jsonify(k)
def err(message, **k): k.update({"ok":False,"error":message}); return jsonify(k)

@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/")
def root():
    return app.send_static_file("index.html")

@app.get("/health")
def health(): return ok(status="healthy")

@app.get("/api/me")
def me():
    if current_user.is_authenticated: return ok(auth=True,email=current_user.email)
    return ok(auth=False)

@app.post("/api/register")
def register():
    p = request.get_json(silent=True) or {}
    email = (p.get("email") or "").strip().lower()
    pw = p.get("password") or ""
    if not email or not pw: return err("missing_fields"), 400
    con=db(); cur=con.cursor()
    cur.execute("SELECT id FROM users WHERE email=?",(email,))
    if cur.fetchone(): con.close(); return err("email_exists"), 400
    ph = bcrypt.generate_password_hash(pw).decode()
    cur.execute("INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",(email,ph,datetime.utcnow().isoformat()))
    con.commit()
    cur.execute("SELECT id,email FROM users WHERE email=?",(email,))
    u=cur.fetchone(); con.close()
    login_user(User(u))
    return ok()

@app.post("/api/login")
def login():
    p = request.get_json(silent=True) or {}
    email = (p.get("email") or "").strip().lower()
    pw = p.get("password") or ""
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,email,password_hash FROM users WHERE email=?",(email,))
    u=cur.fetchone(); con.close()
    if not u or not bcrypt.check_password_hash(u["password_hash"], pw):
        return err("invalid_credentials"), 401
    login_user(User(u))
    return ok()

@app.post("/api/logout")
def logout():
    logout_user(); return ok()

# ---------- Mock KPIs/Trends/Insights ----------
@app.get("/api/kpis")
def kpis():
    return ok(total_spend=4720, avg_roas=1.83, avg_cpa=29, conversions=515)

@app.get("/api/trends")
def trends():
    labels=[f"W-{i}" for i in range(1,8)]
    spend=[520,560,600,640,610,650,690]
    roas=[1.55,1.62,1.68,1.70,1.73,1.78,1.82]
    top={"labels":["Search - Brand","RMK - 7d","Prospecting - Broad","UGC Creators"],"clicks":[1000,780,740,360]}
    return ok(labels=labels, series={"spend":spend,"roas":roas}, top=top)

@app.get("/api/insights")
def insights():
    return ok(insights=[
        {"id":1,"title":"Lift ROAS on Prospecting - Broad","campaign_name":"Prospecting - Broad","kpi":"ROAS","severity":"high","priority_score":1.86,"evidence":{"roas":"0.72","spend":1250,"target_roas":"1.00"},"actions":["Add price anchor (MSRP vs Now) + guarantee top-of-frame","Swap first frame to strongest review (stars + count)","Send traffic to highest-CVR LP; strip header nav"],"expected_impact":0.75},
        {"id":2,"title":"Cut CPA on RMK - 7d","campaign_name":"RMK - 7d","kpi":"CPA","severity":"med","priority_score":1.32,"evidence":{"cpa":"$42","avg_cpa":"$29","delta":"+45%"},"actions":["Narrow audience","Update hook + objection","Bid cap -10%"],"expected_impact":0.55}
    ])

@app.post("/api/playbook")
def playbook():
    d=request.get_json(silent=True) or {}
    selected = set(d.get("insight_ids") or [])
    conns = ["Day 1","Day 2","Day 3","Day 4","Day 5","Day 6","Day 7"]
    ins = insights().get_json()["insights"]
    chosen = [i for i in ins if not selected or i["id"] in selected][:7]
    plan=[]
    for i, it in enumerate(chosen):
        plan.append({"day":conns[i],"title":it["title"],"kpi":it["kpi"],"severity":it["severity"],"what_to_ship":it["actions"],"how_to_measure":[f"Primary KPI: {it['kpi']}", f"Expected impact: +{int((it.get('expected_impact') or 0)*100)}%","Review after 48h"]})
    return ok(plan=plan)

# ---------- Social OAuth ----------
@app.get("/api/oauth/<platform>")
@login_required
def oauth_start(platform):
    cfg = OAUTH.get(platform)
    if not cfg: return err("bad_provider"), 400
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state
    }
    from urllib.parse import urlencode
    return ok(auth_url=f"{cfg['auth_url']}?{urlencode(params)}")

@app.get("/oauth/callback/<platform>")
@login_required
def oauth_callback(platform):
    import requests as rq
    cfg = OAUTH.get(platform)
    if not cfg: return err("bad_provider"), 400
    code = request.args.get("code")
    if not code: return err("missing_code"), 400
    data = {"client_id":cfg["client_id"],"client_secret":cfg["client_secret"],"redirect_uri":cfg["redirect_uri"],"grant_type":"authorization_code","code":code}
    r = rq.post(cfg["token_url"], data=data, headers={"Accept":"application/json"})
    tok = r.json()
    access = tok.get("access_token")
    if not access: return err("token_exchange_failed", detail=tok), 400
    exp = int(time.time()) + int(tok.get("expires_in",3600))
    con = db(); cur = con.cursor()
    cur.execute("INSERT INTO tokens(user_id,platform,access_token,refresh_token,expires_at,raw) VALUES(?,?,?,?,?,?)",
                (current_user.id, platform, access, tok.get("refresh_token"), exp, json.dumps(tok)))
    con.commit(); con.close()
    return redirect("/")

@app.get("/api/social/connections")
@login_required
def social_connections():
    con=db(); cur=con.cursor()
    cur.execute("SELECT platform, COUNT(1) as c FROM tokens WHERE user_id=? GROUP BY platform",(current_user.id,))
    rows=cur.fetchall(); con.close()
    have=set([r["platform"] for r in rows if r["c"]>0])
    allp = ["instagram","tiktok","facebook","youtube","linkedin"]
    return ok(connections=[{"platform":p.capitalize(), "connected": p in have} for p in allp])

# ---------- Posts (demo + "connected" badge) ----------
@app.get("/api/posts")
def posts():
    uid = getattr(current_user,"id",None)
    con=db(); cur=con.cursor()
    if uid:
        cur.execute("SELECT platform,title,caption,metrics FROM posts WHERE user_id=? ORDER BY id DESC LIMIT 200",(uid,))
        rows = [dict(r) for r in cur.fetchall()]
        # if tokens exist, show connected label
        cur.execute("SELECT DISTINCT platform FROM tokens WHERE user_id=?",(uid,))
        plats = [r["platform"] for r in cur.fetchall()]
    else:
        rows = []
        plats = []
    if not rows:
        rows = [
            {"platform":"Instagram","title":"Spring Drop","caption":"New arrivals","metrics":"{\"likes\":1200}"},
            {"platform":"TikTok","title":"Behind the scenes","caption":"BTS shoot","metrics":"{\"plays\":9000}"},
            {"platform":"YouTube","title":"How we scale ROAS","caption":"Case study","metrics":"{\"views\":18000}"}
        ]
    for r in rows:
        if r["platform"].lower() in plats: r["platform"] += " (connected)"
    return ok(posts=rows)

@app.post("/api/social/mock_pull")
@login_required
def mock_pull():
    now=datetime.utcnow().isoformat()
    data=[("Instagram","UGC Hook","Try-on haul","{\"likes\":310,\"comments\":11}"),
          ("TikTok","Test 3 hooks","3 cuts A/B","{\"plays\":9000,\"likes\":600}")]
    con=db(); cur=con.cursor()
    for p in data:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",
                    (current_user.id,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(added=len(data))

# ---------- AI ----------
@app.post("/api/ai/ask")
def ai_ask():
    q=(request.get_json(silent=True) or {}).get("q","").strip()
    if not q: return ok(answer="Ask about your posts, competitors, or KPIs.")
    key=os.environ.get("OPENAI_API_KEY")
    if not key:
        tip="Lead with a bold 2s hook, add price anchor + social proof, and ship 3 creative variants to A/B."
        return ok(answer=tip)
    import requests as rq
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    body={"model":"gpt-4o-mini","messages":[{"role":"system","content":"You are a sharp performance marketing analyst that gives concise, practical recommendations."},{"role":"user","content":q}]}
    res=rq.post("https://api.openai.com/v1/chat/completions",headers=headers,json=body,timeout=30).json()
    ans=(res.get("choices") or [{}])[0].get("message",{}).get("content","")
    return ok(answer=ans or "No answer")

# ---------- Contact ----------
@app.post("/api/contact")
def contact():
    p=request.get_json(silent=True) or {}
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO contacts(name,email,company,phone,message,created_at) VALUES(?,?,?,?,?,?)",
                (p.get("name"),p.get("email"),p.get("company"),p.get("phone"),p.get("message"),datetime.utcnow().isoformat()))
    con.commit(); con.close()
    return ok(emailed=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5050)))
