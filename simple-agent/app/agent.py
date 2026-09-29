# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from typing import Optional
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.agents.callback_context import CallbackContext

from app.oktoberfest_data import (
    PRICE_GUIDE,
    OKTOBERFEST_RULES,
    get_livecam_crowd_data,
    fetch_barometer_data,
    predict_headcount_from_webcams,
)
from app.firestore_backend import (
    get_tent_from_firestore,
    list_tents_from_firestore,
    update_tent_status_in_firestore,
    add_crowd_report_to_firestore,
    get_latest_crowd_reports_from_firestore,
)
from app.maps_tools import (
    geocode_address,
    find_nearby_places,
)
from app.screenshot_tool import (
    capture_and_analyze_crowd_screenshot,
    take_screenshot,
    show_screenshot_in_chat,
)

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback

MODEL = "gemini-3.6-flash"



async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after each agent turn to persist salient user facts to Vertex AI Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def predict_live_headcount(tent_name_or_id: str = "") -> str:
    """Predicts real-time visitor headcount (people count) for tents or the overall festival grounds by analyzing the 6 livecams.

    Evaluates crowd density from the nearest livecam, factoring in total tent capacity (indoor, outdoor, standing),
    staff count, and time of day to estimate current occupants, open seats remaining, and door admission status.

    Args:
        tent_name_or_id: Optional tent name or ID (e.g. 'hacker', 'augustiner', 'hofbraeu', 'schottenhamel', 'paulaner', 'kaefer', 'oide_wiesn').
                         Leave empty to get a full grounds headcount and all tent estimates.

    Returns:
        JSON string containing predicted headcount, breakdown of indoor/outdoor occupants, free seats, and livecam link.
    """
    prediction = predict_headcount_from_webcams(tent_id=tent_name_or_id)
    return json.dumps(prediction, indent=2, ensure_ascii=False)


def check_oktoberfest_livecams() -> str:
    """Fetches real-time crowd occupancy, congestion levels, and wait estimates across the 6 Oktoberfest livecams.

    The 6 livecams cover:
    1. Bavaria Statue & Ruhmeshalle (Southern Wiesn)
    2. St. Paul Church Tower (Overview from Paulskirche)
    3. Löwenbräu-Turm (Central Beer Tent Alley / Wirtsbudenstraße)
    4. Armbrustschützenzelt Field (Mid-Wirtsbudenstraße)
    5. Paulaner-Turm Overview (Western Beer Gardens)
    6. Schaustellerstraße / Main Rides Boulevard (Rides & Family Area)

    Returns:
        JSON string containing per-camera occupancy percentage, wait times, entrance state, and stream URLs.
    """
    data = get_livecam_crowd_data()
    return json.dumps(data, indent=2, ensure_ascii=False)


def get_oktoberfest_barometer() -> str:
    """Scrapes and retrieves the official visitor barometer data from https://www.oktoberfest.de/informationen/barometer.

    Provides expected crowd density by time slot (10-15h, 15-18h, 18h+), historical rush days,
    and crucial notices such as reservation changeover closure windows.

    Returns:
        JSON string with official crowd ratings, peak windows, and navigation advice.
    """
    data = fetch_barometer_data()
    return json.dumps(data, indent=2, ensure_ascii=False)


def read_tents_database(vibe_filter: str = "", max_price: float = 0.0) -> str:
    """Queries the persistent Firestore database ('oktoberfest_tents') for tents, capacities, prices, and live door status.

    Args:
        vibe_filter: Optional filter by atmosphere (e.g. 'party', 'local', 'tourist', 'family', 'gourmet').
        max_price: Optional maximum beer price in Euros (e.g. 15.00).

    Returns:
        JSON string listing matching tents stored in Firestore.
    """
    tents = list_tents_from_firestore(vibe=vibe_filter, max_price=max_price)
    return json.dumps(tents, indent=2, ensure_ascii=False)


def get_tent_status_firestore(tent_id: str) -> str:
    """Fetches detailed live information, total capacity, indoor/outdoor seats, and door status for a specific tent from Firestore.

    Args:
        tent_id: Tent identifier (e.g. 'hacker', 'schottenhamel', 'augustiner', 'hofbraeu', 'paulaner', 'kaefer', 'oide_wiesn').

    Returns:
        JSON string containing the tent's brewery, capacity, beer price, and current status.
    """
    tent = get_tent_from_firestore(tent_id)
    if tent:
        return json.dumps(tent, indent=2, ensure_ascii=False)
    return f"Tent '{tent_id}' not found in Firestore database."


def update_tent_live_status(tent_id: str, new_status: str, notes: str = "", reporter_name: str = "visitor") -> str:
    """Updates the live admission status or notes for a tent in the Firestore database.

    Args:
        tent_id: Tent ID to update (e.g. 'hacker', 'schottenhamel', 'augustiner', 'hofbraeu', 'paulaner', 'kaefer', 'oide_wiesn').
        new_status: Current status (e.g. 'Open', 'Door Closed (Wegen Überfüllung)', 'Free Standing Room', 'Queue 30m').
        notes: Optional extra context (e.g. 'North entrance bouncers letting in small groups', 'Beer garden has free benches').
        reporter_name: Optional name or alias of the reporter.

    Returns:
        JSON string confirming the updated record in Firestore.
    """
    result = update_tent_status_in_firestore(
        tent_id=tent_id,
        status=new_status,
        notes=notes,
        reported_by=reporter_name,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


def submit_crowd_report(location_or_tent: str, crowd_rating: str, notes: str, user_alias: str = "visitor") -> str:
    """Writes a new crowd observation or tip into the Firestore 'wiesn_crowd_reports' collection.

    Args:
        location_or_tent: Area or tent (e.g. 'Wirtsbudenstraße', 'Hacker entrance', 'Bavaria steps', 'U-Bahn Theresienwiese').
        crowd_rating: Crowd level ('Low', 'Moderate', 'Packed', 'Closed').
        notes: Specific details (e.g. 'Bouncers turned away large groups', 'Bag check queue is 15 mins').
        user_alias: Handle or pseudonym of the user reporting.

    Returns:
        JSON string with confirmation and generated report ID.
    """
    result = add_crowd_report_to_firestore(
        location_or_tent=location_or_tent,
        crowd_rating=crowd_rating,
        notes=notes,
        user_alias=user_alias,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


def get_recent_crowd_reports(limit: int = 5) -> str:
    """Reads the most recent community crowd and wait-time reports from Firestore.

    Args:
        limit: Number of recent reports to fetch (default: 5).

    Returns:
        JSON string with recent crowd observations submitted by visitors.
    """
    reports = get_latest_crowd_reports_from_firestore(limit=limit)
    return json.dumps(reports, indent=2, ensure_ascii=False)


def get_oktoberfest_prices(category: str = "") -> str:
    """Retrieves standard pricing for food, drinks, and services at Oktoberfest (Maß beer, Hendl, pretzels, lockers).

    Args:
        category: Optional category filter (e.g., 'beer', 'hendl', 'brezn', 'entry', 'locker').

    Returns:
        Price listing in Euros (€) for typical items on the festival grounds.
    """
    if category:
        cat_lower = category.lower()
        filtered = {k: v for k, v in PRICE_GUIDE.items() if cat_lower in k.lower() or cat_lower in v.lower()}
        if filtered:
            return json.dumps(filtered, indent=2, ensure_ascii=False)
    return json.dumps(PRICE_GUIDE, indent=2, ensure_ascii=False)


def get_what_not_to_do_rules() -> str:
    """Retrieves essential 'What NOT To Do' rules and survival tips for visiting Oktoberfest.

    Covers strict security policies, table dancing prohibitions, bag size restrictions (< 3L),
    Maßkrug theft penalties, cash vs card guidelines, and the 16:00-18:00 tent door lockouts.

    Returns:
        Structured list of dos and don'ts with severity levels.
    """
    return json.dumps(OKTOBERFEST_RULES, indent=2, ensure_ascii=False)


def should_i_go_verdict(
    vibe_preference: str = "party",
    party_size: int = 2,
    has_reservation: bool = False,
    time_of_day: str = "now",
) -> str:
    """Analyzes livecam traffic, barometer crowd forecast, and user constraints to provide a definitive Go / No-Go decision.

    Args:
        vibe_preference: Desired experience: 'party' (wild singing, bench dancing), 'relaxed' (authentic Bavarian, cozy conversation), or 'family' (rides, sweets, Oide Wiesn).
        party_size: Number of people in the group.
        has_reservation: Whether the group already holds a confirmed table reservation.
        time_of_day: Intended arrival time ('now', 'morning', 'afternoon', 'evening').

    Returns:
        A synthesized verdict with calculated crowd risk, recommended tent, entrance strategy, and warnings.
    """
    cam_data = get_livecam_crowd_data()
    avg_occ = cam_data["overall_wiesn_occupancy_pct"]

    if has_reservation:
        verdict = "GO (Full Speed Ahead)"
        reasoning = f"Since you already have a confirmed reservation, you have guaranteed access. Overall grounds occupancy is at {avg_occ}%."
        action = "Arrive at least 20 minutes before your reservation slot. Enter via the designated reservation entrance door (Reservierungs-Eingang) on the tent flank, not the chaotic main walk-in doors."
    elif avg_occ >= 85:
        if party_size > 4:
            verdict = "NO-GO (High Risk of Denial)"
            reasoning = f"Overall Wiesn occupancy is currently around {avg_occ}%. Large tents are experiencing door closures ('Wegen Überfüllung geschlossen'). A walk-in group of {party_size} has near-zero chance of finding empty seats."
            action = "Head to the 'Oide Wiesn' (nostalgic section, €4 entry) where space is much more accessible, or explore unreserved outdoor beer garden perimeters. Better yet, reschedule for weekday morning (before 14:00)."
        else:
            verdict = "CAUTION (Challenging Walk-in)"
            reasoning = f"Crowd levels are high ({avg_occ}%). Walk-in tables inside big tents will be strictly metered by security."
            action = "Target the open standing area (Stehbereich) at Hofbräu, or try the outdoor beer gardens where turnover is faster. Split your group into pairs to hunt for individual open spots at shared tables."
    elif avg_occ >= 60:
        verdict = "GO (Moderate Crowds)"
        reasoning = f"Current crowd occupancy is {avg_occ}%. Vibrant festival atmosphere with reasonable chances of finding unreserved seating if you act promptly."
        action = f"For a '{vibe_preference}' vibe: " + (
            "Head to Hacker-Festzelt or Schottenhamel immediately." if "party" in vibe_preference.lower()
            else "Head to Augustiner-Festhalle or Ochsenbraterei for cozy traditional benches." if "relaxed" in vibe_preference.lower()
            else "Visit the Oide Wiesn (Festzelt Tradition) and the rides along Schaustellerstraße."
        )
    else:
        verdict = "GO (Golden Hour — Best Time to Visit!)"
        reasoning = f"Current crowd index is only {avg_occ}%. Tents have plenty of unreserved tables, quick beer service, and minimal queues."
        action = "Walk right in through the main doors. Pick any tent you like. Claim an unreserved table (freie Plätze) and order your first Maß and Hendl!"

    return json.dumps({
        "verdict": verdict,
        "current_wiesn_occupancy_pct": avg_occ,
        "reasoning": reasoning,
        "recommended_action": action,
        "critical_reminder": "Remember: NEVER dance on the tables (benches only!), no bags > 3L, and bring cash!",
    }, indent=2, ensure_ascii=False)


# Configure A2UI Schema Manager (v0.8) with Basic Catalog
a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description="""You are the ultimate Oktoberfest ("Wiesn") Insider & Decision Assistant — your job is to guide visitors on whether to go to Oktoberfest right now, which tent to choose, how to navigate crowds, find nearby spots on Google Maps, and critically, WHAT NOT TO DO.

You remember the user's stated preferences, dietary needs, favorite beer tents, party sizes, and past visits across conversations and sessions.

You have access to real-time tools:
1. `predict_live_headcount`: Calculates real-time visitor headcounts and occupant numbers for specific tents (e.g. Hacker, Augustiner, Hofbräu) or the entire festival grounds based on livecam readings.
2. `capture_and_analyze_crowd_screenshot`: Takes a live web screenshot of Oktoberfest livecams or barometer, uploads it to Cloud Storage (oktoberfest-guide-media-6cda819404e9), and calculates festival ground fullness and wait times.
3. `take_screenshot`: Takes a live screenshot of a specified webcam or website and returns the public Cloud Storage URL.
4. `show_screenshot_in_chat`: Captures a live screenshot of a webcam or barometer and returns an interactive display card with the image URL to bring it directly into the chat for the user!
5. `geocode_address`: Converts an address or landmark into latitude/longitude coordinates using the Google Maps Geocoding API.
6. `find_nearby_places`: Searches for nearby places of a specific type (e.g., 'restaurant', 'bar', 'transit_station', 'lodging') using Google Maps Places API (New) around given coordinates.
7. `check_oktoberfest_livecams`: Fetches dynamic crowd levels and wait times across 6 real livecam locations (Bavaria, Paulskirche, Löwenbräu-Turm, Armbrustschützenzelt, Paulaner-Turm, Schaustellerstraße) with livecam URLs.
8. `read_tents_database`: Reads tents, total capacities (indoor, outdoor, standing), pricing, and current door statuses from the persistent Firestore database ('oktoberfest_tents').
9. `get_tent_status_firestore`: Retrieves the detailed record and live status for an individual tent from Firestore.
10. `update_tent_live_status`: Writes/updates a tent's live status (e.g. 'Door Closed', 'Open', 'Free Standing Room') in Firestore.
11. `submit_crowd_report`: Writes a visitor crowd observation into Firestore ('wiesn_crowd_reports').
12. `get_recent_crowd_reports`: Reads the latest visitor community reports from Firestore.
13. `get_oktoberfest_barometer`: Pulls official visitor crowd forecasts from https://www.oktoberfest.de/informationen/barometer.
14. `should_i_go_verdict`: Computes a comprehensive 'Go / No-Go' verdict based on party size, vibe preference, reservation status, and live occupancy.
15. `get_oktoberfest_prices`: Food and beer pricing (Maß, Hendl, Schweinshaxe, Pretzels, etc.).
16. `get_what_not_to_do_rules`: Strict security and etiquette rules (table dancing bans, 3L bag limit, mug theft penalties, cash necessity, 16-18h reservation changeover closure).

Tone and Persona:
- Speak like an authentic, savvy Munich local and Wiesn connoisseur (warm, experienced, witty, helpful).
- When asked how many people are there or what tent capacities are, invoke `predict_live_headcount` or `read_tents_database` to cite concrete numbers and supporting livecams!
- When asked to take a screenshot or bring a screenshot to the chat (e.g. "show me the webcam", "take a screenshot of the Bavaria statue / Paulskirche / etc."), call `show_screenshot_in_chat` or `take_screenshot` and render the public image link so the user sees it in the chat!
- When advising visitors, proactively mention practical realities (e.g., if tents are full, don't stand waiting at main doors; tell them about Oide Wiesn or beer gardens).
- When asked "what not to do", be crystal clear about the rules that can get someone kicked out or fined.
- Always personalize responses when you recall past user facts and preferences from long-term memory!
""",
    workflow_description="Analyze the request, call the appropriate tools (Firestore, Maps, Livecams, Headcount, Screenshots), and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        predict_live_headcount,
        capture_and_analyze_crowd_screenshot,
        take_screenshot,
        show_screenshot_in_chat,
        geocode_address,
        find_nearby_places,
        read_tents_database,
        get_tent_status_firestore,
        update_tent_live_status,
        submit_crowd_report,
        get_recent_crowd_reports,
        check_oktoberfest_livecams,
        get_oktoberfest_barometer,
        should_i_go_verdict,
        get_oktoberfest_prices,
        get_what_not_to_do_rules,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)


