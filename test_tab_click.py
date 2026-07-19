#!/usr/bin/env python3
"""Test tab clicking with a headless browser simulation."""

import threading
import time
import requests
from app import _start_flask_server

# Start Flask server in background
print("Starting Flask server...")
server_thread = threading.Thread(target=_start_flask_server, daemon=True)
server_thread.start()
time.sleep(2)

# Get the HTML page
print("\nGetting HTML page...")
response = requests.get('http://localhost:7860/')
html = response.text

# Save HTML to file for inspection
with open('/tmp/test_fids.html', 'w') as f:
    f.write(html)

print("✓ HTML saved to /tmp/test_fids.html")
print("\nTo test tabs in browser:")
print("1. Open: http://localhost:7860/")
print("2. Open browser console (F12)")
print("3. Click on 'Update Flight' tab")
print("4. Check console for any JavaScript errors")
print("\nOr manually test by running:")
print("  open http://localhost:7860/")
print("\nIf tabs don't work, try:")
print("1. Hard refresh: Cmd+Shift+R")
print("2. Clear cache and reload")
print("3. Check browser console for errors")