import os, sqlite3, time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = "/tmp/admind.db"

app = Flask(__name__, static_folder=str(ROOT / "static"))
CORS(app)

def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def ensure_schema():
    con = get_db(); cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          platform TEXT,
          external_id TEXT,
          monthly_spend REAL DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          account_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          spend REAL DEFAULT 0,
          cpa REAL DEFAULT 0,
          roas REAL DEFAULT 0,
          ctr REAL DEFAULT 0,
          impressions INTEGER DEFAULT 0,
          clicks INTEGER DEFAULT 0,
          conversions INTEGER DEFAULT 0,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          account_id INTEGER,
          title TEXT NOT NULL,
          description TEXT,
          impact_score REAL DEFAULT 0,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    con.commit(); con.close()

def dicts(cur):
    return [dict(r) for r in cur.fetchall()]

def build_recommendations(con, account_id=None):
    cur = con.cursor()
    if account_id:
        cur.execute("DELETE FROM recommendations WHERE account_id=?", (account_id,))
    else:
        cur.execute("DELETE FROM recommendations")

    # Simple rules
    if account_id:
        cur.execute("SELECT * FROM campaigns WHERE account_id=?", (account_id,))
    else:
        cur.execute("SELECT * FROM campaigns")
    rows = cur.fetchall()

    for r in rows:
        acc_id = r["account_id"]
        name = r["name"]
        recs = []

        # Rule: Low CTR
        if r["ctr"] < 1.0:
            recs.append((
                acc_id,
                f"Improve CTR on {name}",
                "CTR is under 1%. Test 3–5 hooks, try square 1:1/9:16, swap first 2s.",
                0.7
            ))
        # Rule: High CPA
        if r["cpa"] > 40:
            recs.append((
                acc_id,
                f"Reduce CPA on {name}",
                "CPA above target. Try narrowing audience or add UGC with clear CTA.",
                0.8
            ))
        # Rule: Low ROAS
        if r["roas"] < 1.0:
            recs.append((
                acc_id,
                f"Boost ROAS on {name}",
                "ROAS < 1. Test price anchoring, objection-handling, stronger offer.",
                0.9
            ))

        if recs:
            cur.executemany("""
              INSERT INTO recommendations(account_id,title,description,impact_score)
              VALUES (?,?,?,?)
            """, recs)

    con.commit()

# ---------- Routes ----------
@app.route("/health")
def health():
    return jsonify(ok=True, status="healthy")

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/accounts")
def accounts():
    con=get_db(); cur=con.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY id DESC")
    data = dicts(cur); con.close()
    return jsonify(ok=True, accounts=data)

@app.route("/api/campaigns")
def campaigns():
    con=get_db(); cur=con.cursor()
    cur.execute("SELECT * FROM campaigns ORDER BY updated_at DESC")
    data = dicts(cur); con.close()
    return jsonify(ok=True, campaigns=data)

@app.route("/api/recommendations")
def recommendations():
    con=get_db(); cur=con.cursor()
    cur.execute("SELECT * FROM recommendations ORDER BY impact_score DESC, id DESC")
    data = dicts(cur); con.close()
    return jsonify(ok=True, recommendations=data)

@app.route("/api/seed", methods=["POST"])
def seed():
    """Seeds one demo account + 4 campaigns, rebuilds recs."""
    con=get_db(); cur=con.cursor()
    # wipe demo
    cur.execute("DELETE FROM recommendations")
    cur.execute("DELETE FROM campaigns")
    cur.execute("DELETE FROM accounts")
    con.commit()

    # insert account
    cur.execute("""INSERT INTO accounts(name,platform,external_id,monthly_spend)
                   VALUES(?,?,?,?)""", ("Demo Brand","meta","demo-123",5000))
    acc_id = cur.lastrowid

    rows = [
        (acc_id,"Prospecting - Broad","active",1250,48,0.72,0.65,85000,553,92),
        (acc_id,"Remarketing - 7d","active",980,22,2.35,1.45,42000,609,143),
        (acc_id,"Search - Brand","active",1670,12,3.10,2.20,36000,792,218),
        (acc_id,"Creators - UGC","active",820,35,1.10,0.75,51000,383,62),
    ]
    cur.executemany("""
      INSERT INTO campaigns(account_id,name,status,spend,cpa,roas,ctr,impressions,clicks,conversions)
      VALUES(?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()

    build_recommendations(con, account_id=acc_id)
    con.close()
    return jsonify(ok=True, seeded_account_id=acc_id)

# Initialize schema on import
ensure_schema()

if __name__ == "__main__":
    port = int(os.environ.get("PORT","5000"))
    app.run(host="0.0.0.0", port=port)

@app.get("/api/kpis")
def kpis():
    con = get_db(); cur = con.cursor()
    cur.execute("""
      SELECT IFNULL(SUM(spend),0) AS total_spend,
             IFNULL(AVG(roas),0)  AS avg_roas,
             IFNULL(AVG(cpa),0)   AS avg_cpa,
             IFNULL(SUM(conversions),0) AS conversions
      FROM campaigns
    """)
    row = cur.fetchone()
    out = {k: row[k] for k in row.keys()} if row else {}
    con.close()
    return out

@app.get("/api/trends")
def trends():
    """Generate simple 8-period trends from current campaign totals (synthetic)."""
    con = get_db(); cur = con.cursor()
    cur.execute("SELECT IFNULL(SUM(spend),0) AS spend, IFNULL(AVG(roas),0) AS roas FROM campaigns")
    row = cur.fetchone() or {"spend":0,"roas":0}
    total_spend = float(row["spend"] or 0)
    avg_roas = float(row["roas"] or 0)
    labels = [f"W-{i}" for i in range(7,-1,-1)]
    # Distribute totals across 8 periods
    import random
    random.seed(42)
    base = total_spend/8.0 if total_spend>0 else 100
    spend = [round(base*(0.85+random.random()*0.3),2) for _ in labels]
    roas  = [round(max(0.1, avg_roas*(0.85+random.random()*0.3)),2) for _ in labels]
    top_labels, clicks = [], []
    cur.execute("""SELECT name, clicks FROM campaigns ORDER BY clicks DESC LIMIT 5""")
    for r in cur.fetchall() or []:
      top_labels.append(r["name"]); clicks.append(int(r["clicks"] or 0))
    con.close()
    return {
      "labels": labels,
      "series": {"spend": spend, "roas": roas},
      "top": {"labels": top_labels, "clicks": clicks}
    }

# ================== INSIGHTS ENGINE + PLAYBOOK ==================
def analyze_campaigns(con):
    """
    Returns specific, scored insights per campaign, with evidence & actions.
    """
    cur = con.cursor()
    cur.execute("SELECT * FROM campaigns")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return []

    import statistics
    avg_cpa  = statistics.fmean([r["cpa"]  for r in rows if r.get("cpa")  is not None]) if rows else 0
    avg_roas = statistics.fmean([r["roas"] for r in rows if r.get("roas") is not None]) if rows else 0
    avg_ctr  = statistics.fmean([r["ctr"]  for r in rows if r.get("ctr")  is not None]) if rows else 0

    insights = []
    iid = 1

    def add(c, title, severity, kpi, expected_impact, evidence, actions, weight=1.0):
        nonlocal iid
        spend = float(c.get("spend") or 0)
        score = round(expected_impact * (1.0 + min(spend/1000.0, 5.0)) * weight, 2)
        insights.append({
            "id": iid,
            "campaign_id": c["id"],
            "campaign_name": c["name"],
            "severity": severity,
            "kpi": kpi,
            "title": title,
            "expected_impact": expected_impact,
            "priority_score": score,
            "evidence": evidence,
            "actions": actions
        })
        iid += 1

    for c in rows:
        ctr  = float(c.get("ctr") or 0)
        cpa  = float(c.get("cpa") or 0)
        roas = float(c.get("roas") or 0)
        spend= float(c.get("spend") or 0)
        name = (c.get("name") or "").lower()

        # CTR improvement
        import math
        ctr_target = max(1.0, avg_ctr*0.9) if avg_ctr else 1.0
        if ctr < ctr_target:
            add(
                c,
                title=f"Raise CTR on {c['name']}",
                severity="high" if ctr < 0.8 else "med",
                kpi="CTR",
                expected_impact=0.70 if ctr < 0.8 else 0.45,
                evidence={"ctr": f"{ctr:.2f}%", "benchmark_ctr": f"{ctr_target:.2f}%", "spend": spend},
                actions=[
                    "Ship 5 new hooks (first 2s = problem ➜ promise, product in frame).",
                    "Test 1:1, 4:5, 9:16 crops. Lead with benefit copy+price anchor.",
                    "Pause any ad <0.60% CTR for 48h."
                ],
                weight=1.0
            )

        # CPA high vs average
        if avg_cpa and cpa > avg_cpa * 1.25 and cpa > 25:
            delta = f"+{((cpa/avg_cpa)-1)*100:.0f}%"
            add(
                c,
                title=f"Cut CPA on {c['name']}",
                severity="high",
                kpi="CPA",
                expected_impact=0.65,
                evidence={"cpa": f"${cpa:.0f}", "avg_cpa": f"${avg_cpa:.0f}", "delta": delta, "spend": spend},
                actions=[
                    "Narrow audience (stack top 3 interests), exclude recent visitors.",
                    "Add strong CTA + objection handling in first 3 sec.",
                    "Try highest-volume bidding with 10–15% lower cap."
                ],
                weight=1.2
            )

        # ROAS target by intent
        target_roas = 1.0
        if "brand" in name or "search" in name:
            target_roas = 2.5
        elif "remarketing" in name:
            target_roas = 2.0

        if roas < target_roas:
            add(
                c,
                title=f"Lift ROAS on {c['name']}",
                severity="high" if roas < target_roas*0.8 else "med",
                kpi="ROAS",
                expected_impact=0.75 if roas < target_roas*0.8 else 0.5,
                evidence={"roas": f"{roas:.2f}", "target_roas": f"{target_roas:.2f}", "spend": spend},
                actions=[
                    "Add price anchor (MSRP vs Now) + guarantee top-of-frame.",
                    "Swap first frame to strongest review (stars + count).",
                    "Send traffic to highest-CVR LP; strip header nav."
                ],
                weight=1.1
            )

        # Scale winners
        if avg_roas and avg_cpa and roas >= max(2.5, avg_roas*1.2) and cpa <= max(25, avg_cpa*0.9):
            add(
                c,
                title=f"Scale budget +20–30% on {c['name']}",
                severity="med",
                kpi="Spend",
                expected_impact=0.60,
                evidence={"roas": f"{roas:.2f}", "cpa": f"${cpa:.0f}", "avg_roas": f"{avg_roas:.2f}", "avg_cpa": f"${avg_cpa:.0f}"},
                actions=[
                    "Increase daily budget 20–30% (avoid >40%).",
                    "Clone winning ad set; 70/30 creative split.",
                    "Guardrail: pause if ROAS < 1.8 for 48h."
                ],
                weight=0.9
            )

    insights.sort(key=lambda x: x["priority_score"], reverse=True)
    return insights

@app.get("/api/insights")
def api_insights():
    con = get_db()
    data = analyze_campaigns(con)
    con.close()
    return {"ok": True, "insights": data}

@app.post("/api/playbook")
def api_playbook():
    payload = request.get_json(silent=True) or {}
    sel = payload.get("insight_ids")
    con = get_db()
    all_insights = analyze_campaigns(con)
    con.close()

    if sel:
        chosen = [i for i in all_insights if i["id"] in set(sel)]
    else:
        chosen = all_insights[:5]

    days = ["Day 1","Day 2","Day 3","Day 4","Day 5","Day 6","Day 7"]
    plan = []
    for idx, ins in enumerate(chosen):
        d = days[idx % len(days)]
        plan.append({
            "day": d,
            "title": ins["title"],
            "kpi": ins["kpi"],
            "severity": ins["severity"],
            "what_to_ship": ins["actions"][:3],
            "how_to_measure": [
                f"Primary KPI: {ins['kpi']}",
                f"Expected impact: +{int(ins['expected_impact']*100)}%",
                "Review after 48h; keep if KPI improves vs baseline."
            ],
            "evidence": ins["evidence"]
        })
    return {"ok": True, "plan": plan}
# ================== /INSIGHTS ENGINE ==================

# ===================== AdMind: Auth + Social + AI =====================
from flask import request, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from oauthlib.oauth2 import WebApplicationClient
from datetime import datetime
import sqlite3, os, json
from dotenv import load_dotenv

load_dotenv()
try:
    app.secret_key = os.getenv("SECRET_KEY") or app.secret_key
except Exception:
    pass

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "api_login"

# --- DB helpers (reuse existing get_db if defined) ---
def _get_db():
    try:
        return get_db()  # reuse if already present in your app
    except NameError:
        con = sqlite3.connect("admind.db")
        con.row_factory = sqlite3.Row
        return con

def init_admind_tables():
    con = _get_db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS social_connections(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      platform TEXT NOT NULL,
      access_token TEXT,
      meta_json TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, platform)
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
    con.commit()
    try: con.close()
    except: pass

init_admind_tables()

# --- User model (lightweight) ---
class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]

@login_manager.user_loader
def load_user(user_id):
    con = _get_db(); cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    r = cur.fetchone()
    try: con.close()
    except: pass
    return User(r) if r else None

# --- Auth endpoints ---
@app.post("/api/register")
def api_register():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return {"ok": False, "error": "email & password required"}, 400
    pw = bcrypt.generate_password_hash(password).decode("utf-8")
    con = _get_db(); cur = con.cursor()
    try:
        cur.execute("INSERT INTO users(email,password_hash) VALUES(?,?)", (email, pw))
        con.commit()
    except sqlite3.IntegrityError:
        try: con.close()
        except: pass
        return {"ok": False, "error": "user exists"}, 400
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    u = User(cur.fetchone())
    login_user(u)
    try: con.close()
    except: pass
    return {"ok": True, "user": {"id": u.id, "email": u.email}}

@app.post("/api/login")
def api_login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    con = _get_db(); cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    r = cur.fetchone()
    if not r:
        try: con.close()
        except: pass
        return {"ok": False, "error": "invalid credentials"}, 401
    ok = bcrypt.check_password_hash(r["password_hash"], password)
    if not ok:
        try: con.close()
        except: pass
        return {"ok": False, "error": "invalid credentials"}, 401
    u = User(r); login_user(u)
    try: con.close()
    except: pass
    return {"ok": True, "user": {"id": u.id, "email": u.email}}

@app.get("/api/logout")
@login_required
def api_logout():
    logout_user()
    return {"ok": True}

# --- Social OAuth placeholders (swap with real provider flows) ---
CLIENT_IDS = {
    "instagram": os.getenv("IG_CLIENT_ID"),
    "facebook":  os.getenv("FB_CLIENT_ID"),
    "youtube":   os.getenv("YT_CLIENT_ID"),
    "tiktok":    os.getenv("TT_CLIENT_ID"),
}
CLIENT_SECRETS = {
    "instagram": os.getenv("IG_CLIENT_SECRET"),
    "facebook":  os.getenv("FB_CLIENT_SECRET"),
    "youtube":   os.getenv("YT_CLIENT_SECRET"),
    "tiktok":    os.getenv("TT_CLIENT_SECRET"),
}
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/oauth/callback")

@app.get("/api/oauth/<platform>")
@login_required
def oauth_begin(platform):
    cid = CLIENT_IDS.get(platform)
    if not cid:
        return {"ok": False, "error": "unsupported platform"}, 400
    auth_url = f"https://auth.{platform}.com/oauth?client_id={cid}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read"
    return {"ok": True, "auth_url": auth_url}

@app.get("/oauth/callback")
def oauth_callback():
    # NOTE: Replace this stub with the real token exchange per platform.
    # For demo: store a fake token so the UI "connected" state works.
    platform = request.args.get("platform", "instagram")
    token = request.args.get("code", "demo_token")
    if not current_user.is_authenticated:
        return "Login first", 401
    con = _get_db(); cur = con.cursor()
    cur.execute("""
      INSERT INTO social_connections(user_id, platform, access_token, meta_json)
      VALUES(?,?,?,?)
      ON CONFLICT(user_id,platform) DO UPDATE SET access_token=excluded.access_token, meta_json=excluded.meta_json
    """, (current_user.id, platform, token, json.dumps({"demo": True})))
    con.commit()
    try: con.close()
    except: pass
    return "Connected!"

# --- Social data stubs (replace with real API pulls) ---
@app.get("/api/social/connections")
@login_required
def social_connections():
    con = _get_db(); cur = con.cursor()
    cur.execute("SELECT platform, access_token IS NOT NULL AS connected FROM social_connections WHERE user_id=?", (current_user.id,))
    rows = [dict(r) for r in cur.fetchall()]
    try: con.close()
    except: pass
    return {"ok": True, "connections": rows}

@app.post("/api/social/mock_pull")
@login_required
def mock_pull():
    # Seed a few demo posts for the user
    demo = [
      ("instagram","IG-001","Launch Post","#NewDrop", {"likes":890,"comments":34,"saves":55,"ctr":1.1}),
      ("tiktok","TT-002","Behind the Scenes","BTS clip", {"views":52000,"likes":3100,"comments":120,"ctr":2.2}),
      ("youtube","YT-003","How-to","Tutorial desc", {"views":18000,"watch_pct":47,"subs":120}),
      ("facebook","FB-004","Offer Post","BOGO today", {"reactions":430,"shares":60,"ctr":0.9})
    ]
    con = _get_db(); cur = con.cursor()
    for p in demo:
        cur.execute("INSERT INTO posts(user_id,platform,post_id,title,caption,metrics_json) VALUES(?,?,?,?,?,?)",
            (current_user.id, p[0], p[1], p[2], p[3], json.dumps(p[4])))
    con.commit()
    try: con.close()
    except: pass
    return {"ok": True, "seeded": len(demo)}

@app.get("/api/posts")
@login_required
def list_posts():
    con = _get_db(); cur = con.cursor()
    cur.execute("SELECT id, platform, post_id, title, caption, metrics_json, created_at FROM posts WHERE user_id=? ORDER BY id DESC", (current_user.id,))
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        try: r["metrics"] = json.loads(r.pop("metrics_json") or "{}")
        except: r["metrics"] = {}
    try: con.close()
    except: pass
    return {"ok": True, "posts": rows}

# --- Simple AI advisory stub (rule-based; swap with your LLM later) ---
@app.post("/api/ai/ask")
@login_required
def ai_ask():
    q = (request.get_json(force=True) or {}).get("q","").lower()
    con = _get_db(); cur = con.cursor()
    cur.execute("SELECT platform, title, caption, metrics_json FROM posts WHERE user_id=? ORDER BY id DESC LIMIT 50", (current_user.id,))
    posts = [{"platform":r["platform"], "title":r["title"], "caption":r["caption"], "metrics": json.loads(r["metrics_json"] or "{}")} for r in cur.fetchall()]
    try: con.close()
    except: pass
    tip = []
    for p in posts:
        m = p["metrics"]
        if p["platform"]=="tiktok" and (m.get("ctr",0) or 0) < 1.5:
            tip.append("TikTok: tighten first 2s hook; add on-screen promise and 9:16 crop.")
        if p["platform"]=="instagram" and m.get("saves",0) < 40:
            tip.append("Instagram: use a carousel with step-by-step; add caption CTA 'save for later'.")
        if p["platform"]=="facebook" and (m.get("ctr",0) or 0) < 1.0:
            tip.append("Facebook: front-load offer and price anchor; try square 1:1 with bold headline.")
        if p["platform"]=="youtube" and (m.get("watch_pct",0) or 0) < 50:
            tip.append("YouTube: stronger thumbnail contrast + benefit-first intro; cut 10s dead air.")
    if not tip:
        tip = ["Looks solid. Next: A/B thumbnail + first-frame hook test across platforms."]
    return {"ok": True, "answer": " ".join(tip[:4]), "looked_at_posts": len(posts)}
# ===================== /AdMind: Auth + Social + AI =====================

# ---- auth status probe ----
@app.get("/api/me")
def api_me():
    try:
        from flask_login import current_user
    except Exception:
        return {"ok": True, "auth": False}
    if current_user.is_authenticated:
        return {"ok": True, "auth": True, "email": getattr(current_user, "email", None)}
    return {"ok": True, "auth": False}
