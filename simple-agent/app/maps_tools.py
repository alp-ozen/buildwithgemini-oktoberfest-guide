"""Google Maps Platform integration: Geocoding API and Places API (New).

Calls the official REST endpoints directly using the API key loaded from the local .env.
API key is never hardcoded.
"""

import os
import json
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

GEOCODING_REST_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_NEARBY_REST_URL = "https://places.googleapis.com/v1/places:searchNearby"


def _get_api_key() -> str:
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise ValueError(
            "GOOGLE_MAPS_API_KEY environment variable is missing. "
            "Please check simple-agent/.env"
        )
    return key


def geocode_address(address: str) -> Dict[str, Any]:
    """Uses the Google Maps Geocoding API REST endpoint to convert an address into geographic coordinates.

    Args:
        address: The address or place name to geocode (e.g., 'Theresienwiese, Munich' or 'Marienplatz 1, Munich').

    Returns:
        Dictionary containing key fields: 'name', 'address', and 'location' (latitude, longitude).
    """
    api_key = _get_api_key()
    params = {
        "address": address,
        "key": api_key,
    }

    try:
        response = httpx.get(GEOCODING_REST_URL, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            first_result = data["results"][0]
            loc = first_result.get("geometry", {}).get("location", {})
            formatted_addr = first_result.get("formatted_address", address)
            return {
                "name": formatted_addr,
                "address": formatted_addr,
                "location": {
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                },
                "place_id": first_result.get("place_id"),
            }
        else:
            return {
                "error": f"Geocoding failed for address '{address}'. Status: {data.get('status')}",
                "raw_response": data,
            }
    except Exception as e:
        return {"error": f"Error calling Geocoding API: {str(e)}"}


def find_nearby_places(
    place_type: str,
    latitude: float,
    longitude: float,
    radius_meters: float = 1000.0,
) -> Dict[str, Any]:
    """Uses the Google Maps Places API (New) REST endpoint to search for nearby places of a specific type.

    Args:
        place_type: The Place type to search for (e.g., 'restaurant', 'bar', 'transit_station', 'lodging', 'tourist_attraction').
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        radius_meters: Search radius in meters (default 1000m / 1km, maximum 50000m).

    Returns:
        Dictionary with a list of matching places returning key fields: 'name', 'address', and 'location'.
    """
    api_key = _get_api_key()

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }

    body = {
        "includedTypes": [place_type],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
    }

    try:
        response = httpx.post(
            PLACES_NEARBY_REST_URL,
            headers=headers,
            json=body,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        places_raw = data.get("places", [])
        clean_places = []
        for p in places_raw:
            clean_places.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", "No address available"),
                "location": {
                    "latitude": p.get("location", {}).get("latitude"),
                    "longitude": p.get("location", {}).get("longitude"),
                },
            })

        return {
            "search_type": place_type,
            "center": {"latitude": latitude, "longitude": longitude},
            "radius_meters": radius_meters,
            "count": len(clean_places),
            "places": clean_places,
        }
    except Exception as e:
        return {"error": f"Error calling Places API (New): {str(e)}"}
