#!/usr/bin/env python3
"""Interactive script to login to Instagram with 2FA and save session."""

import os
import sys

# Load .env
from dotenv import load_dotenv
load_dotenv()

from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

def main():
    username = os.environ.get('INSTAGRAM_USERNAME')
    password = os.environ.get('INSTAGRAM_PASSWORD')
    
    if not username or not password:
        print("❌ INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in .env")
        sys.exit(1)
    
    print(f"🔐 Logging in as: {username}")
    
    cl = Client()
    
    try:
        cl.login(username, password)
        print("✅ Login successful (no 2FA required)")
    except TwoFactorRequired:
        print("📱 Two-factor authentication required!")
        print("Check your phone for the verification code.")
        
        code = input("Enter 2FA code: ").strip()
        
        try:
            cl.login(username, password, verification_code=code)
            print("✅ Login successful with 2FA!")
        except Exception as e:
            print(f"❌ 2FA login failed: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)
    
    # Save session
    cl.dump_settings("session.json")
    print("💾 Session saved to session.json")
    print("🚀 You can now restart the app with: docker compose up -d")

if __name__ == "__main__":
    main()
