import os
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5050")
OAUTH = {
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "client_id": os.environ.get("FB_CLIENT_ID",""),
        "client_secret": os.environ.get("FB_CLIENT_SECRET",""),
        "scope": "public_profile,email,instagram_basic,instagram_manage_insights,pages_show_list",
        "redirect_uri": f"{BASE_URL}/oauth/callback/facebook",
        "api_base": "https://graph.facebook.com/v19.0"
    },
    "instagram": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "client_id": os.environ.get("IG_CLIENT_ID",""),
        "client_secret": os.environ.get("IG_CLIENT_SECRET",""),
        "scope": "instagram_basic,instagram_manage_insights",
        "redirect_uri": f"{BASE_URL}/oauth/callback/instagram",
        "api_base": "https://graph.facebook.com/v19.0"
    },
    "youtube": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": os.environ.get("YT_CLIENT_ID",""),
        "client_secret": os.environ.get("YT_CLIENT_SECRET",""),
        "scope": "https://www.googleapis.com/auth/youtube.readonly",
        "redirect_uri": f"{BASE_URL}/oauth/callback/youtube",
        "api_base": "https://www.googleapis.com/youtube/v3"
    },
    "tiktok": {
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "client_id": os.environ.get("TT_CLIENT_ID",""),
        "client_secret": os.environ.get("TT_CLIENT_SECRET",""),
        "scope": "user.info.basic,video.list",
        "redirect_uri": f"{BASE_URL}/oauth/callback/tiktok",
        "api_base": "https://open.tiktokapis.com/v2"
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_id": os.environ.get("LI_CLIENT_ID",""),
        "client_secret": os.environ.get("LI_CLIENT_SECRET",""),
        "scope": "r_liteprofile r_emailaddress w_member_social",
        "redirect_uri": f"{BASE_URL}/oauth/callback/linkedin",
        "api_base": "https://api.linkedin.com/v2"
    }
}
