import os
from flask import Flask, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, '..', 'static')

# Serve static files at /static (do NOT use '/')
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

@app.route("/")
def index():
    # Serve the homepage
    return send_from_directory(STATIC_DIR, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port)
