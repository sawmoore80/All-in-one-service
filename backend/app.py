import os, sqlite3, threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "static"))
CORS(app)

# Use /tmp on Render so DB is fresh per deploy and avoids permission issues
DB_PATH = os.environ.get("DB_PATH", "/tmp/admind.db")
STATIC_DIR = Path(app.static_folder)

write_lock = threading.Lock()

def dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    # Less locking pain
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA busy_timeout=8000;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def ensure_schema():
    con = get_db()
    cur = con.cursor()
    # Core tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            platform TEXT,
            external_id TEXT,
            monthly_spend REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
    """)
    # Recommendations must include 'title'. If missing, recreate table safely.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            impact_score REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
    """)
    # Verify 'title' exists; if not, rebuild the table.
    cur.execute("PRAGMA table_info(recommendations);")
    cols = {row["name"] for row in dicts(cur)}
    if "title" not in cols:
        cur.execute("DROP TABLE IF EXISTS recommendations;")
        cur.execute("""
            CREATE TABLE recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                impact_score REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
        """)
    con.commit()
    con.close()

def build_recommendations(con, account_id: int):
    cur = con.cursor()
    # Pull campaigns for account
    cur.execute("""
        SELECT name, spend, cpa, roas, ctr, impressions, clicks, conversions
        FROM campaigns
        WHERE account_id = ?
    """, (account_id,))
    rows = dicts(cur)

    recs = []
    if not rows:
        return recs

    # Very simple heuristics
    # 1) CPA optimization
    high_cpa = [r for r in rows if r["cpa"] and r["cpa"] >= 35]
    low_cpa  = [r for r in rows if r["cpa"] and r["cpa"] <= 15]
    if high_cpa and low_cpa:
        title = "Shift budget from high CPA to low CPA campaigns"
        desc  = f"Reallocate ~15–25% from {', '.join([r['name'] for r in high_cpa[:2]])} into {', '.join([r['name'] for r in low_cpa[:2]])} to reduce blended CPA."
        recs.append((account_id, title, desc, 0.9))

    # 2) CTR improvement
    low_ctr = sorted(rows, key=lambda r: r.get("ctr", 0))[:1]
    if low_ctr and (low_ctr[0].get("ctr") or 0) < 0.8:
        title = "Refresh creatives on lowest-CTR campaign"
        desc  = f"{low_ctr[0]['name']} has CTR {low_ctr[0]['ctr']}%. Test 3 new hooks, new intros, and top comment overlays."
        recs.append((account_id, title, desc, 0.7))

    # 3) Brand search protection
    brand = [r for r in rows if "brand" in r["name"].lower()]
    if brand:
        title = "Protect/Search: Brand term coverage"
        desc  = "Ensure exact+phrase match coverage on brand terms and monitor impression share > 80%."
        recs.append((account_id, title, desc, 0.6))

    # 4) Retargeting scale
    remarket = [r for r in rows if "remarket" in r["name"].lower()]
    if remarket:
        title = "Scale remarketing window tests"
        desc  = "Add 14d/30d windows and test 2 new creatives tailored to cart visitors."
        recs.append((account_id, title, desc, 0.5))

    # Persist (clear old then insert)
    cur.execute("DELETE FROM recommendations WHERE account_id = ?;", (account_id,))
    cur.executemany("""
        INSERT INTO recommendations (account_id, title, description, impact_score)
        VALUES (?, ?, ?, ?)
    """, recs)
    con.commit()

@app.before_first_request
def _boot():
    # Ensure schema exists and is compatible on cold start
    ensure_schema()

@app.route("/health")
def health():
    return jsonify(ok=True, status="healthy", db_path=DB_PATH)

@app.route("/")
def index():
    # Serve static app (optional)
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return send_from_directory(str(STATIC_DIR), "index.html")
    return jsonify(ok=True, message="AdMind API")

@app.route("/api/seed", methods=["POST"])
def seed():
    ensure_schema()  # make extra sure
    with write_lock:
        con = get_db()
        cur = con.cursor()
        # Create demo account
        cur.execute("""
            INSERT INTO accounts(name, platform, external_id, monthly_spend)
            VALUES(?, ?, ?, ?)
        """, ("Demo Brand", "meta", "demo-123", 5000))
        acc_id = cur.lastrowid

        # Seed sample campaigns
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

@app.route("/api/recommendations", methods=["GET"])
def recommendations():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM recommendations ORDER BY impact_score DESC, id DESC;")
    data = dicts(cur)
    con.close()
    return jsonify(ok=True, recommendations=data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
