from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = Flow.from_client_secrets_file(
    "client_secret.json",
    scopes=SCOPES,
    redirect_uri="http://localhost:8000/auth/youtube/callback",
)

auth_url, state = flow.authorization_url(
    access_type="offline",
    include_granted_scopes="true",
    prompt="consent",
)

print("\nOpen this URL in your browser:\n")
print(auth_url)

code = input("\nPaste the authorization code here: ").strip()

flow.fetch_token(code=code)

creds = flow.credentials

print("\n==============================")
print("ACCESS TOKEN")
print(creds.token)
print("\nREFRESH TOKEN")
print(creds.refresh_token)
print("==============================")
