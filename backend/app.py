import os, sqlite3, json, smtplib
from email.message import EmailMessage
from datetime import datetime
from flask import Flask, request, send_from_directory
from flask_login import LoginManager, login_user, logout_user, UserMixin, current_user
from flask_bcrypt import Bcrypt

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)  # repo root
DB_PATH = os.path.join(ROOT, "admind.db")

app = Flask(__name__, static_folder=os.path.join(ROOT, "static"), static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","supersecretkey")
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["SESSION_COOKIE_SECURE"]=os.environ.get("SESSION_COOKIE_SECURE","1")=="1"
bcrypt = Bcrypt(app)
login = LoginManager(app)

# ---------- DB ----------
def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      pw_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      platform TEXT, title TEXT, caption TEXT, metrics TEXT,
      created_at TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, email TEXT, company TEXT, phone TEXT, message TEXT,
      created_at TEXT NOT NULL
    )""")
    con.commit(); con.close()
init_db()

# ---------- Auth ----------
class User(UserMixin):
    def __init__(self, rid, email): self.id=rid; self.email=email

@login.user_loader
def load_user(uid):
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,email FROM users WHERE id=?",(uid,))
    row=cur.fetchone(); con.close()
    return User(row["id"],row["email"]) if row else None

# ---------- Helpers ----------
def ok(**kw): return {"ok": True, **kw}

@app.after_request
def headers(resp):
    resp.headers["Cache-Control"]="no-store"
    resp.headers["X-AdMind"]="ok"
    return resp

# ---------- Static ----------
@app.get("/")
def index(): return send_from_directory(app.static_folder, "index.html")

# ---------- Health ----------
@app.get("/health")
def health(): return ok(status="healthy")

@app.get("/api/test")
def api_test(): return ok(message="AdMind alive", user=getattr(current_user,"email","guest"))

# ---------- Auth endpoints ----------
@app.get("/api/me")
def me():
    if getattr(current_user, "is_authenticated", False):
        return ok(auth=True, email=current_user.email)
    return ok(auth=False)

@app.post("/api/register")
def register():
    p = request.get_json(silent=True) or {}
    email = (p.get("email") or "").strip().lower()
    pw = p.get("password") or ""
    if not email or not pw: return {"ok": False, "error":"missing_fields"}, 400
    con=db(); cur=con.cursor()
    try:
        cur.execute("INSERT INTO users(email,pw_hash,created_at) VALUES(?,?,?)",
                    (email, bcrypt.generate_password_hash(pw).decode(), datetime.utcnow().isoformat()))
        con.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError:
        con.close(); return {"ok": False, "error":"email_exists"}, 400
    con.close(); login_user(User(uid,email))
    return ok()

@app.post("/api/login")
def login_route():
    p = request.get_json(silent=True) or {}
    email=(p.get("email") or "").strip().lower()
    pw=p.get("password") or ""
    con=db(); cur=con.cursor()
    cur.execute("SELECT id,email,pw_hash FROM users WHERE email=?",(email,))
    row=cur.fetchone(); con.close()
    if not row or not bcrypt.check_password_hash(row["pw_hash"], pw):
        return {"ok": False, "error":"invalid_credentials"}, 400
    login_user(User(row["id"],row["email"]))
    return ok()

@app.post("/api/logout")
def logout_route():
    try: logout_user()
    except: pass
    return ok()

# ---------- Demo data / analytics ----------
@app.post("/api/seed")
def seed():
    uid=getattr(current_user,"id",None)
    now=datetime.utcnow().isoformat()
    demo=[("Instagram","Spring Drop","New arrivals","{\"likes\":420,\"comments\":18}"),
          ("TikTok","BTS","Behind the scenes","{\"plays\":12000,\"likes\":900}"),
          ("YouTube","Scale ROAS","Case study","{\"views\":8000,\"avg_view\":3.1}")]
    con=db(); cur=con.cursor()
    for p in demo:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",
                    (uid,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(message="Demo seeded")

@app.get("/api/kpis")
def kpis():
    con=db(); cur=con.cursor()
    cur.execute("SELECT COUNT(*) c FROM posts")
    c=cur.fetchone()["c"]; con.close()
    return ok(total_spend=4720, avg_roas=1.83, avg_cpa=29, conversions=515+c)

@app.get("/api/trends")
def trends():
    labels=[f"W-{i}" for i in range(1,8)]
    return ok(labels=labels,
              series={"spend":[520,560,600,640,610,650,690],
                      "roas":[1.55,1.62,1.68,1.70,1.73,1.78,1.82]},
              top={"labels":["Search - Brand","RMK - 7d","Prospecting - Broad","UGC Creators"],
                   "clicks":[1000,780,740,360]})

@app.get("/api/insights")
def insights():
    data=[{
        "id":1,"title":"Lift ROAS on Prospecting - Broad","campaign_name":"Prospecting - Broad",
        "kpi":"ROAS","severity":"high","priority_score":1.86,
        "evidence":{"roas":"0.72","spend":1250,"target_roas":"1.00"},
        "actions":["Add price anchor (MSRP vs Now) + guarantee top-of-frame",
                   "Swap first frame to strongest review (stars + count)",
                   "Send traffic to highest-CVR LP; strip header nav"],
        "expected_impact":0.75
    },{
        "id":2,"title":"Cut CPA on RMK - 7d","campaign_name":"RMK - 7d",
        "kpi":"CPA","severity":"med","priority_score":1.32,
        "evidence":{"cpa":"$42","avg_cpa":"$29","delta":"+45%"},
        "actions":["Narrow audience","Update hook + objection","Bid cap -10%"],
        "expected_impact":0.55
    }]
    return ok(insights=data)

@app.post("/api/playbook")
def playbook():
    p=request.get_json(silent=True) or {}
    sel=p.get("insight_ids")
    all_=insights()["insights"]
    chosen=[i for i in all_ if not sel or i["id"] in set(sel)] or all_[:5]
    days=["Day 1","Day 2","Day 3","Day 4","Day 5","Day 6","Day 7"]
    plan=[]
    for i,ins in enumerate(chosen[:7]):
        plan.append({"day":days[i],"title":ins["title"],"kpi":ins["kpi"],"severity":ins["severity"],
                     "what_to_ship":ins["actions"][:3],
                     "how_to_measure":[f"Primary KPI: {ins['kpi']}",
                                       f"Expected impact: +{int(ins['expected_impact']*100)}%",
                                       "Review after 48h; keep if KPI improves vs baseline."]})
    return ok(plan=plan)

# ---------- Posts ----------
@app.get("/api/posts")
def posts():
    uid=getattr(current_user,"id",None)
    con=db(); cur=con.cursor()
    if uid: cur.execute("SELECT platform,title,caption,metrics,created_at FROM posts WHERE user_id=? ORDER BY id DESC",(uid,))
    else:   cur.execute("SELECT platform,title,caption,metrics,created_at FROM posts ORDER BY id DESC")
    rows=[dict(r) for r in cur.fetchall()]
    con.close()
    return ok(posts=rows)

@app.post("/api/social/mock_pull")
def mock_pull():
    uid=getattr(current_user,"id",None)
    now=datetime.utcnow().isoformat()
    more=[("Instagram","UGC Hook","Try-on haul","{\"likes\":310,\"comments\":11}"),
          ("TikTok","Test 3 hooks","3 cuts A/B","{\"plays\":9000,\"likes\":600}")]
    con=db(); cur=con.cursor()
    for p in more:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",
                    (uid,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(added=len(more))

# ---------- Social OAuth placeholders ----------
@app.get("/api/oauth/<platform>")
def oauth(platform):
    return ok(auth_url=f"https://auth.{platform}.com/demo")

@app.get("/api/social/connections")
def connections():
    return ok(connections=[{"platform":"Instagram","connected":False},
                           {"platform":"TikTok","connected":False},
                           {"platform":"Facebook","connected":False},
                           {"platform":"YouTube","connected":False}])

# ---------- AI ----------
@app.post("/api/ai/ask")
def ai_ask():
    q=(request.get_json(silent=True) or {}).get("q","")
    tip="Use a stronger first 2 seconds and add social proof."
    if "competitor" in q.lower():
        tip="Identify top 3 competitors, mirror their highest-CTR hooks, then differentiate with a price anchor and guarantee."
    return ok(answer=f"🤖 On '{q}': {tip}")

# ---------- Contact (stores + optional email) ----------
@app.post("/api/contact")
def contact():
    p=request.get_json(silent=True) or {}
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO contacts(name,email,company,phone,message,created_at) VALUES(?,?,?,?,?,?)",
                (p.get("name"),p.get("email"),p.get("company"),p.get("phone"),p.get("message"),datetime.utcnow().isoformat()))
    con.commit(); con.close()
    emailed=False
    if os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"):
        try:
            msg=EmailMessage(); msg["Subject"]="AdMind Contact"; msg["From"]=os.environ["SMTP_USER"]
            msg["To"]=os.environ.get("CONTACT_TO","sawmoore80@gmail.com"); msg.set_content(json.dumps(p,indent=2))
            import ssl, smtplib
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT","465"))) as s:
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"]); s.send_message(msg)
            emailed=True
        except Exception: emailed=False
    return ok(emailed=emailed)

@app.get("/_ping")
def _ping(): return ok(pong=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))


from auth import bp as auth_bp
app.register_blueprint(auth_bp)
