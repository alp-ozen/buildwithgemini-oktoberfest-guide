# Project Brief: Oktoberfest ("Wiesn") Insider & Decision Guide

## Overview
An interactive Bavarian assistant that helps visitors decide whether to go to Oktoberfest right now, which tent to choose based on real-time crowds, what budgets to expect, and critically, what NOT to do to avoid security ejection or fines.

## Cloud Infrastructure

### 1. Cloud Storage Bucket (Public Media & Assets)
* **Bucket Name:** `oktoberfest-guide-media-6cda819404e9`
* **GCS URI:** `gs://oktoberfest-guide-media-6cda819404e9/`
* **Location:** `us-east1`
* **Public Access:** Enabled (`--no-public-access-prevention`, `--uniform-bucket-level-access`)
* **IAM Policy:** `allUsers` has `roles/storage.objectViewer`
* **Public URL Pattern:** `https://storage.googleapis.com/oktoberfest-guide-media-6cda819404e9/<filename>` (objects can be directly embedded in web pages and frontend cards as images).

### 2. Cloud Firestore (Database)
* **GCP Project ID (Hardcoded String):** `"qwiklabs-gcp-04-6cda819404e9"`  
  *(Intentionally hardcoded as a literal string in the Firestore client and seed scripts to prevent Agent Platform environment conflicts where `google.auth.default()` returns numeric project IDs).*
* **Primary Collections:**
  1. `oktoberfest_tents`: Persistent catalog of all major festival tents.
     * `tent_id` (string, doc ID): e.g. `hacker`, `schottenhamel`, `augustiner`, `hofbraeu`, `paulaner`, `kaefer`, `oide_wiesn`
     * `name` (string): Full display name
     * `brewery` (string): Serving brewery (e.g. Augustiner Holzfass)
     * `vibe` (string): Atmosphere description
     * `total_capacity` (int): Total people supported (e.g. 9,300)
     * `indoor_seats` (int): Indoor table capacity (e.g. 6,950)
     * `outdoor_seats` (int): Beer garden capacity (e.g. 2,350)
     * `standing_capacity` (int): Standing area capacity (e.g. 800)
     * `staff_count` (int): Number of active staff on duty (e.g. 280)
     * `daily_mass_served` (int): Average daily Maß beer volume (e.g. 19,500)
     * `beer_price_eur` (float): Maß price (e.g. 14.90, 15.10)
     * `status` (string): Live admission status (e.g. `Open`, `Door Closed (Wegen Überfüllung)`, `Fresh wooden barrel just tapped`)
     * `closest_webcam` (string): Nearest mapped webcam
     * `door_policy` (string): Queue advice and entry timing
     * `best_for` (string): Target group (party, locals, students, gourmet)
     * `rating` (float): Average visitor sentiment
     * `last_updated` (ISO timestamp)
  2. `wiesn_crowd_reports`: Real-time community-submitted wait times and crowd updates.
     * `location` (string)
     * `crowd_rating` (string)
     * `notes` (string)
     * `user_alias` (string)
     * `created_at` (ISO timestamp)
* **Seeding Script:** `scripts/seed_firestore.py` (seeds 7 core tents with complete capacity metrics).

## Real-Time & External Integrations
1. **Headcount & Occupancy Prediction Engine:**
   * Analyzes crowd density from the nearest livecam and maps it to the tent's capacity specs (total, indoor, outdoor, standing).
   * Predicts:
     * Current headcount (number of people in the tent right now)
     * Indoor vs outdoor visitor distribution
     * Remaining free seats
     * Door admission status (Open, Metered Queue, Closed for Overcrowding)
     * Overall Theresienwiese ground visitor estimate (~1,500 - 450,000 depending on peak)
2. **Official Oktoberfest Barometer:**
   * URL: `https://www.oktoberfest.de/informationen/barometer`
   * Scrapes official forecast data by time window (10-15h, 15-18h, 18h+) and monitors reservation shift changeover lockout alerts (16:00 - 18:00).
3. **6 HD Livecams (Dynamic Crowd Simulation):**
   * Source: `https://www.wiesn.tv/livecams/`
   * Cameras:
     1. Bavaria Statue & Ruhmeshalle (`https://www.wiesn.tv/livecams-bavaria/`)
     2. St. Paul Church Tower (`https://www.wiesn.tv/livecams-paulskirche/`)
     3. Löwenbräu-Turm (`https://www.wiesn.tv/loewenbraeuturm-webcam/`)
     4. Armbrustschützenzelt Field (`https://www.wiesn.tv/armbrustschuetzenfeld-webcam/`)
     5. Paulaner-Turm Overview (`https://www.wiesn.tv/paulaner-turm/`)
     6. Schaustellerstraße / Main Rides Boulevard (`https://www.wiesn.tv/livecams/`)
   * Dynamic simulation: Generates realistic fluctuating occupancy percentages, queue wait estimates, and tent entrance status based on Munich local time and randomized jitter.

## Fixed Knowledge Base
* **Price Guide:** Maß beer (€14.90 - €15.40), Hendl (€15.50 - €17.50), Schweinshaxe (€22 - €26.50), giant Brezn (€5.50 - €6.80), water & soft drinks (€10 - €12.80/L), Oide Wiesn admission (€4.00).
* **Strict "What NOT To Do" Rules:**
  1. Never dance on tables (benches only).
  2. No bags > 3 liters (< 20cm x 15cm x 10cm).
  3. No stealing Maßkrug (criminal theft prosecution & fines).
  4. No queuing at main tent doors between 16:00 and 18:00 (reservation changeover lockout).
  5. Always carry cash (€80–€120).
  6. No glass bottles or spray cans.
  7. No unsuccessful beer chugging ("Exen") on benches.
  8. Avoid sleeping on the "Kotzhügel" behind Bavaria.
  9. Avoid U-Bahn Theresienwiese at closing peak.

## Tools Registered on Agent
* **Headcount & Prediction:**
  * `predict_live_headcount(tent_name_or_id)`: Calculates real-time visitor count, indoor/outdoor split, remaining seats, and livecam link for any tent or the full festival.
* **Firestore Tools:**
  * `read_tents_database(vibe_filter, max_price)`: Reads and filters tents from Firestore.
  * `get_tent_status_firestore(tent_id)`: Fetches live status and detailed capacities for a specific tent.
  * `update_tent_live_status(tent_id, new_status, notes, reporter_name)`: Updates live tent status in Firestore.
  * `submit_crowd_report(location_or_tent, crowd_rating, notes, user_alias)`: Adds crowd observations.
  * `get_recent_crowd_reports(limit)`: Reads recent community crowd reports.
* **External & Logic Tools:**
  * `check_oktoberfest_livecams()`
  * `get_oktoberfest_barometer()`
  * `should_i_go_verdict(vibe_preference, party_size, has_reservation, time_of_day)`
  * `get_oktoberfest_prices(category)`
  * `get_what_not_to_do_rules()`

## Deployment Policy
* **Local-only testing** until explicitly authorized by the user for cloud deployment.
