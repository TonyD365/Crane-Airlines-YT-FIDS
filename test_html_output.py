#!/usr/bin/env python3
"""Test the HTML output to verify tabs are working."""

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

# Check if the HTML contains the tab elements
print("\nChecking HTML content...")

# Check for tab buttons
if 'onclick="showTab(\'add\')"' in html:
    print("✓ Add Flight tab button found")
else:
    print("✗ Add Flight tab button NOT found")

if 'onclick="showTab(\'update\')"' in html:
    print("✓ Update Flight tab button found")
else:
    print("✗ Update Flight tab button NOT found")

if 'onclick="showTab(\'delete\')"' in html:
    print("✓ Delete Flight tab button found")
else:
    print("✗ Delete Flight tab button NOT found")

# Check for tab content divs
if 'id="add" class="tab-content active"' in html:
    print("✓ Add Flight tab content found")
else:
    print("✗ Add Flight tab content NOT found")

if 'id="update" class="tab-content"' in html:
    print("✓ Update Flight tab content found")
else:
    print("✗ Update Flight tab content NOT found")

if 'id="delete" class="tab-content"' in html:
    print("✓ Delete Flight tab content found")
else:
    print("✗ Delete Flight tab content NOT found")

# Check for JavaScript function
if 'function showTab(tabName)' in html:
    print("✓ showTab JavaScript function found")
else:
    print("✗ showTab JavaScript function NOT found")

# Check for button type="button"
if 'type="button" class="tab' in html:
    print("✓ Tab buttons have type='button' attribute")
else:
    print("✗ Tab buttons missing type='button' attribute")

print("\n✅ HTML output test completed!")
print("\nIf tabs still don't work in browser:")
print("1. Restart the app: python3 app.py")
print("2. Hard refresh browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)")
print("3. Clear browser cache if needed")