import os, sqlite3, traceback
from pathlib import Path
from flask import Flask, request, send_from_directory
from flask_cors import CORS

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "admind.db"
STATIC_DIR = BASE / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app)

def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS accounts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, platform TEXT, external_id TEXT, monthly_spend REAL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS campaigns(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id INTEGER, name TEXT, status TEXT,
      spend REAL DEFAULT 0, cpa REAL DEFAULT 0, roas REAL DEFAULT 0,
      ctr REAL DEFAULT 0, impressions INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0, conversions INTEGER DEFAULT 0,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS recommendations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id INTEGER, title TEXT, details TEXT, impact_score REAL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    con.commit(); con.close()

init_db()

def dicts(cur): return [dict(r) for r in cur.fetchall()]

def build_recommendations(con, account_id=None):
    cur = con.cursor()
    q = "SELECT * FROM campaigns" + (" WHERE account_id=?" if account_id else "")
    cur.execute(q, (account_id,) if account_id else ())
    rows = [dict(r) for r in cur.fetchall()]
    cur.execute("DELETE FROM recommendations" + (" WHERE account_id=?" if account_id else ""),
                (account_id,) if account_id else ())
    made=[]
    for r in rows:
        roas = float(r.get("roas") or 0)
        ctr  = float(r.get("ctr") or 0)
        cpa  = float(r.get("cpa") or 0)
        score = (roas * 2.5) + (ctr * 0.5) - (cpa * 0.1)
        title = f"Adjust bid for {r['name']}"
        details = f"CPA={cpa}, ROAS={roas}, CTR={ctr} — +10% if ROAS>1.5, else -10%."
        cur.execute("INSERT INTO recommendations(account_id,title,details,impact_score) VALUES(?,?,?,?)",
                    (r["account_id"], title, details, round(score,2)))
        made.append({"account_id": r["account_id"], "title": title, "impact_score": round(score,2)})
    con.commit(); return made

@app.get("/health")
def health():
    return {"ok": True, "status": "healthy"}

@app.get("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")

@app.route("/api/accounts", methods=["GET","POST"])
def accounts():
    init_db()
    con=get_db(); cur=con.cursor()
    if request.method=="POST":
        d=request.get_json(force=True) or {}
        cur.execute("INSERT INTO accounts(name,platform,external_id,monthly_spend) VALUES(?,?,?,?)",
                    (d.get("name"), d.get("platform"), d.get("external_id"), d.get("monthly_spend",0)))
        con.commit(); con.close()
        return {"ok":True,"id":cur.lastrowid},201
    cur.execute("SELECT * FROM accounts ORDER BY id DESC")
    out = {"ok":True,"accounts":dicts(cur)}; con.close(); return out

@app.route("/api/campaigns", methods=["GET","POST"])
def campaigns():
    init_db()
    con=get_db(); cur=con.cursor()
    if request.method=="POST":
        d=request.get_json(force=True)
        cur.execute("""INSERT INTO campaigns(account_id,name,status,spend,cpa,roas,ctr,impressions,clicks,conversions)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (d["account_id"], d["name"], d.get("status","active"), d.get("spend",0), d.get("cpa",0),
                     d.get("roas",0), d.get("ctr",0), d.get("impressions",0), d.get("clicks",0), d.get("conversions",0)))
        con.commit(); con.close()
        return {"ok":True,"id":cur.lastrowid},201
    cur.execute("SELECT * FROM campaigns ORDER BY updated_at DESC")
    out = {"ok":True,"campaigns":dicts(cur)}; con.close(); return out

@app.route("/api/recommendations", methods=["GET","POST"])
def recommendations():
    init_db()
    con=get_db(); cur=con.cursor()
    if request.method=="POST":
        d=request.get_json(force=True) or {}
        made = build_recommendations(con, account_id=d.get("account_id"))
        con.close()
        return {"ok":True,"recommendations":made}
    cur.execute("SELECT * FROM recommendations ORDER BY impact_score DESC")
    out = {"ok":True,"recommendations":dicts(cur)}; con.close(); return out

@app.post("/api/seed")
def seed():
    init_db()
    try:
        con=get_db(); cur=con.cursor()
        cur.executescript("DELETE FROM accounts; DELETE FROM campaigns; DELETE FROM recommendations;")
        cur.execute("INSERT INTO accounts(name,platform,external_id,monthly_spend) VALUES(?,?,?,?)",
                    ("Demo Brand","meta","demo-123",5000))
        acc_id = cur.lastrowid
        rows = [
            (acc_id,"Prospecting - Broad","active",1250,48,0.72,0.65,85000,553,92),
            (acc_id,"Remarketing - 7d","active",980,22,2.35,1.45,42000,609,143),
            (acc_id,"Search - Brand","active",1670,12,3.10,2.20,36000,792,218),
            (acc_id,"Creators - UGC","active",820,35,1.10,0.75,51000,383,62),
        ]
        for r in rows:
            cur.execute("""INSERT INTO campaigns(account_id,name,status,spend,cpa,roas,ctr,impressions,clicks,conversions)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""", r)
        con.commit()
        build_recommendations(con, account_id=acc_id)
        con.close()
        return {"ok":True,"seeded_account_id":acc_id}
    except Exception as e:
        traceback.print_exc()
        return {"ok":False,"error":str(e)}, 500

if __name__ == "__main__":
    port=int(os.environ.get("PORT","5000"))
    app.run(host="0.0.0.0", port=port)
