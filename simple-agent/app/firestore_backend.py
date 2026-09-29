"""Firestore backend for Oktoberfest tents and visitor status reports.

IMPORTANT: The Google Cloud project ID is intentionally hardcoded as a string.
Do not read it from google.auth.default() or GOOGLE_CLOUD_PROJECT, as those
return the numeric project number on Agent Platform, breaking Firestore after deployment.
"""

import datetime
from typing import Any, Dict, List, Optional
from google.cloud import firestore

# Hardcoded GCP Project ID as required
GCP_PROJECT_ID = "qwiklabs-gcp-04-6cda819404e9"
COLLECTION_TENTS = "oktoberfest_tents"
COLLECTION_REPORTS = "wiesn_crowd_reports"

_db: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    """Returns the singleton Firestore client initialized with the hardcoded project ID."""
    global _db
    if _db is None:
        _db = firestore.Client(project=GCP_PROJECT_ID)
    return _db


def get_tent_from_firestore(tent_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a specific tent document by its ID from Firestore."""
    db = get_db()
    doc_ref = db.collection(COLLECTION_TENTS).document(tent_id.strip().lower())
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        data["tent_id"] = doc.id
        return data
    return None


def list_tents_from_firestore(
    vibe: str = "",
    max_price: float = 0.0,
) -> List[Dict[str, Any]]:
    """Queries tents from Firestore with optional filtering by vibe or maximum beer price."""
    db = get_db()
    tents_ref = db.collection(COLLECTION_TENTS)
    docs = tents_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        data["tent_id"] = doc.id

        # Filter by vibe if requested
        if vibe and vibe.lower() not in data.get("vibe", "").lower() and vibe.lower() not in data.get("best_for", "").lower():
            continue

        # Filter by beer price if requested
        if max_price > 0 and data.get("beer_price_eur", 99.0) > max_price:
            continue

        results.append(data)

    return sorted(results, key=lambda x: x.get("name", ""))


def update_tent_status_in_firestore(
    tent_id: str,
    status: str,
    notes: str = "",
    reported_by: str = "visitor",
) -> Dict[str, Any]:
    """Updates the live status (e.g., 'Open', 'Door Closed', 'Moderate Queues') of a tent in Firestore."""
    db = get_db()
    clean_id = tent_id.strip().lower()
    doc_ref = db.collection(COLLECTION_TENTS).document(clean_id)
    doc = doc_ref.get()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    update_payload = {
        "status": status,
        "last_updated": timestamp,
    }
    if notes:
        update_payload["latest_notes"] = notes
    if reported_by:
        update_payload["last_reported_by"] = reported_by

    if doc.exists:
        doc_ref.update(update_payload)
        return {
            "success": True,
            "tent_id": clean_id,
            "tent_name": doc.to_dict().get("name", clean_id),
            "updated_fields": update_payload,
        }
    else:
        # Create minimal document if it didn't exist
        update_payload["name"] = clean_id.capitalize()
        doc_ref.set(update_payload)
        return {
            "success": True,
            "tent_id": clean_id,
            "tent_name": clean_id,
            "created": True,
            "updated_fields": update_payload,
        }


def add_crowd_report_to_firestore(
    location_or_tent: str,
    crowd_rating: str,
    notes: str,
    user_alias: str = "wiesn_guest",
) -> Dict[str, Any]:
    """Appends a community crowd or wait-time report to Firestore."""
    db = get_db()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report_doc = {
        "location": location_or_tent,
        "crowd_rating": crowd_rating,  # e.g., 'Low', 'Busy', 'Packed', 'Closed'
        "notes": notes,
        "user_alias": user_alias,
        "created_at": timestamp,
    }
    doc_ref = db.collection(COLLECTION_REPORTS).add(report_doc)
    return {
        "success": True,
        "report_id": doc_ref[1].id,
        "data": report_doc,
    }


def get_latest_crowd_reports_from_firestore(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves recent live community reports from Firestore."""
    db = get_db()
    reports_ref = (
        db.collection(COLLECTION_REPORTS)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    results = []
    for doc in reports_ref.stream():
        data = doc.to_dict()
        data["report_id"] = doc.id
        results.append(data)
    return results
