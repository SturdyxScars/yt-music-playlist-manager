import json

from flask import Flask, redirect, request, url_for, session, render_template, jsonify
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix



app = Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')


app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None"
)

app.config["SESSION_TYPE"] = "filesystem"  # or "redis" if you want persistent sessions
app.config["SESSION_PERMANENT"] = False
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
        "redirect_uris": [os.environ.get('REDIRECT_URI')]
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
@app.route("/login")
def login():
    flow = Flow.from_client_config(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=CLIENT_SECRETS_FILE['web']['redirect_uris'][0]
    )
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt = "consent")
    session["state"] = state
    print(state)
    return redirect(auth_url)


# --- GOOGLE REDIRECT HANDLER ---
@app.route("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=session["state"],
        redirect_uri=CLIENT_SECRETS_FILE['web']['redirect_uris'][0]
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = creds.to_json()
    print(session["state"])
    return redirect(url_for("index"))


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
    creds = Credentials.from_authorized_user_info(eval(creds_json))
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
