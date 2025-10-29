import json
import redis
from flask import Flask, redirect, request, url_for, session, render_template, jsonify
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
import secrets
from datetime import datetime, timedelta

redis_client = redis.Redis.from_url(os.environ.get('REDIS_URL'), decode_responses=True)
def store_state(state):
    """Store state with 10-minute expiry"""
    redis_client.setex(f"oauth_state:{state}", 600, "valid")  # 10 minutes

def validate_state(state):
    """Check if state exists and is valid"""
    return redis_client.exists(f"oauth_state:{state}") == 1

def delete_state(state):
    """Delete state after use"""
    redis_client.delete(f"oauth_state:{state}")



# os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
SECRET_KEY = os.environ.get('SECRET_KEY')
app.secret_key = SECRET_KEY


app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_REDIS=redis_client,
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_SECURE=True,  # Should be True in production
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',  # Change from 'None' to 'Lax' initially
    PERMANENT_SESSION_LIFETIME=1800  # 30 minutes
)

Session(app)


# your client_secret.json from Google Cloud
CLIENT_SECRETS_FILE = {
    "web":{
        "client_id" : os.environ.get('CLIENT_ID'),
        "project_id" : os.environ.get('PROJECT_ID'),
        "auth_uri" : "https://accounts.google.com/o/oauth2/auth",
        "token_uri":"https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_secret" : os.environ.get('CLIENT_SECRET'),
        "redirect_uris": ["https://ytm-playlists.onrender.com/oauth2callback"]
    }

}

# OAuth scope — this one gives access to YouTube Data API
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
print(CLIENT_SECRETS_FILE['web']['redirect_uris'][0])

def insert(song_list, youtube_build, playlist_id):
    for song in song_list:
        search = youtube_build.search().list(
            part="snippet",
            maxResults=1,
            q=song,
            type="video",
        ).execute()
        if search["items"]:
            video_id = search["items"][0]["id"]["videoId"]
            print(search["items"][0]["snippet"]["title"])
            youtube_build.playlistItems().insert(
                part="snippet",
                body={"snippet": {"playlistId": playlist_id,
                                  "resourceId": {
                                                "kind": "youtube#video",
                                                "videoId": video_id
                                                }
                                  }
                      }

                ).execute()
            print("________")
            print("added to youtube")


# --- HOME PAGE ---
@app.route("/")
def index():
    return render_template("index.html")

# --- LOGIN ---
# Simple in-memory store (use Redis or database in production)
oauth_states = {}


@app.route("/login")
def login():
    try:
        flow = Flow.from_client_config(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=CLIENT_SECRETS_FILE['web']['redirect_uris'][0]
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )

        # Store state with timestamp
        store_state(state)
        session["oauth_state"] = state
        session.modified = True

        print(f"Generated state: {state}")
        print(f"Authorization URL: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        print(e)
        return redirect("/")


@app.route("/oauth2callback")
def oauth2callback():
    state = session.get("oauth_state")
    print(f"after callback retrieved state : {state}")
    if not state:
        print("session timeout, sign in again")
        return "Session expired. Please try again.", 400

    # Validate state using Redis
    if not validate_state(state):
        print("state didn't validate")
        return "Invalid or expired state. Please try again.", 400

    flow = Flow.from_client_config(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=CLIENT_SECRETS_FILE['web']['redirect_uris'][0]
    )

    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        session["credentials"] = creds.to_json()
        session.modified = True

        # Clean up the used state from Redis
        delete_state(state)
        session.pop("oauth_state", None)

        print("OAuth successful")
        return redirect(url_for("index"))

    except Exception as e:
        print(f"OAuth callback error: {e}")
        return f"Authentication failed: {e}", 400


#--- playlists dynamics----
@app.route("/get_playlists")
def get_playlists():
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        creds_json = session["credentials"]
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.load(creds_json))
        creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)
        playlists = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        ).execute()

        playlist_data = []
        for item in playlists["items"]:
            playlist_data.append({
                "id": item["id"],
                "title": item["snippet"]["title"]
            })

        print("Fetched playlists:", [p["title"] for p in playlist_data])
        return jsonify(playlists=playlist_data)

    except Exception as e:
        print(f"Error fetching playlists: {str(e)}")
        return jsonify({"error": str(e)}), 500


# --- FILE UPLOAD HANDLER ---
@app.route("/upload", methods=["POST"])
def upload():
    if "credentials" not in session:
        return redirect(url_for("login"))

    creds_json = session["credentials"]
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_info(json.load(creds_json))
    creds.refresh(Request())

    # Example YouTube API client
    youtube = build("youtube", "v3", credentials=creds)


    uploaded_file = request.files.get("file")
    song_list_text = request.form.get("songList")
    playlist_id = request.form.get("playlist_id")


    if uploaded_file and uploaded_file.filename:
        content = uploaded_file.read().decode("utf-8").splitlines()
        insert(content, youtube_build = youtube, playlist_id= playlist_id) # function to add songs

    if song_list_text:
        list = song_list_text.splitlines()
        insert(list, youtube_build = youtube, playlist_id = playlist_id) # function to add song
    return None

if __name__ == "__main__":
    app.run("0.0.0.0", 5000, debug=False)
