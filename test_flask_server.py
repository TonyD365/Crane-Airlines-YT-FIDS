#!/usr/bin/env python3
"""Test the Flask server."""

import threading
import time
import requests
from app import _start_flask_server

# Start Flask server in background
print("Starting Flask server...")
server_thread = threading.Thread(target=_start_flask_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(2)

try:
    # Test GET request
    print("\nTesting GET request to http://localhost:7860/")
    response = requests.get('http://localhost:7860/', timeout=5)
    print(f"Status Code: {response.status_code}")
    print(f"Response preview: {response.text[:200]}")
    
    # Test HEAD request
    print("\nTesting HEAD request to http://localhost:7860/")
    head_response = requests.head('http://localhost:7860/', timeout=5)
    print(f"Status Code: {head_response.status_code}")
    
    print("\n✅ Flask server is working correctly!")
    
except requests.exceptions.ConnectionError:
    print("❌ Could not connect to Flask server")
except Exception as e:
    print(f"❌ Error: {e}")