from opensky_api import OpenSkyApi
from flightaware_api import FlightAwareAPI
import time
from datetime import datetime, timezone
import pytz
# Configuration
FLIGHTAWARE_API_KEY = "oZdMTAzCFpI8BVMRhVOjFBbGuNZt6bev"

# Update these constants
SOUTH_WEST_LAT, SOUTH_WEST_LON = 41.94774639163531, -87.73394803145516
NORTH_EAST_LAT, NORTH_EAST_LON = 42.03079536502291, -87.59029769334172


# Bounding box coordinates (approximately 10 miles in each direction)
OHARE_SOUTH_WEST_LAT, OHARE_SOUTH_WEST_LON = 41.8386, -88.0848
OHARE_NORTH_EAST_LAT, OHARE_NORTH_EAST_LON = 42.1186, -87.7248

def get_flights_and_details(opensky_api, flightaware_api):
    print("Fetching flight data...")
    #states = opensky_api.get_states(bbox=(SOUTH_WEST_LAT, NORTH_EAST_LAT, SOUTH_WEST_LON, NORTH_EAST_LON))
    states = opensky_api.get_states(bbox=(OHARE_SOUTH_WEST_LAT, OHARE_NORTH_EAST_LAT, OHARE_SOUTH_WEST_LON, OHARE_NORTH_EAST_LON))
    if not states or not states.states:
        print("No data received")
        return

    flights_with_details = []
    current_time = int(time.time())
    one_hour_ago = current_time - 3600

    for state in states.states:
        if state.on_ground or state.last_contact <= one_hour_ago:
            continue

        heading = state.true_track
        if heading is None or (heading < 45 or heading > 315):  # Exclude north/south flights
            continue

        is_departing = 45 <= heading <= 225  # Heading east (departing)

        print(f"Processing data for aircraft {state.icao24} with callsign {state.callsign}...")
        
        if state.callsign:
            # Convert last_contact to Central Time
            ct_tz = pytz.timezone('America/Chicago')
            last_contact_utc = datetime.fromtimestamp(state.last_contact, tz=timezone.utc)
            last_contact_ct = last_contact_utc.astimezone(ct_tz)
            
            print(f"Last contact (CT): {last_contact_ct.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            flight_data = flightaware_api.get_flight_info(state.callsign.strip())
            if flight_data and flight_data.get('flights', []):
                # Increment the monthly calls counter
                flightaware_api.increment_monthly_calls()
                
                # Select the flight closest to current time
                now = datetime.now(timezone.utc)
                closest_flight = min(
                    flight_data['flights'],
                    key=lambda x: abs(datetime.fromisoformat(x['scheduled_out'].rstrip('Z') if x['scheduled_out'] else '').replace(tzinfo=timezone.utc) - now) if x['scheduled_out'] else float('inf')
                )
                
                flight_info = flightaware_api.extract_flight_info({'flights': [closest_flight]})
                
                if flight_info:
                    flight_info.update({
                        'icao24': state.icao24,
                        'latitude': state.latitude,
                        'longitude': state.longitude,
                        'altitude': state.baro_altitude,
                        'last_contact_ct': last_contact_ct.strftime('%Y-%m-%d %H:%M:%S %Z'),
                        'is_departing': is_departing,
                        'heading': heading
                    })
                    flights_with_details.append(flight_info)
                else:
                    print(f"No detailed flight information found for {state.callsign}")
            else:
                print(f"No FlightAware data available for {state.callsign}")
        else:
            print(f"No callsign available for aircraft {state.icao24}")

    return flights_with_details

def main():
    opensky_api = OpenSkyApi()
    flightaware_api = FlightAwareAPI(FLIGHTAWARE_API_KEY, max_calls_per_run=5, cache_duration_minutes=15, monthly_limit=1000)
    flights = get_flights_and_details(opensky_api, flightaware_api)

    if flights:
        print(f"\nFound {len(flights)} flight(s) in the specified area:")
        for flight in flights:
            print(f"Callsign: {flight.get('callsign', 'N/A')}")
            print(f"Heading: {flight.get('heading', 'N/A')}° ({'Departing' if flight.get('is_departing') else 'Arriving'})")
            print(f"Last Contact (CT): {flight.get('last_contact_ct', 'N/A')}")
            print(f"Origin: {flight.get('origin', 'N/A')} ({flight.get('origin_display', 'N/A')})")
            print(f"Destination: {flight.get('destination', 'N/A')} ({flight.get('destination_display', 'N/A')})")
            print(f"Operator: {flight.get('operator', 'N/A')}")
            print(f"Aircraft Type: {flight.get('aircraft_type', 'N/A')}")
            print(f"Aircraft Size: {flight.get('aircraft_size', 'N/A')} ({flight.get('total_seats', 'N/A')} seats)")
            print(f"Aircraft Make/Model: {flight.get('aircraft_make_model', 'N/A')}")
            print(f"Speed: {flight.get('speed', 'N/A')} kts")
            print(f"Status: {flight.get('status', 'N/A')}")
            print(f"Delayed: {'Yes' if flight.get('is_delayed') else 'No'}")
            print(f"Time in Air: {flight.get('time_in_air', 'N/A')}")
            print(f"Route Distance: {flight.get('route_distance', 'N/A')} nm")
            print(f"Current Position: Lat: {flight.get('latitude', 'N/A')}, Lon: {flight.get('longitude', 'N/A')}, Alt: {flight.get('altitude', 'N/A')} m")
            print("---")
    else:
        print("No flights found in the O'Hare area")

    print(f"FlightAware API calls made this run: {flightaware_api.calls_made}")
    print(f"FlightAware API calls made this month: {flightaware_api.monthly_calls}")

if __name__ == "__main__":
    main()
