#!/usr/bin/env python3
"""Test the flight management API endpoints."""

import threading
import time
import requests
from datetime import datetime, timezone
from app import _start_flask_server, provider
from crane_fids import Flight, FlightStatus

# Start Flask server in background
print("Starting Flask server...")
server_thread = threading.Thread(target=_start_flask_server, daemon=True)
server_thread.start()
time.sleep(2)

# Add a test flight first
print("\n1. Adding a test flight...")
test_flight = {
    "flight_number": "TEST101",
    "destination": "TEST DESTINATION",
    "scheduled": "14:30",
    "gate": "T01",
    "status": "ON_TIME",
    "departure": "TEST CITY"
}

response = requests.post('http://localhost:7860/api/flights', 
                        json=test_flight,
                        headers={'Content-Type': 'application/json'})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Get all flights
print("\n2. Getting all flights...")
response = requests.get('http://localhost:7860/api/flights')
print(f"Status: {response.status_code}")
flights = response.json()
print(f"Number of flights: {len(flights)}")
if flights:
    print(f"First flight: {flights[0]['flight_number']} - {flights[0]['destination']}")

# Update the flight
print("\n3. Updating flight TEST101...")
response = requests.put('http://localhost:7860/api/flights/TEST101',
                       json={"status": "DELAYED", "gate": "T02"},
                       headers={'Content-Type': 'application/json'})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Verify update
print("\n4. Verifying update...")
response = requests.get('http://localhost:7860/api/flights')
flights = response.json()
test_flight_data = [f for f in flights if f['flight_number'] == 'TEST101']
if test_flight_data:
    print(f"Updated flight: {test_flight_data[0]['flight_number']} - Status: {test_flight_data[0]['status']} - Gate: {test_flight_data[0]['gate']}")

# Delete the flight
print("\n5. Deleting flight TEST101...")
response = requests.delete('http://localhost:7860/api/flights/TEST101')
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Verify deletion
print("\n6. Verifying deletion...")
response = requests.get('http://localhost:7860/api/flights')
flights = response.json()
test_flight_data = [f for f in flights if f['flight_number'] == 'TEST101']
print(f"Flight TEST101 exists: {len(test_flight_data) > 0}")

print("\n✅ Flight management API test completed!")