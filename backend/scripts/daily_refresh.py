from backend.app import get_db, build_recommendations
con=get_db()
build_recommendations(con)
print("Refreshed")
