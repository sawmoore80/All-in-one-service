import os, json, sqlite3, time, secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, jsonify, request, redirect, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_bcrypt import Bcrypt
from backend.oauth_providers import OAUTH

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "admind.db"

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE","0")=="1",
    JSON_SORT_KEYS=False,
)
CORS(app, supports_credentials=True)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        password_hash TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tokens(
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        platform TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at INTEGER,
        raw JSON
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        platform TEXT,
        title TEXT,
        caption TEXT,
        metrics TEXT,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY,
        name TEXT, email TEXT, company TEXT, phone TEXT, message TEXT, created_at TEXT
    )""")
    con.commit(); con.close()

init_db()

class U(UserMixin):
    def __init__(self, id, email): self.id=id; self.email=email

@login_manager.user_loader
def load_user(uid):
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,email FROM users WHERE id=?",(uid,))
    row=cur.fetchone(); con.close()
    return U(row[0],row[1]) if row else None

def ok(**k): k.setdefault("ok",True); return jsonify(k)
def err(msg, **k): k.update({"ok":False,"error":msg}); return jsonify(k)

@app.get("/")
def index_root():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/health")
def health(): return ok(status="healthy")

@app.get("/api/me")
def api_me():
    if current_user.is_authenticated:
        return ok(auth=True,email=current_user.email)
    return ok(auth=False)

@app.post("/api/register")
def api_register():
    p=request.get_json() or {}
    email=p.get("email","").strip().lower(); pw=p.get("password","")
    if not email or not pw: return err("missing_fields"),400
    con=db(); cur=con.cursor()
    try:
        cur.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",(email,bcrypt.generate_password_hash(pw).decode()))
        con.commit()
        cur.execute("SELECT id FROM users WHERE email=?",(email,))
        uid=cur.fetchone()[0]
        login_user(U(uid,email))
        return ok(user_id=uid,email=email)
    except sqlite3.IntegrityError:
        con.close(); return err("email_exists"),409

@app.post("/api/login")
def api_login():
    p=request.get_json() or {}
    email=p.get("email","").strip().lower(); pw=p.get("password","")
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,password_hash FROM users WHERE email=?",(email,))
    row=cur.fetchone(); con.close()
    if not row or not bcrypt.check_password_hash(row[1], pw):
        return err("bad_credentials"),401
    login_user(U(row[0],email))
    return ok(email=email)

@app.post("/api/logout")
def api_logout():
    try: logout_user()
    except Exception: pass
    return ok()

@app.get("/api/kpis")
def kpis():
    return ok(total_spend=4720, avg_roas=1.83, avg_cpa=29, conversions=515)

@app.get("/api/trends")
def trends():
    labels=[f"W-{i}" for i in range(1,8)]
    spend=[520,560,600,640,610,650,690]
    roas=[1.55,1.62,1.68,1.70,1.68,1.76,1.83]
    top={"labels":["Search - Brand","RMK - 7d","Prospecting - Broad","UGC Creators"],"clicks":[1000,780,740,360]}
    return ok(labels=labels,series={"spend":spend,"roas":roas},top=top)

@app.get("/api/insights")
def insights():
    return ok(insights=[
        {"id":1,"title":"Lift ROAS on Prospecting - Broad","campaign_name":"Prospecting - Broad","kpi":"ROAS","severity":"high","priority_score":1.86,"evidence":{"roas":"0.72","spend":1250,"target_roas":"1.00"},"actions":["Add price anchor (MSRP vs Now) + guarantee top-of-frame","Swap first frame to strongest review (stars + count)","Send traffic to highest-CVR LP; strip header nav"],"expected_impact":0.75},
        {"id":2,"title":"Cut CPA on RMK - 7d","campaign_name":"RMK - 7d","kpi":"CPA","severity":"med","priority_score":1.32,"evidence":{"cpa":"$42","avg_cpa":"$29","delta":"+45%"},"actions":["Narrow audience","Update hook + objection","Bid cap -10%"],"expected_impact":0.55}
    ])

@app.post("/api/playbook")
def playbook():
    d=request.get_json() or {}
    ids=set(d.get("insight_ids",[]))
    ins=insights().json["insights"]
    chosen=[i for i in ins if not ids or i["id"] in ids][:7]
    days=[f"Day {i}" for i in range(1,8)]
    plan=[]
    for i, it in enumerate(chosen):
        plan.append({"day":days[i],"title":it["title"],"kpi":it["kpi"],"severity":it["severity"],
                     "what_to_ship":it["actions"][:3],
                     "how_to_measure":[f"Primary KPI: {it['kpi']}",
                                       f"Expected impact: +{int(it['expected_impact']*100)}%",
                                       "Review after 48h vs baseline."]})
    return ok(plan=plan)

@app.get("/api/posts")
@login_required
def posts():
    con=db(); cur=con.cursor()
    cur.execute("SELECT platform,title,caption,metrics,created_at FROM posts WHERE user_id=? ORDER BY id DESC LIMIT 100",(current_user.id,))
    rows=[{"platform":r[0],"title":r[1],"caption":r[2],"metrics":r[3],"created_at":r[4]} for r in cur.fetchall()]
    con.close()
    return ok(posts=rows)

@app.post("/api/social/mock_pull")
@login_required
def mock_pull():
    now=datetime.utcnow().isoformat()
    more=[("Instagram","UGC Hook","Try-on haul","{\"likes\":310,\"comments\":11}"),
          ("TikTok","3 hooks test","A/B/C","{\"plays\":9000,\"likes\":600}")]
    con=db(); cur=con.cursor()
    for p in more:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",
            (current_user.id,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(added=len(more))

@app.get("/api/social/connections")
@login_required
def list_connections():
    con=db(); cur=con.cursor()
    cur.execute("SELECT platform, COUNT(*) FROM tokens WHERE user_id=? GROUP BY platform",(current_user.id,))
    rows={r[0]:r[1]>0 for r in cur.fetchall()}
    con.close()
    plats=["instagram","tiktok","facebook","youtube","linkedin"]
    return ok(connections=[{"platform":p.capitalize(),"connected":bool(rows.get(p))} for p in plats])

@app.get("/api/oauth/<platform>")
@login_required
def oauth_start(platform):
    cfg=OAUTH.get(platform)
    if not cfg or not cfg["client_id"]: return err("provider_not_configured"),400
    state=secrets.token_urlsafe(24)
    request.environ.setdefault("admind.state",{})[state]=platform
    q={"client_id":cfg["client_id"],"redirect_uri":cfg["redirect_uri"],"response_type":"code",
       "scope":cfg["scope"],"state":state,"access_type":"offline","prompt":"consent"}
    return ok(auth_url=f'{cfg["auth_url"]}?{urlencode(q)}')

@app.get("/oauth/callback/<platform>")
def oauth_callback(platform):
    import requests as rq
    cfg=OAUTH.get(platform)
    if not cfg: return err("bad_provider"),400
    code=request.args.get("code"); 
    if not code: return err("missing_code"),400
    data={"client_id":cfg["client_id"],"client_secret":cfg["client_secret"],
          "redirect_uri":cfg["redirect_uri"],"grant_type":"authorization_code","code":code}
    r=rq.post(cfg["token_url"],data=data,headers={"Accept":"application/json"})
    tok=r.json(); access=tok.get("access_token")
    if not access: return err("token_exchange_failed", detail=tok),400
    exp=int(time.time())+int(tok.get("expires_in",3600))
    uid=getattr(current_user,"id",None)
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO tokens(user_id,platform,access_token,refresh_token,expires_at,raw) VALUES(?,?,?,?,?,?)",
                (uid,platform,access,tok.get("refresh_token"),exp,json.dumps(tok)))
    con.commit(); con.close()
    return redirect("/")

@app.post("/api/ai/ask")
def ai_ask():
    q=(request.get_json(silent=True) or {}).get("q","").strip()
    if not q: return ok(answer="Ask me about your posts, competitors, or KPIs.")
    key=os.environ.get("OPENAI_API_KEY")
    if not key:
        tip="Lead with a bold 2s hook, add price anchor + social proof, and ship 3 creative variants to A/B."
        return ok(answer=f"Draft: {tip}")
    import requests as rq
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    body={"model":"gpt-4o-mini","messages":[{"role":"system","content":"You are a performance marketing analyst."},{"role":"user","content":q}]}
    res=rq.post("https://api.openai.com/v1/chat/completions",headers=headers,json=body,timeout=30).json()
    ans=res.get("choices",[{}])[0].get("message",{}).get("content","")
    return ok(answer=ans or "No answer")

@app.post("/api/seed")
def seed():
    con=db(); cur=con.cursor()
    cur.execute("DELETE FROM posts")
    now=datetime.utcnow().isoformat()
    demo=[("Instagram","Spring Drop","New arrivals","{\"likes\":1200}"),
          ("Facebook","Carousel Test","3-card","{\"clicks\":320}"),
          ("YouTube","How we scale ROAS","Case study","{\"views\":18000}")]
    for p in demo: cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",(None,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(message="Seeded")

@app.post("/api/contact")
def contact():
    p=request.get_json() or {}
    if len((p.get("message") or ""))>4000: return err("message_too_long"),400
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO contacts(name,email,company,phone,message,created_at) VALUES(?,?,?,?,?,?)",
        (p.get("name"),p.get("email"),p.get("company"),p.get("phone"),p.get("message"),datetime.utcnow().isoformat()))
    con.commit(); con.close()
    return ok(emailed=False)

@app.after_request
def _hdrs(resp):
    resp.headers["Cache-Control"]="no-store"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5050)))
