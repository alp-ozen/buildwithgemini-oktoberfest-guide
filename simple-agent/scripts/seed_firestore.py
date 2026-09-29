#!/usr/bin/env python3
"""Seed script to populate Firestore with detailed Oktoberfest tents, capacities, and status data.

IMPORTANT: Project ID is explicitly hardcoded as a string.
"""

import sys
import datetime
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-6cda819404e9"
COLLECTION_NAME = "oktoberfest_tents"

SEED_TENTS = [
    {
        "tent_id": "hacker",
        "name": "Hacker-Festzelt ('Himmel der Bayern')",
        "brewery": "Hacker-Pschorr",
        "vibe": "Party & Youthful, brass-rock music, famous opening ceiling",
        "total_capacity": 9300,
        "indoor_seats": 6950,
        "outdoor_seats": 2350,
        "standing_capacity": 800,
        "staff_count": 280,
        "daily_mass_served": 19500,
        "beer_price_eur": 15.10,
        "status": "Open — High Demand",
        "best_for": "Wild party, afternoon sing-alongs, bench dancing",
        "door_policy": "Closes doors early on weekends due to overcrowding.",
        "rating": 4.8,
        "closest_webcam": "Löwenbräu-Turm (Lion Tower)",
    },
    {
        "tent_id": "schottenhamel",
        "name": "Schottenhamel Festhalle",
        "brewery": "Spaten-Franziskaner",
        "vibe": "Historic, student crowd, official 'O'zapft is!' opening tent",
        "total_capacity": 10000,
        "indoor_seats": 6000,
        "outdoor_seats": 4000,
        "standing_capacity": 900,
        "staff_count": 310,
        "daily_mass_served": 22000,
        "beer_price_eur": 14.95,
        "status": "Open",
        "best_for": "Students, young crowd, socializing around square tables",
        "door_policy": "Arrive before 11:00 AM on Saturdays to get walk-in seats.",
        "rating": 4.6,
        "closest_webcam": "Armbrustschützenzelt Field",
    },
    {
        "tent_id": "augustiner",
        "name": "Augustiner-Festhalle",
        "brewery": "Augustiner (exclusively from wooden barrels / Holzfass)",
        "vibe": "Authentic Bavarian, local favorite, family-friendly",
        "total_capacity": 8500,
        "indoor_seats": 6000,
        "outdoor_seats": 2500,
        "standing_capacity": 650,
        "staff_count": 260,
        "daily_mass_served": 18000,
        "beer_price_eur": 14.90,
        "status": "Open — Fresh wooden barrel just tapped",
        "best_for": "Locals' choice, smoothest traditional beer, cozy atmosphere",
        "door_policy": "Regulars fill unreserved tables quickly at lunch.",
        "rating": 4.9,
        "closest_webcam": "Löwenbräu-Turm (Lion Tower)",
    },
    {
        "tent_id": "hofbraeu",
        "name": "Hofbräu-Festzelt",
        "brewery": "Hofbräu München",
        "vibe": "World-famous international party, massive standing area",
        "total_capacity": 9992,
        "indoor_seats": 6920,
        "outdoor_seats": 3072,
        "standing_capacity": 1200,
        "staff_count": 320,
        "daily_mass_served": 24000,
        "beer_price_eur": 15.20,
        "status": "Open — Free Standing Room",
        "best_for": "Solo travelers, tourists, standing room without table reservations",
        "door_policy": "Standing area in front of music stage accepts walk-ins.",
        "rating": 4.5,
        "closest_webcam": "Armbrustschützenzelt Field",
    },
    {
        "tent_id": "paulaner",
        "name": "Paulaner Festzelt (Winzerer Fähndl)",
        "brewery": "Paulaner",
        "vibe": "Spacious, iconic rotating mug tower, sports stars & balanced crowd",
        "total_capacity": 8450,
        "indoor_seats": 6380,
        "outdoor_seats": 2070,
        "standing_capacity": 700,
        "staff_count": 270,
        "daily_mass_served": 17500,
        "beer_price_eur": 15.10,
        "status": "Open",
        "best_for": "Great central beer garden, hearty traditional meals",
        "door_policy": "Outdoor garden offers faster seating turnover.",
        "rating": 4.7,
        "closest_webcam": "Paulaner-Turm Overview",
    },
    {
        "tent_id": "kaefer",
        "name": "Käfer Wiesn-Schänke",
        "brewery": "Paulaner",
        "vibe": "Celebrity hotspot, gourmet Bavarian dining, open until 01:00 AM",
        "total_capacity": 3400,
        "indoor_seats": 1500,
        "outdoor_seats": 1900,
        "standing_capacity": 300,
        "staff_count": 190,
        "daily_mass_served": 9000,
        "beer_price_eur": 15.40,
        "status": "Reservation Preferred",
        "best_for": "Late-night drinks, roasted duck, gourmet delicacies",
        "door_policy": "Serves beer until 00:30 AM (unlike big tents closing 22:30).",
        "rating": 4.7,
        "closest_webcam": "Bavaria Statue & Ruhmeshalle",
    },
    {
        "tent_id": "oide_wiesn",
        "name": "Oide Wiesn (Festzelt Tradition)",
        "brewery": "Augustiner in stone mugs (Keferloher)",
        "vibe": "Nostalgic, historic folk dancing, brass band without electric amps",
        "total_capacity": 8000,
        "indoor_seats": 5000,
        "outdoor_seats": 3000,
        "standing_capacity": 400,
        "staff_count": 220,
        "daily_mass_served": 14000,
        "beer_price_eur": 15.00,
        "status": "Open — Relaxed Entry (€4 admission)",
        "best_for": "Escaping massive party crowds, authentic culture, families",
        "door_policy": "Best retreat when main festival tents are completely locked.",
        "rating": 4.8,
        "closest_webcam": "Bavaria Statue & Ruhmeshalle",
    },
]


def seed():
    print(f"Connecting to Firestore for project: '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    collection_ref = db.collection(COLLECTION_NAME)

    print(f"Updating {len(SEED_TENTS)} tents with capacity metrics in '{COLLECTION_NAME}'...")
    for item in SEED_TENTS:
        tent_id = item["tent_id"]
        doc_data = dict(item)
        doc_data["last_updated"] = now_iso
        doc_ref = collection_ref.document(tent_id)
        doc_ref.set(doc_data)
        print(f"  ✓ Seeded tent: {item['name']} (Total Cap: {item['total_capacity']:,})")

    print("\n✅ Firestore successfully seeded with tent capacities!")


if __name__ == "__main__":
    seed()
