import requests
import json
from datetime import datetime, timedelta
import os
import csv
from typing import Dict, Tuple

def load_processed_airport_data() -> Dict[str, Tuple[str, str, str]]:
    airport_data = {}
    with open('processed_airports.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ident = row['ident']
            airport_data[ident] = (row['iso_country'], row['country_name'], row['municipality'])
    return airport_data

AIRPORT_DATA = load_processed_airport_data()

def get_airport_info(ident: str) -> Tuple[str, str, str]:
    return AIRPORT_DATA.get(ident, ('Unknown', 'Unknown', 'Unknown'))

class FlightAwareAPI:
    def __init__(self, api_key, max_calls_per_run=5, cache_duration_minutes=15, monthly_limit=3000):
        self.api_key = api_key
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
        self.headers = {
            'x-apikey': self.api_key
        }
        self.cache = {}
        self.max_calls_per_run = max_calls_per_run
        self.calls_made = 0
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.monthly_limit = monthly_limit
        self.monthly_calls_file = 'monthly_calls.json'
        self.load_monthly_calls()
        self.monthly_calls = self.load_monthly_calls()

    def load_monthly_calls(self):
        if os.path.exists(self.monthly_calls_file):
            with open(self.monthly_calls_file, 'r') as f:
                data = json.load(f)
                monthly_calls = data['calls']
                last_reset = datetime.fromisoformat(data['last_reset'])
        else:
            monthly_calls = 0
            last_reset = datetime.now()

        # Reset if it's a new month
        if last_reset.month != datetime.now().month:
            monthly_calls = 0
            last_reset = datetime.now()

        self.save_monthly_calls(monthly_calls, last_reset)
        return monthly_calls

    def save_monthly_calls(self, calls, last_reset):
        with open(self.monthly_calls_file, 'w') as f:
            json.dump({
                'calls': calls,
                'last_reset': last_reset.isoformat()
            }, f)

    def get_flight_info(self, ident):
        # Check if monthly limit is reached
        if self.monthly_calls >= self.monthly_limit:
            print(f"Monthly API call limit ({self.monthly_limit}) reached. Skipping API call for {ident}.")
            return None

        # Check cache first
        if ident in self.cache:
            cached_time, cached_data = self.cache[ident]
            if datetime.now() - cached_time < self.cache_duration:
                print(f"Using cached data for {ident}")
                return cached_data

        # Make the API call
        try:
            # Set up start and end times for a 2-hour window
            now = datetime.utcnow()
            start_time = now - timedelta(hours=2)
            end_time = now + timedelta(hours=1)

            # Format times as ISO8601 strings
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            params = {
                'start': start_str,
                'end': end_str
            }
            response = requests.get(f"{self.base_url}/flights/{ident}", headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            self.cache[ident] = (datetime.now(), data)
            
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for flight {ident}: {str(e)}")
            return None

    def increment_monthly_calls(self):
        self.monthly_calls += 1
        self.save_monthly_calls(self.monthly_calls, datetime.now())

    def extract_flight_info(self, data):
        if not data or 'flights' not in data or not data['flights']:
            return None

        flight = data['flights'][0]  # Assuming the first flight is the one we want
        
        # Calculate time in air
        estimated_off = flight.get('estimated_off')
        time_in_air = None
        if estimated_off:
            off_time = datetime.fromisoformat(estimated_off.rstrip('Z'))
            time_in_air = str(datetime.utcnow() - off_time)

        # Check if flight is delayed
        scheduled_out = flight.get('scheduled_out')
        estimated_out = flight.get('estimated_out') or flight.get('actual_out')
        is_delayed = False
        if scheduled_out and estimated_out:
            scheduled = datetime.fromisoformat(scheduled_out.rstrip('Z'))
            estimated = datetime.fromisoformat(estimated_out.rstrip('Z'))
            is_delayed = estimated > scheduled

        # Calculate total seats
        total_seats = ((flight.get('seats_cabin_business', 0) or 0) + 
                       (flight.get('seats_cabin_coach', 0) or 0) + 
                       (flight.get('seats_cabin_first', 0) or 0))

        origin_code = flight.get('origin', {}).get('code', 'N/A')
        destination_code = flight.get('destination', {}).get('code', 'N/A')

        origin_iso, origin_country, origin_city = get_airport_info(origin_code)
        dest_iso, dest_country, dest_city = get_airport_info(destination_code)

        # Include origin country if it's not US
        origin_display = f"{origin_city}, {origin_country}" if not origin_country in ('United States of America','United Kingdom of Great Britain and Northern Ireland') else origin_city
        destination_display = f"{dest_city}, {dest_country}" if not dest_country in ('United States of America','United Kingdom of Great Britain and Northern Ireland') else dest_city
        return {
            'callsign': flight.get('ident', 'N/A'),
            'origin': origin_code,
            'origin_city': origin_city,
            'origin_country': origin_country,
            'origin_iso': origin_iso,
            'origin_display': origin_display,
            'destination': destination_code,
            'destination_city': dest_city,
            'destination_country': dest_country,
            'destination_iso': dest_iso,
            'destination_display': destination_display,
            'latitude': None,  # Not available in this data
            'longitude': None,  # Not available in this data
            'altitude_ft': None,  # Not available in this data
            'speed': flight.get('filed_airspeed', 'N/A'),
            'operator': flight.get('operator', 'N/A'),
            'aircraft_type': flight.get('aircraft_type', 'N/A'),
            'status': flight.get('status', 'N/A'),
            'scheduled_out': flight.get('scheduled_out', 'N/A'),
            'estimated_out': flight.get('estimated_out', 'N/A'),
            'actual_out': flight.get('actual_out', 'N/A'),
            'scheduled_in': flight.get('scheduled_in', 'N/A'),
            'estimated_in': flight.get('estimated_in', 'N/A'),
            'actual_in': flight.get('actual_in', 'N/A'),
            'is_delayed': is_delayed,
            'time_in_air': time_in_air,
            'aircraft_size': self.get_aircraft_size(total_seats),
            'aircraft_make_model': flight.get('aircraft_type', 'N/A'),
            'total_seats': total_seats,
            'route_distance': flight.get('route_distance', 'N/A')
        }

    def get_aircraft_size(self, total_seats):
        if total_seats < 50:
            return 'Small'
        elif total_seats < 150:
            return 'Medium'
        else:
            return 'Large'