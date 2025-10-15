import os, json, sqlite3
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, send_from_directory, request, session

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(ROOT)
DB_PATH = os.path.join(APP_ROOT, "admind.db")

app = Flask(__name__, static_folder=os.path.join(APP_ROOT, "static"), static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY","super-secret")

def ok(**kw): return {"ok": True, **kw}
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con=db(); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw_hash TEXT, created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY, user_id INTEGER, platform TEXT, title TEXT, caption TEXT, metrics TEXT, created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY, name TEXT, email TEXT, company TEXT, phone TEXT, message TEXT, created_at TEXT)""")
    con.commit(); con.close()
init_db()

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/health")
def health():
    return ok(status="healthy")

try:
    from backend.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
except Exception:
    @app.post("/api/register")
    def _r(): return {"ok":False,"error":"auth not loaded"},500
    @app.post("/api/login")
    def _l(): return {"ok":False,"error":"auth not loaded"},500
    @app.post("/api/logout")
    def _o(): session.clear(); return ok()
    @app.get("/api/me")
    def _m(): return ok(auth=False)

@app.post("/api/seed")
def seed():
    labels=[f"W-{i}" for i in range(1,8)]
    con=db(); cur=con.cursor()
    uid = session.get("uid")
    now = datetime.utcnow().isoformat()
    demo = [("Instagram","Launch post","New drop","{\"likes\":420,\"comments\":23}"),
            ("TikTok","UGC Hook Test","3 hooks A/B","{\"plays\":12000,\"likes\":780}"),
            ("YouTube","Case study","Scaling ROAS","{\"views\":5400,\"likes\":210}")]
    for p in demo:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",(uid,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(labels=labels, added=len(demo))

@app.get("/api/kpis")
def kpis():
    return ok(total_spend=4720, avg_roas=1.83, avg_cpa=29, conversions=515)

@app.get("/api/trends")
def trends():
    return ok(
        labels=["W-1","W-2","W-3","W-4","W-5","W-6","W-7"],
        series={"spend":[520,560,600,640,610,650,690],"roas":[1.55,1.62,1.68,1.70,1.73,1.78,1.82]},
        top={"labels":["Search - Brand","RMK - 7d","Prospecting - Broad","UGC Creators"],"clicks":[1000,780,740,360]}
    )

@app.get("/api/insights")
def insights():
    rows = [
        {"id":1,"title":"Lift ROAS on Prospecting - Broad","campaign_name":"Prospecting - Broad","kpi":"ROAS","severity":"high","priority_score":1.86,"expected_impact":0.75,"evidence":{"roas":"0.72","spend":1250,"target_roas":"1.00"},"actions":["Add price anchor (MSRP vs Now) + guarantee top-of-frame","Swap first frame to strongest review (stars + count)","Send traffic to highest-CVR LP; strip header nav"]},
        {"id":2,"title":"Cut CPA on RMK - 7d","campaign_name":"RMK - 7d","kpi":"CPA","severity":"med","priority_score":1.32,"expected_impact":0.55,"evidence":{"cpa":"$42","avg_cpa":"$29","delta":"+45%"},"actions":["Narrow audience","Update hook + objection","Bid cap -10%"]},
    ]
    return ok(insights=rows)

@app.post("/api/playbook")
def playbook():
    sel = (request.get_json(silent=True) or {}).get("insight_ids")
    chosen = [i for i in insights()["insights"] if not sel or i["id"] in set(sel)][:7]
    days = ["Day 1","Day 2","Day 3","Day 4","Day 5","Day 6","Day 7"]
    plan=[]
    for idx, ins in enumerate(chosen):
        plan.append({"day":days[idx],"title":ins["title"],"kpi":ins["kpi"],"severity":ins["severity"],
            "what_to_ship": ins["actions"][:3],
            "how_to_measure":[f"Primary KPI: {ins['kpi']}", f"Expected impact: +{int(ins['expected_impact']*100)}%", "Review after 48h; keep if KPI improves vs baseline."]})
    return ok(plan=plan)

@app.get("/api/posts")
def posts():
    con=db(); cur=con.cursor()
    cur.execute("SELECT platform,title,caption FROM posts ORDER BY id DESC LIMIT 50")
    rows=[dict(r) for r in cur.fetchall()]; con.close()
    return ok(posts=rows)

@app.post("/api/social/mock_pull")
def mock_pull():
    uid=session.get("uid"); now=datetime.utcnow().isoformat()
    more=[("Instagram","UGC Hook","Try-on haul","{\"likes\":310,\"comments\":11}"),
          ("TikTok","Test 3 hooks","3 cuts A/B","{\"plays\":9000,\"likes\":600}")]
    con=db(); cur=con.cursor()
    for p in more:
        cur.execute("INSERT INTO posts(user_id,platform,title,caption,metrics,created_at) VALUES(?,?,?,?,?,?)",(uid,p[0],p[1],p[2],p[3],now))
    con.commit(); con.close()
    return ok(added=len(more))

@app.get("/api/oauth/<platform>")
def oauth_start(platform):
    urls={
        "instagram":"https://www.instagram.com/accounts/login/",
        "tiktok":"https://www.tiktok.com/login",
        "facebook":"https://www.facebook.com/login.php",
        "youtube":"https://accounts.google.com/ServiceLogin"
    }
    return ok(auth_url=urls.get(platform,"https://example.com"))

@app.get("/api/social/connections")
def connections():
    return ok(connections=[{"platform":"Instagram","connected":False},{"platform":"TikTok","connected":False},{"platform":"Facebook","connected":False},{"platform":"YouTube","connected":False}])

@app.post("/api/ai/ask")
def ai_ask():
    q=(request.get_json(silent=True) or {}).get("q","")
    if "competit" in q.lower():
        ans="Identify top 3 competitors by share of voice; mirror their highest-CTR hooks then differentiate with price anchor + guarantee."
    else:
        ans="Use a stronger first 2 seconds, add social proof, and test 3 hooks with clear CTA."
    return ok(answer=f"🤖 {ans}")

@app.post("/api/contact")
def contact():
    p=request.get_json(silent=True) or {}
    if len((p.get("message") or ""))>500: return {"ok":False,"error":"message too long"},400
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO contacts(name,email,company,phone,message,created_at) VALUES(?,?,?,?,?,?)",
                (p.get("name"),p.get("email"),p.get("company"),p.get("phone"),p.get("message"),datetime.utcnow().isoformat()))
    con.commit(); con.close()
    emailed=False
    if os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"):
        try:
            msg=EmailMessage(); msg["Subject"]="AdMind Contact"; msg["From"]=os.environ["SMTP_USER"]
            msg["To"]=os.environ.get("CONTACT_TO","sawmoore80@gmail.com"); msg.set_content(json.dumps(p,indent=2))
            import smtplib, ssl
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT","465"))) as s:
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"]); s.send_message(msg)
            emailed=True
        except Exception: emailed=False
    return ok(emailed=emailed)

@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"]="no-store"
    return resp

@app.get("/_ping")
def _ping(): return ok(pong=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
