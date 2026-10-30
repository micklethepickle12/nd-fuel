#!/usr/bin/env python3
"""Download Notre Dame dining hall menus to local CSV and JSON files."""
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'https://nd.api.nutrislice.com/menu/api/weeks/school/{hall}/menu-type/{meal}/{year}/{month}/{day}/'
HALLS = {'south': 'south-dining-hall', 'north': 'north-dining-hall'}
MEALS = ('breakfast', 'lunch', 'dinner')
FIELDS = ['date', 'hall', 'meal', 'station', 'food', 'serving_size', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g', 'sodium_mg', 'allergens_and_tags']

def fetch(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; NDMenuFetcher/1.0)', 'Accept': 'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)

def flatten(payload, hall, meal):
    rows = []
    for day in payload.get('days', []):
        station = ''
        for item in day.get('menu_items', []):
            if item.get('is_station_header'):
                station = item.get('text') or station
            food = item.get('food')
            if not food:
                continue
            n = food.get('rounded_nutrition_info') or {}
            serving = food.get('serving_size_info') or {}
            icons = (food.get('icons') or {}).get('food_icons') or []
            rows.append({
                'date': day.get('date'), 'hall': hall, 'meal': meal,
                'station': station, 'food': food.get('name', ''),
                'serving_size': f"{serving.get('serving_size_amount', '')} {serving.get('serving_size_unit', '')}".strip(),
                'calories': n.get('calories'), 'protein_g': n.get('g_protein'),
                'carbs_g': n.get('g_carbs'), 'fat_g': n.get('g_fat'),
                'fiber_g': n.get('g_fiber'), 'sodium_mg': n.get('mg_sodium'),
                'allergens_and_tags': ', '.join(i.get('name', '') for i in icons),
            })
    return rows


def main():
    day = date.today()
    if len(sys.argv) > 1:
        try:
            day = date.fromisoformat(sys.argv[1])
        except ValueError:
            sys.exit('Date must be YYYY-MM-DD, e.g. 2026-10-29')
    rows, errors = [], []
    # Request the current week and the following week, avoiding duplicates.
    for week_day in (day, day + timedelta(days=7)):
        for hall, slug in HALLS.items():
            for meal in MEALS:
                url = BASE.format(hall=slug, meal=meal, year=week_day.year, month=week_day.month, day=week_day.day)
                try:
                    payload = fetch(url)
                    if not isinstance(payload, dict) or 'days' not in payload:
                        raise ValueError('Unexpected response format')
                    part = flatten(payload, hall, meal)
                    rows.extend(part)
                    print(f'OK {week_day} {hall} {meal}: {len(part)} entries')
                except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f'{week_day} {hall} {meal}: {exc}')
                    print(f'FAILED {week_day} {hall} {meal}: {exc}')
    if errors:
        sys.exit('Menu download incomplete; keeping last published menu. ' + '; '.join(errors))
    if not rows:
        sys.exit('No menu items received; keeping last published menu.')
    unique = {(r['date'], r['hall'], r['meal'], r['station'], r['food'], r['serving_size']): r for r in rows}
    rows = sorted(unique.values(), key=lambda r: (r['date'], r['hall'], r['meal'], r['station'], r['food']))
    out = Path(__file__).resolve().parent
    with (out / 'all_menus.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out / 'all_menus.json').write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Saved {len(rows)} menu items.')

if __name__ == '__main__':
    main()
