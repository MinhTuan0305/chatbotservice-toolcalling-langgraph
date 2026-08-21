"""
Generate a secure API key for socket server endpoints.

Usage:
    python generate_api_key.py

Copy the generated key to your .env file:
    API_KEY=<generated_key>
"""

import secrets

def generate_api_key():
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(32)

if __name__ == '__main__':
    api_key = generate_api_key()
    print("\n" + "=" * 60)
    print("GENERATED API KEY")
    print("=" * 60)
    print(f"\n{api_key}\n")
    print("=" * 60)
    print("\nAdd this to your .env file:")
    print(f"API_KEY={api_key}")
    print("\nKeep this key secret! Do not commit to git.")
    print("=" * 60 + "\n")
