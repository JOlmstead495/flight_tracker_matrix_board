import csv
import requests
from typing import Dict, Tuple

def load_country_data() -> Dict[str, str]:
    country_data = {}
    url = "https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/master/all/all.csv"
    response = requests.get(url)
    reader = csv.DictReader(response.text.splitlines())
    for row in reader:
        country_data[row['alpha-2']] = row['name']
    return country_data

def process_and_save_airport_data():
    country_data = load_country_data()
    processed_data = []

    url = "https://raw.githubusercontent.com/datasets/airport-codes/master/data/airport-codes.csv"
    response = requests.get(url)
    reader = csv.DictReader(response.text.splitlines())
    for row in reader:
        if row['type'] == 'large_airport':
            ident = row['ident']
            iso_country = row['iso_country']
            country_name = country_data.get(iso_country, 'Unknown')
            municipality = row['municipality']
            processed_data.append([ident, iso_country, country_name, municipality])

    with open('processed_airports.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ident', 'iso_country', 'country_name', 'municipality'])
        writer.writerows(processed_data)

    print("Processed airport data saved to 'processed_airports.csv'")

if __name__ == "__main__":
    process_and_save_airport_data()