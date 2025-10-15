import os, sqlite3, json, smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv
from flask import Flask, request, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_bcrypt import Bcrypt

# ---------- Flask app ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "static"))

app = Flask(__name__, static_url_path="/static", static_folder=STATIC_DIR)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "devkey")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "api_login"

# ---------- DB ----------
def db():
  con = sqlite3.connect(os.path.join(APP_DIR, "..", "admind.db"))
  con.row_factory = sqlite3.Row
  return con

with db() as con:
  con.executescript("""
  CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS contacts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, email TEXT, company TEXT, phone TEXT, message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS posts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    post_id TEXT,
    title TEXT,
    caption TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  """)

# ---------- Auth ----------
class User(UserMixin):
  def __init__(self, row):
    self.id = row["id"]
    self.email = row["email"]

@login_manager.user_loader
def load_user(user_id):
  with db() as con:
    r = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
  return User(r) if r else None

@app.post("/api/register")
def api_register():
  d = request.get_json(force=True)
  email = (d.get("email") or "").strip().lower()
  pw = d.get("password") or ""
  if not email or not pw:
    return {"ok": False, "error": "email & password required"}, 400
  ph = bcrypt.generate_password_hash(pw).decode("utf-8")
  try:
    with db() as con:
      con.execute("INSERT INTO users(email,password_hash) VALUES(?,?)", (email, ph))
      r = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
  except sqlite3.IntegrityError:
    return {"ok": False, "error": "user exists"}, 400
  login_user(User(r))
  return {"ok": True, "user": {"id": r["id"], "email": r["email"]}}

@app.post("/api/login")
def api_login():
  d = request.get_json(force=True)
  email = (d.get("email") or "").strip().lower()
  pw = d.get("password") or ""
  with db() as con:
    r = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
  if not r or not bcrypt.check_password_hash(r["password_hash"], pw):
    return {"ok": False, "error": "invalid credentials"}, 401
  login_user(User(r))
  return {"ok": True, "user": {"id": r["id"], "email": r["email"]}}

@app.get("/api/logout")
@login_required
def api_logout():
  logout_user()
  return {"ok": True}

@app.get("/api/me")
def api_me():
  if current_user.is_authenticated:
    return {"ok": True, "auth": True, "email": current_user.email}
  return {"ok": True, "auth": False}

# ---------- Health / Seed / Mock Data ----------
@app.get("/health")
def health():
  return {"ok": True, "status": "healthy"}

@app.post("/api/seed")
def seed_demo():
  return {"ok": True, "message": "Demo data seeded"}

@app.get("/api/kpis")
def get_kpis():
  return {"ok": True, "total_spend": 4720, "avg_roas": 1.82, "avg_cpa": 29, "conversions": 515}

@app.get("/api/trends")
def get_trends():
  labels = [f"W-{i}" for i in range(7)]
  spend = [600, 520, 640, 580, 620, 655, 690]
  roas = [1.6, 1.52, 1.68, 1.70, 1.75, 1.78, 1.82]
  top = {"labels": ["Search - Brand", "Remarketing - 7d", "Prospecting - Broad", "Creators - UGC"], "clicks": [1000, 750, 720, 350]}
  return {"ok": True, "labels": labels, "series": {"spend": spend, "roas": roas}, "top": top}

@app.get("/api/insights")
def get_insights():
  return {
    "ok": True,
    "insights": [
      {
        "id": 1,
        "title": "Lift ROAS on Prospecting - Broad",
        "campaign_name": "Prospecting - Broad",
        "kpi": "ROAS",
        "severity": "high",
        "priority_score": 1.86,
        "evidence": {"roas": "0.72", "spend": 1250, "target_roas": "1.00"},
        "actions": [
          "Add price anchor (MSRP vs Now) + guarantee top-of-frame",
          "Swap first frame to strongest review (stars + count)",
          "Send traffic to highest-CVR LP; strip header nav"
        ],
        "expected_impact": 0.75
      }
    ]
  }

@app.post("/api/playbook")
def api_playbook():
  d = request.get_json(silent=True) or {}
  insights = get_insights()["insights"]
  sel = d.get("insight_ids")
  chosen = [i for i in insights if not sel or i["id"] in set(sel)]
  days = ["Day 1","Day 2","Day 3","Day 4","Day 5","Day 6","Day 7"]
  plan=[]
  for idx, ins in enumerate(chosen[:7]):
    plan.append({
      "day": days[idx],
      "title": ins["title"],
      "kpi": ins["kpi"],
      "severity": ins["severity"],
      "what_to_ship": ins["actions"][:3],
      "how_to_measure": [
        f"Primary KPI: {ins['kpi']}",
        f"Expected impact: +{int(ins['expected_impact']*100)}%",
        "Review after 48h; keep if KPI improves vs baseline."
      ]
    })
  return {"ok": True, "plan": plan}

# ---------- Social (mock) ----------
@app.get("/api/oauth/<platform>")
def oauth_login_mock(platform):
  return {"ok": True, "auth_url": f"https://auth.{platform}.com/demo_oauth"}

@app.get("/api/social/connections")
def list_connections():
  return {
    "ok": True,
    "connections": [
      {"platform": "Instagram", "connected": False},
      {"platform": "TikTok", "connected": False},
      {"platform": "Facebook", "connected": False},
      {"platform": "YouTube", "connected": False}
    ]
  }

@app.post("/api/social/mock_pull")
@login_required
def mock_pull_posts():
  sample = [
    {"platform":"Instagram","post_id":"ig1","title":"Spring Drop","caption":"New arrivals","metrics":{"likes":320,"comments":18}},
    {"platform":"TikTok","post_id":"tt1","title":"Behind the scenes","caption":"BTS shoot","metrics":{"plays":12000,"hearts":850}},
  ]
  with db() as con:
    for p in sample:
      con.execute(
        "INSERT INTO posts(user_id,platform,post_id,title,caption,metrics_json) VALUES(?,?,?,?,?,?)",
        (current_user.id,p["platform"],p["post_id"],p["title"],p["caption"],json.dumps(p["metrics"]))
      )
  return {"ok": True, "added": len(sample)}

@app.get("/api/posts")
@login_required
def api_posts():
  with db() as con:
    rows = [dict(r) for r in con.execute("SELECT platform,post_id,title,caption,metrics_json FROM posts WHERE user_id=? ORDER BY id DESC",(current_user.id,)).fetchall()]
  for r in rows:
    try: r["metrics"] = json.loads(r.pop("metrics_json") or "{}")
    except: r["metrics"] = {}
  return {"ok": True, "posts": rows}

# ---------- AI (mock) ----------
@app.post("/api/ai/ask")
def ai_ask():
  q = (request.get_json(force=True) or {}).get("q","")
  return {"ok": True, "answer": f"🤖 Based on '{q}', test stronger hook + social proof in first 3 seconds."}

# ---------- Contact (store + email) ----------
def _send_email(subject, body_text):
  host=os.getenv("SMTP_HOST"); port=int(os.getenv("SMTP_PORT","587"))
  user=os.getenv("SMTP_USER"); pwd=os.getenv("SMTP_PASS")
  to=os.getenv("OWNER_EMAIL","sawmoore80@gmail.com")
  if not (host and port and user and pwd): return False
  msg = MIMEText(body_text, "plain")
  msg["Subject"]=subject; msg["From"]=formataddr(("AdMind",user)); msg["To"]=to
  s = smtplib.SMTP(host, port, timeout=10); s.starttls(); s.login(user, pwd); s.sendmail(user, [to], msg.as_string()); s.quit()
  return True

@app.post("/api/contact")
def api_contact():
  d = request.get_json(force=True)
  name=d.get("name",""); email=d.get("email",""); company=d.get("company",""); phone=d.get("phone",""); message=d.get("message","")
  with db() as con:
    con.execute("INSERT INTO contacts(name,email,company,phone,message) VALUES(?,?,?,?,?)",(name,email,company,phone,message))
  emailed=False
  try:
    emailed=_send_email("New AdMind Contact", f"Name: {name}\nEmail: {email}\nCompany: {company}\nPhone: {phone}\n\n{message}")
  except Exception:
    emailed=False
  return {"ok": True, "emailed": emailed}

# ---------- Root & static ----------
@app.get("/")
def root_index():
  return app.send_static_file("index.html")

# ---------- Error helper (deploy diagnostics) ----------
@app.errorhandler(Exception)
def _err(e):
  import traceback
  return {"ok": False, "error": str(e), "trace": traceback.format_exc().splitlines()[-10:]}, 500

@app.get("/_ping")
def _ping():
    return {"ok": True, "pong": True}

@app.get("/_healthz")
def _healthz():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.get("/")
def index_root():
    try:
        return app.send_static_file("index.html")
    except Exception:
        return "<h1>AdMind</h1><p>Static not found. Ensure static/index.html exists.</p>", 200
