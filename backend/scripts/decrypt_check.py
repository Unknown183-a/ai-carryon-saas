"""
Run locally: python3 decrypt_check.py
Paste your CHANNEL_SECRETS_ENCRYPTION_KEY and the encrypted
youtube_oauth_token value when prompted. Prints only which JSON keys
are present/missing -- never prints the actual secret values.
"""
import base64
import json

from cryptography.fernet import Fernet

encryption_key = input("CHANNEL_SECRETS_ENCRYPTION_KEY: ").strip()
encrypted_token = input("encrypted youtube_oauth_token value: ").strip()

fernet = Fernet(encryption_key.encode("utf-8"))
decrypted_b64 = fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
token_json = json.loads(base64.b64decode(decrypted_b64))

required = ["refresh_token", "token_uri", "client_id", "client_secret", "token"]
print("\nFields present in the stored token:")
for field in required:
    present = field in token_json and token_json[field] is not None
    print(f"  {'OK ' if present else 'MISSING'}  {field}")

print("\nAll keys found:", list(token_json.keys()))
