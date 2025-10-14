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
