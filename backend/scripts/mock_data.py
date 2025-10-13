import random
from backend.app import get_db, build_recommendations, init_db

def seed():
    init_db()
    con=get_db(); cur=con.cursor()
    # Create a sample account
    cur.execute("INSERT INTO accounts(name,platform,external_id,monthly_spend) VALUES(?,?,?,?)",
                ("Client A","Meta","meta_abc",45000))
    acc_id=cur.lastrowid

    def mk(name):
        spend=random.uniform(100,2000); roas=random.uniform(0.3,3.5); cpa=random.uniform(10,120)
        ctr=random.uniform(0.3,3.0); imps=random.randint(5000,200000)
        clicks=int(imps*ctr/100); conv=int(clicks*0.02)
        return (acc_id,name,"active",spend,cpa,roas,ctr,imps,clicks,conv)

    for n in ["Prospecting - Broad","Remarketing - 7d","Creators - UGC","Search - Brand"]:
        cur.execute("""INSERT INTO campaigns(account_id,name,status,spend,cpa,roas,ctr,impressions,clicks,conversions)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", mk(n))
    con.commit()
    build_recommendations(con)
    print("Seeded.")

if __name__=="__main__":
    seed()
