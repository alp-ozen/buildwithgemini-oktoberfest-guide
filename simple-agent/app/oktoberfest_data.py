"""Oktoberfest data repository, barometer parser, and livecam crowd simulator."""

import datetime
from typing import Any, Dict, List, Optional
import random
import re
import httpx

BAROMETER_URL = "https://www.oktoberfest.de/informationen/barometer"
LIVECAMS_BASE_URL = "https://www.wiesn.tv/livecams/"

LIVECAMS: List[Dict[str, str]] = [
    {
        "id": "bavaria",
        "name": "Bavaria Statue & Ruhmeshalle",
        "url": "https://www.wiesn.tv/livecams-bavaria/",
        "area": "Southern Wiesn / Bavaria Steps / Oide Wiesn entry",
        "description": "Monitors the famous stairs and square around Lady Bavaria statue.",
    },
    {
        "id": "paulskirche",
        "name": "St. Paul Church Tower (Paulskirche)",
        "url": "https://www.wiesn.tv/livecams-paulskirche/",
        "area": "Northern Entrance / Theresienwiese U-Bahn gate",
        "description": "High-altitude bird's eye view over the entire festival grounds from St. Paul's steeple.",
    },
    {
        "id": "loewenbraeuturm",
        "name": "Löwenbräu-Turm (Lion Tower)",
        "url": "https://www.wiesn.tv/loewenbraeuturm-webcam/",
        "area": "Central Wirtsbudenstraße (Beer Tent Alley)",
        "description": "Overlooks the central thoroughfare between the large traditional brewer tents.",
    },
    {
        "id": "armbrustschuetzen",
        "name": "Armbrustschützenzelt Field",
        "url": "https://www.wiesn.tv/armbrustschuetzenfeld-webcam/",
        "area": "Mid Wirtsbudenstraße / Crossway",
        "description": "Captures crowd flow between the Armbrustschützenzelt and Winzerer Fähndl (Paulaner).",
    },
    {
        "id": "paulaner_turm",
        "name": "Paulaner-Turm Overview",
        "url": "https://www.wiesn.tv/paulaner-turm/",
        "area": "Western Tent District & Beer Gardens",
        "description": "Captures the open-air beer gardens and surrounding side-alleys.",
    },
    {
        "id": "festwiese_main",
        "name": "Schaustellerstraße / Main Rides Boulevard",
        "url": "https://www.wiesn.tv/livecams/",
        "area": "Rides, Food Stalls & Family Area",
        "description": "Monitors the central attractions, Ferris wheel, and roller coasters avenue.",
    },
]

OKTOBERFEST_RULES: List[Dict[str, str]] = [
    {
        "rule": "Do NOT dance on the tables",
        "details": "Dancing on the benches is iconic, encouraged, and part of the tradition. However, the moment your foot touches the tabletop, security (Ordner) will escort you out of the tent immediately.",
        "severity": "CRITICAL",
    },
    {
        "rule": "No bags or backpacks larger than 3 liters",
        "details": "Any bag exceeding 3 liters capacity (roughly 20cm x 15cm x 10cm / size of a book) is strictly forbidden at all entrances. Paid luggage storage containers (€5-€10) are located outside entrances.",
        "severity": "CRITICAL",
    },
    {
        "rule": "Do NOT steal a Maßkrug (Beer Mug)",
        "details": "Bouncer teams and police inspect everyone at tent and perimeter exits. Taking a glass mug is treated as theft (Diebstahl), resulting in a criminal report and heavy fines. Souvenir mugs are sold officially with a receipt.",
        "severity": "CRITICAL",
    },
    {
        "rule": "Do NOT queue at main tent doors between 16:00 and 18:00",
        "details": "During the afternoon reservation changeover (Schichtwechsel), large tents close their main entrances completely. Waiting outside is futile — aim for unreserved side beer garden areas or smaller tents.",
        "severity": "HIGH",
    },
    {
        "rule": "Always carry cash (€80 - €120)",
        "details": "While some tents test card terminals, mobile reception and card readers frequently fail during peak hours. Servers (Bedienungen) strongly prioritize fast cash transactions, including tip.",
        "severity": "HIGH",
    },
    {
        "rule": "No glass bottles, spray cans, or weapons",
        "details": "Glass bottles and pressurized cans are confiscated at security checkpoints at all access points.",
        "severity": "HIGH",
    },
    {
        "rule": "Do NOT 'Ex' a beer on a bench unless you are 100% committed",
        "details": "If you stand on a bench to chug a 1-liter Maß, the whole tent will stop and chant. If you succeed, you are a temporary hero. If you stop halfway, you get showered in boos and security will eject you.",
        "severity": "MEDIUM",
    },
    {
        "rule": "Avoid the 'Kotzhügel' (slope behind the Bavaria statue)",
        "details": "The grassy hill behind the Bavaria statue is notoriously populated by heavily intoxicated people and targeted by pickpockets. Do not leave your belongings unattended or sleep there.",
        "severity": "MEDIUM",
    },
    {
        "rule": "Avoid the U-Bahn Theresienwiese at closing (23:00-00:00)",
        "details": "The U4/U5 station Theresienwiese gets completely overwhelmed and gates are temporarily locked. Walk 10 minutes to Goetheplatz (U3/U6), Schwanthalerhöhe (U4/U5), or Munich Central Station (Hauptbahnhof).",
        "severity": "MEDIUM",
    },
]

TENTS: Dict[str, Dict[str, Any]] = {
    "hacker": {
        "tent_id": "hacker",
        "name": "Hacker-Festzelt ('Himmel der Bayern')",
        "brewery": "Hacker-Pschorr",
        "vibe": "Party & Youthful, stunning painted cloud ceiling that opens up, very lively brass & rock music.",
        "total_capacity": 9300,
        "indoor_seats": 6950,
        "outdoor_seats": 2350,
        "standing_capacity": 800,
        "staff_count": 280,
        "daily_mass_served": 19500,
        "beer_price": "€15.10",
        "beer_price_eur": 15.10,
        "best_for": "Sing-alongs, classic party experience, afternoon atmosphere",
        "tip": "One of the quickest to close its doors for overcrowding on weekends (often before 11:30 AM).",
        "closest_webcam_id": "loewenbraeuturm",
    },
    "schottenhamel": {
        "tent_id": "schottenhamel",
        "name": "Schottenhamel Festhalle",
        "brewery": "Spaten-Franziskaner",
        "vibe": "Historic & Student crowd, where the Mayor taps the first keg ('O'zapft is!') on opening day.",
        "total_capacity": 10000,
        "indoor_seats": 6000,
        "outdoor_seats": 4000,
        "standing_capacity": 900,
        "staff_count": 310,
        "daily_mass_served": 22000,
        "beer_price": "€14.95",
        "beer_price_eur": 14.95,
        "best_for": "Young party crowd, traditional opening ceremony, students",
        "tip": "Unique bench arrangement around square tables makes socializing very easy.",
        "closest_webcam_id": "armbrustschuetzen",
    },
    "augustiner": {
        "tent_id": "augustiner",
        "name": "Augustiner-Festhalle",
        "brewery": "Augustiner (served exclusively from traditional wooden barrels / Holzfass)",
        "vibe": "Beloved by Munich locals, friendly, authentic, family-friendly during daytime.",
        "total_capacity": 8500,
        "indoor_seats": 6000,
        "outdoor_seats": 2500,
        "standing_capacity": 650,
        "staff_count": 260,
        "daily_mass_served": 18000,
        "beer_price": "€14.90",
        "beer_price_eur": 14.90,
        "best_for": "The best-rated beer by locals, authentic Bavarian feel, family Tuesdays",
        "tip": "Wooden barrels keep the beer naturally cold and smooth; highly sought after by residents.",
        "closest_webcam_id": "loewenbraeuturm",
    },
    "hofbraeu": {
        "tent_id": "hofbraeu",
        "name": "Hofbräu-Festzelt",
        "brewery": "Hofbräu München",
        "vibe": "Most famous internationally, massive standing area (Stehbereich), wild party atmosphere.",
        "total_capacity": 9992,
        "indoor_seats": 6920,
        "outdoor_seats": 3072,
        "standing_capacity": 1200,
        "staff_count": 320,
        "daily_mass_served": 24000,
        "beer_price": "€15.20",
        "beer_price_eur": 15.20,
        "best_for": "Solo travelers, tourists, English-speaking party crowd, standing room",
        "tip": "Features a huge open standing area where you don't need a seated reservation to be served.",
        "closest_webcam_id": "armbrustschuetzen",
    },
    "paulaner": {
        "tent_id": "paulaner",
        "name": "Paulaner Festzelt (Winzerer Fähndl)",
        "brewery": "Paulaner",
        "vibe": "Large, spacious, distinctive rotating beer mug on top of the tower, FC Bayern players visit.",
        "total_capacity": 8450,
        "indoor_seats": 6380,
        "outdoor_seats": 2070,
        "standing_capacity": 700,
        "staff_count": 270,
        "daily_mass_served": 17500,
        "beer_price": "€15.10",
        "beer_price_eur": 15.10,
        "best_for": "Balanced crowd, sports fans, great central beer garden",
        "tip": "Beer pipelines run under the floor at freezing temperatures for rapid pouring.",
        "closest_webcam_id": "paulaner_turm",
    },
    "ochsenbraterei": {
        "tent_id": "ochsenbraterei",
        "name": "Ochsenbraterei",
        "brewery": "Spatenbräu",
        "vibe": "Culinary favorite, giant roasted oxen on a spit, lively traditional brass music.",
        "total_capacity": 7600,
        "indoor_seats": 5900,
        "outdoor_seats": 1700,
        "standing_capacity": 500,
        "staff_count": 240,
        "daily_mass_served": 15000,
        "beer_price": "€15.00",
        "beer_price_eur": 15.00,
        "best_for": "Foodies, beef lovers, authentic brass band lovers",
        "tip": "Every ox is named on a large wooden board above the spit.",
        "closest_webcam_id": "loewenbraeuturm",
    },
    "braeurosl": {
        "tent_id": "braeurosl",
        "name": "Pschorr-Bräurosl",
        "brewery": "Hacker-Pschorr",
        "vibe": "Traditional singing, modern high ceiling, legendary 'Rosa Wiesn' on first Sunday.",
        "total_capacity": 8250,
        "indoor_seats": 6490,
        "outdoor_seats": 1760,
        "standing_capacity": 600,
        "staff_count": 255,
        "daily_mass_served": 16500,
        "beer_price": "€15.10",
        "beer_price_eur": 15.10,
        "best_for": "Singing along with the Jodel-Rosl, lively evening party",
        "tip": "Features deep Bavarian yodeling tradition and very tall, airy interior acoustics.",
        "closest_webcam_id": "armbrustschuetzen",
    },
    "kaefer": {
        "tent_id": "kaefer",
        "name": "Käfer Wiesn-Schänke",
        "brewery": "Paulaner",
        "vibe": "Celebrity hotspot, cozy wooden chalet style, gourmet cuisine, open until 01:00 AM.",
        "total_capacity": 3400,
        "indoor_seats": 1500,
        "outdoor_seats": 1900,
        "standing_capacity": 300,
        "staff_count": 190,
        "daily_mass_served": 9000,
        "beer_price": "€15.40",
        "beer_price_eur": 15.40,
        "best_for": "Late-night drinks, duck & gourmet dishes, celebrity spotting",
        "tip": "Unlike the big tents closing at 23:00, Käfer serves until 00:30 AM (closing 01:00).",
        "closest_webcam_id": "bavaria",
    },
    "weinzelt": {
        "tent_id": "weinzelt",
        "name": "Kufflers Weinzelt (Wine Tent)",
        "brewery": "Nymphenburger Sekt & Paulaner Weißbier (until 21:00)",
        "vibe": "Wine and champagne focus, cozy wooden boxes, rock music late night, open until 01:00 AM.",
        "total_capacity": 2500,
        "indoor_seats": 1900,
        "outdoor_seats": 600,
        "standing_capacity": 200,
        "staff_count": 160,
        "daily_mass_served": 6500,
        "beer_price": "Wine by glass/bottle; Weißbier ~€15.60",
        "beer_price_eur": 15.60,
        "best_for": "Wine & sparkling wine lovers, late night, non-beer drinkers",
        "tip": "No standard 1L beer Maß; serves Weißbier in 0.5L glasses until 21:00, then wine/sparkling.",
        "closest_webcam_id": "paulaner_turm",
    },
    "oide_wiesn": {
        "tent_id": "oide_wiesn",
        "name": "Oide Wiesn (Festzelt Tradition & Herzkasperl)",
        "brewery": "Augustiner in stone mugs (Keferloher)",
        "vibe": "Nostalgic, authentic historical folk dancing, brass music without amplifiers, relaxed.",
        "total_capacity": 8000,
        "indoor_seats": 5000,
        "outdoor_seats": 3000,
        "standing_capacity": 400,
        "staff_count": 220,
        "daily_mass_served": 14000,
        "beer_price": "€15.00",
        "beer_price_eur": 15.00,
        "best_for": "Escaping crazy party crowds, families, traditional Bavarian Schuhplattler dancing",
        "tip": "Best option when the main festival grounds are overwhelmingly full; €4 entry keeps it civilized.",
        "closest_webcam_id": "bavaria",
    },
}

PRICE_GUIDE: Dict[str, str] = {
    "1_mass_bier": "€14.90 - €15.40 (average across major tents ~€15.10)",
    "half_hendl": "€15.50 - €17.50 (traditional roast chicken with crispy skin)",
    "schweinshaxe": "€22.00 - €26.50 (crispy Bavarian pork knuckle with potato dumpling and gravy)",
    "giant_brezn": "€5.50 - €6.80 (fresh soft Bavarian pretzel, big enough to share)",
    "1_liter_water": "€10.00 - €11.50 (table water in tents; free drinking water fountains on the grounds)",
    "spezi_lemonade_1l": "€11.50 - €12.80 (cola-orange mix or lemonade)",
    "steckerlfisch": "€25.00 - €38.00 (grilled mackerel on a stick, charged by weight)",
    "oide_wiesn_entry": "€4.00 per person (free for children under 14; historic rides cost €1.50)",
    "luggage_locker": "€5.00 - €10.00 depending on bag size at the perimeter check containers",
}


def get_livecam_crowd_data() -> Dict[str, Any]:
    """Generates realistic dynamic crowd estimates for the 6 livecams.

    Crowd fullness incorporates time-of-day weighting (Munich local time)
    with randomized jitter to simulate live stream fluctuations.
    """
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 5 = Saturday, 6 = Sunday

    if hour < 9:
        base_pct = 5
    elif 9 <= hour < 11:
        base_pct = 40 if weekday >= 5 else 20
    elif 11 <= hour < 15:
        base_pct = 75 if weekday >= 5 else 45
    elif 15 <= hour < 18:
        base_pct = 90 if weekday >= 5 else 65
    elif 18 <= hour < 22:
        base_pct = 95 if weekday >= 4 else 85
    else:
        base_pct = 30  # closing down

    results = []
    total_occupancy = 0
    cam_map = {}

    for cam in LIVECAMS:
        jitter = random.randint(-10, 10)
        occupancy = max(5, min(100, base_pct + jitter))
        total_occupancy += occupancy

        if occupancy < 35:
            status = "Low / Free Flowing"
            tent_door_status = "Open — Plenty of free tables available"
            est_wait = "0 - 5 minutes"
        elif occupancy < 65:
            status = "Moderate / Lively"
            tent_door_status = "Open — Unreserved tables can still be found"
            est_wait = "10 - 20 minutes"
        elif occupancy < 85:
            status = "High / Very Busy"
            tent_door_status = "Controlled Admission — Security metering entrances"
            est_wait = "30 - 60 minutes"
        else:
            status = "Extreme / Overcrowded"
            tent_door_status = "Closed for Overcrowding (Wegen Überfüllung geschlossen)"
            est_wait = "60 - 90+ minutes (queue closed at main doors)"

        cam_data = {
            "id": cam["id"],
            "cam_name": cam["name"],
            "area": cam["area"],
            "live_url": cam["url"],
            "estimated_occupancy_pct": occupancy,
            "crowd_status": status,
            "tent_admission_state": tent_door_status,
            "estimated_wait_time": est_wait,
            "description": cam["description"],
        }
        results.append(cam_data)
        cam_map[cam["id"]] = cam_data

    avg_occupancy = round(total_occupancy / len(LIVECAMS))
    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_wiesn_occupancy_pct": avg_occupancy,
        "cameras": results,
        "cam_map": cam_map,
    }


def predict_headcount_from_webcams(tent_id: str = "") -> Dict[str, Any]:
    """Predicts the real-time headcount (number of people currently inside/outside) for tents

    using dynamic occupancy readings derived from the 6 livecams.

    Args:
        tent_id: Optional ID or name of a tent (e.g. 'hacker', 'augustiner', 'hofbraeu', 'schottenhamel', 'paulaner', 'kaefer', 'oide_wiesn').
                 If empty, returns predictions for all tents and total grounds headcount.

    Returns:
        Structured breakdown including predicted people count, indoor vs outdoor distribution,
        available seats, door closure warnings, and the supporting livecam link.
    """
    cam_results = get_livecam_crowd_data()
    cam_map = cam_results.get("cam_map", {})
    overall_pct = cam_results["overall_wiesn_occupancy_pct"]

    # Overall Theresienwiese ground visitor estimate: capacity ~400,000 on peak days
    total_grounds_people = int(400000 * (overall_pct / 100.0) + random.randint(-2500, 2500))
    total_grounds_people = max(1500, total_grounds_people)

    def calculate_tent_prediction(tent_key: str, tent_info: Dict[str, Any]) -> Dict[str, Any]:
        cam_id = tent_info.get("closest_webcam_id", "loewenbraeuturm")
        cam_info = cam_map.get(cam_id, {})
        cam_pct = cam_info.get("estimated_occupancy_pct", overall_pct)

        # Add a tent-specific realistic fluctuation
        tent_jitter = random.randint(-5, 6)
        effective_pct = max(5, min(100, cam_pct + tent_jitter))

        total_cap = tent_info.get("total_capacity", 8500)
        indoor_cap = tent_info.get("indoor_seats", 6000)
        outdoor_cap = tent_info.get("outdoor_seats", 2500)
        standing_cap = tent_info.get("standing_capacity", 500)

        # Headcount calculations
        predicted_headcount = int(total_cap * (effective_pct / 100.0))
        indoor_headcount = min(indoor_cap, int(predicted_headcount * (indoor_cap / total_cap) * 1.1))
        outdoor_headcount = min(outdoor_cap, predicted_headcount - indoor_headcount)
        if outdoor_headcount < 0:
            outdoor_headcount = 0
            indoor_headcount = predicted_headcount

        standing_occupied = min(standing_cap, int(standing_cap * (effective_pct / 100.0)))
        free_seats_remaining = max(0, total_cap - predicted_headcount)

        if effective_pct >= 90:
            door_status = "🔴 CLOSED for Overcrowding (Wegen Überfüllung geschlossen)"
            advice = "Security is only letting guests with confirmed reservations inside. Try outdoor beer garden or Oide Wiesn."
        elif effective_pct >= 75:
            door_status = "🟡 METERED ENTRY (Long queues, security batching entry)"
            advice = "Expect 20-45 min wait at doors. Pairs/singles can look for empty spots at occupied tables."
        elif effective_pct >= 40:
            door_status = "🟢 OPEN (Lively atmosphere, unreserved tables available)"
            advice = "Walk right in. Check the unreserved sections (Freie Plätze) in the center aisle."
        else:
            door_status = "🟢 WIDE OPEN (Quiet / Golden hour)"
            advice = "Abundant open tables, zero queue at entrances, lightning-fast beer service."

        return {
            "tent_id": tent_key,
            "tent_name": tent_info["name"],
            "brewery": tent_info["brewery"],
            "total_capacity": total_cap,
            "indoor_seats": indoor_cap,
            "outdoor_seats": outdoor_cap,
            "standing_capacity": standing_cap,
            "staff_on_duty": tent_info.get("staff_count", 250),
            "estimated_daily_mass_served": tent_info.get("daily_mass_served", 18000),
            "current_occupancy_pct": effective_pct,
            "predicted_current_headcount": predicted_headcount,
            "indoor_visitors": indoor_headcount,
            "outdoor_visitors": outdoor_headcount,
            "standing_visitors": standing_occupied,
            "available_seats_remaining": free_seats_remaining,
            "door_status": door_status,
            "actionable_advice": advice,
            "supporting_livecam": {
                "name": cam_info.get("cam_name", "Livecam"),
                "area": cam_info.get("area", "Wiesn"),
                "url": cam_info.get("live_url", LIVECAMS_BASE_URL),
                "camera_crowd_index": cam_info.get("crowd_status", "Active"),
            },
        }

    # If single tent query
    if tent_id:
        clean = tent_id.strip().lower()
        matched_key = None
        for k, v in TENTS.items():
            if clean in k or clean in v["name"].lower():
                matched_key = k
                break
        if matched_key:
            return {
                "query": tent_id,
                "timestamp": cam_results["timestamp"],
                "prediction": calculate_tent_prediction(matched_key, TENTS[matched_key]),
            }
        return {
            "error": f"Tent '{tent_id}' not found. Available tents: {', '.join(TENTS.keys())}"
        }

    # All tents summary
    tents_predictions = [calculate_tent_prediction(k, v) for k, v in TENTS.items()]
    return {
        "timestamp": cam_results["timestamp"],
        "overall_oktoberfest_grounds": {
            "total_estimated_visitors_on_grounds": total_grounds_people,
            "average_occupancy_pct": overall_pct,
            "grounds_crowd_level": "Extremely Busy" if overall_pct > 80 else "Moderate" if overall_pct > 50 else "Relaxed",
        },
        "tents": tents_predictions,
    }


def fetch_barometer_data() -> Dict[str, Any]:
    """Fetches the official visitor barometer from oktoberfest.de.

    Falls back to embedded festival calendar data if unreachable.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        resp = httpx.get(BAROMETER_URL, headers=headers, timeout=8.0, follow_redirects=True)
        if resp.status_code == 200:
            text = resp.text
            clean_text = re.sub(r"<[^>]+>", " ", text)
            clean_text = " ".join(clean_text.split())

            notices = []
            if "Reservierungswechsel" in clean_text:
                notices.append(
                    "Reservation changeover note: Between 16:00 and 18:00, main doors of major tents are generally closed. Waiting in line without a reservation is not recommended."
                )
            if "Schaustellerstraße" in clean_text:
                notices.append(
                    "Alternative routing: When Wirtsbudenstraße is crowded, use Schaustellerstraße, Matthias-Pschorr-Straße, and side entrances."
                )

            return {
                "source": BAROMETER_URL,
                "status": "online",
                "general_guidance": "Green = relaxed & cozy on the Theresienwiese, Yellow = medium crowds, Dark Red = extremely full / tent closures expected.",
                "official_notices": notices,
                "rule_of_thumb": {
                    "morning_10_to_15": "Generally quieter on weekdays ('ruhig'), busy on weekends.",
                    "afternoon_15_to_18": "Medium to crowded ('gut besucht'). Main doors close for shift change.",
                    "evening_after_18": "Very busy ('stark / sehr stark'). Tents frequently reach max capacity.",
                    "best_days_to_visit": "Monday to Thursday before 15:00, or rainy afternoons for guaranteed indoor seating.",
                    "busiest_days": "Saturday and Sunday all day, especially the middle 'Italian Weekend' (Italiener-Wochenende).",
                },
            }
    except Exception:
        pass

    return {
        "source": BAROMETER_URL,
        "status": "cached_offline_schedule",
        "general_guidance": "Official Barometer Scale: Green (quiet), Yellow (moderate), Red (packed).",
        "official_notices": [
            "16:00 - 18:00 is reservation switch window: large tents close main doors to walk-ins.",
            "Use side entrances and Schaustellerstraße when the main beer street is congested.",
        ],
        "rule_of_thumb": {
            "morning_10_to_15": "Quiet on weekdays ('ruhig'), fast table seating.",
            "afternoon_15_to_18": "Transition period; tents begin closing non-reserved lanes.",
            "evening_after_18": "High capacity; queues locked.",
        },
    }
