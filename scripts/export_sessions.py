#!/usr/bin/env python3
"""
Export session cookies to base64 for use as environment variable.

This script reads session files from the sessions/ directory and outputs
them in a format suitable for the INSTAGRAM_SESSIONS environment variable.

Usage:
    python scripts/export_sessions.py
    
Output format:
    username1:base64data,username2:base64data
    
Then set this as your INSTAGRAM_SESSIONS environment variable on Render.
"""

import base64
import pickle
from pathlib import Path


def export_sessions():
    """Export all session files to base64 format."""
    sessions_dir = Path(__file__).parent.parent / "sessions"
    
    if not sessions_dir.exists():
        print("❌ No sessions directory found.")
        print("   Run the browser login first to create sessions.")
        return
    
    session_files = list(sessions_dir.glob("session-*"))
    
    if not session_files:
        print("❌ No session files found.")
        print("   Run the browser login first to create sessions.")
        return
    
    print(f"Found {len(session_files)} session file(s):\n")
    
    parts = []
    
    for session_file in session_files:
        username = session_file.name.replace("session-", "")
        
        try:
            with open(session_file, 'rb') as f:
                cookies = pickle.load(f)
            
            # Re-pickle and base64 encode
            b64_data = base64.b64encode(pickle.dumps(cookies)).decode('utf-8')
            
            # Check for sessionid
            has_sessionid = any(c.name == 'sessionid' for c in cookies)
            
            print(f"  ✅ {username}")
            print(f"     Cookies: {len(cookies)}")
            print(f"     Has sessionid: {'Yes ✓' if has_sessionid else 'No ✗'}")
            print(f"     Base64 length: {len(b64_data)} chars")
            print()
            
            parts.append(f"{username}:{b64_data}")
            
        except Exception as e:
            print(f"  ❌ {username}: Error - {e}")
            print()
    
    if parts:
        print("=" * 60)
        print("INSTAGRAM_SESSIONS value (copy this to Render):")
        print("=" * 60)
        print()
        full_value = ",".join(parts)
        print(full_value)
        print()
        print(f"Total length: {len(full_value)} characters")
        print()
        
        # Also save to a file for easy copying
        output_file = Path(__file__).parent.parent / "sessions_export.txt"
        with open(output_file, 'w') as f:
            f.write(full_value)
        print(f"💾 Also saved to: {output_file}")
        print("   (Add this file to .gitignore!)")


if __name__ == "__main__":
    export_sessions()
