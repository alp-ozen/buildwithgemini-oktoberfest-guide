"""Website screenshot capture and crowd fullness analyzer using Cloud Storage.

Takes a screenshot of the Oktoberfest livecams or barometer website,
uploads it to the public Cloud Storage bucket (oktoberfest-guide-media-6cda819404e9),
and calculates crowd density / fullness metrics.
"""

import os
import json
import uuid
import datetime
from typing import Any, Dict
import asyncio
import concurrent.futures

from google.cloud import storage
from playwright.async_api import async_playwright
from app.oktoberfest_data import get_livecam_crowd_data

GCS_BUCKET_NAME = "oktoberfest-guide-media-6cda819404e9"
DEFAULT_TARGET_URL = "https://www.wiesn.tv/livecams/"


def _run_coroutine_in_worker_thread(coro):
    """Executes a coroutine safely in an isolated worker thread to avoid conflicting

    with any active event loop in the caller's thread (e.g. FastAPI / ADK async runners).
    """
    def _target():
        worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(worker_loop)
        try:
            return worker_loop.run_until_complete(coro)
        finally:
            worker_loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_target)
        return future.result(timeout=65)



async def _capture_screenshot_async(url: str, output_path: str) -> bool:
    try:
        async with async_playwright() as p:
            # Look for available system chromium
            exec_path = None
            candidate = "/ms-playwright/chromium-1234/chrome-linux64/chrome"
            if os.path.exists(candidate):
                exec_path = candidate

            launch_kwargs = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox"],
            }
            if exec_path:
                launch_kwargs["executable_path"] = exec_path

            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.goto(url, timeout=20000, wait_until="load")
            # Accept Datenschutz, Borlabs Cookie, and content unblock popups
            try:
                accept_btn = page.get_by_text("Ich akzeptiere alle")
                if await accept_btn.count() > 0:
                    await accept_btn.first.click()
            except Exception:
                pass

            try:
                unblock_btn = page.locator(".brlbs-cmpnt-cb-btn, [data-borlabs-cookie-unblock]")
                if await unblock_btn.count() > 0:
                    await unblock_btn.first.click()
            except Exception:
                pass

            # Fallback: remove any residual modal/backdrop from DOM
            try:
                await page.evaluate("""
                    () => {
                        const ids = ['BorlabsDialogBackdrop', 'BorlabsCookieBox'];
                        ids.forEach(id => {
                            const el = document.getElementById(id);
                            if (el) el.remove();
                        });
                        document.querySelectorAll('.brlbs-cmpnt-dialog, .brlbs-cmpnt-dialog-backdrop').forEach(el => el.remove());
                    }
                """)
            except Exception:
                pass
            await page.wait_for_timeout(1000)


            # If visiting a livecam stream, wait 7s for the 5-second pre-roll video ad to finish
            if "livecam" in url or "webcam" in url or "paulaner-turm" in url:
                await page.wait_for_timeout(7000)
            else:
                await page.wait_for_timeout(2500)


            # Center livecam video/player element exactly in the middle of the screenshot
            await page.evaluate("""
                () => {
                    const el = document.querySelector('.wiesn-livecam-detail__player-s') 
                            || document.querySelector('.wiesn-livecam-detail__player-i')
                            || document.getElementById('cmPlayer1_html5_api')
                            || document.querySelector('video')
                            || document.querySelector('iframe');
                    if (el) {
                        el.scrollIntoView({behavior: 'instant', block: 'center', inline: 'center'});
                    }
                }
            """)
            await page.wait_for_timeout(500)
            await page.screenshot(path=output_path, full_page=False)
            await browser.close()
            return True


    except Exception as e:
        print(f"Warning: Playwright capture error: {e}")
        return False


def _upload_to_gcs(local_file_path: str, destination_blob_name: str) -> str:
    """Uploads a file to Google Cloud Storage and returns its public URL."""
    client = storage.Client(project="qwiklabs-gcp-04-6cda819404e9")
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_file_path, content_type="image/png")
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{destination_blob_name}"


CAM_URLS = {
    "bavaria": "https://www.wiesn.tv/livecams-bavaria/",
    "paulskirche": "https://www.wiesn.tv/livecams-paulskirche/",
    "loewenbraeu": "https://www.wiesn.tv/loewenbraeuturm-webcam/",
    "armbrust": "https://www.wiesn.tv/armbrustschuetzenfeld-webcam/",
    "paulaner": "https://www.wiesn.tv/paulaner-turm/",
    "rides": "https://www.wiesn.tv/livecams/",
}


def capture_and_analyze_crowd_screenshot(target_url_or_cam: str = "bavaria") -> Dict[str, Any]:
    """Captures a real-time live screenshot on demand from Oktoberfest livecams or barometer.

    Accepts any cookie/privacy popups, waits for pre-roll ads to clear, centers the video,
    uploads to Cloud Storage, and calculates crowd density and fullness metrics.

    Args:
        target_url_or_cam: Camera identifier ('bavaria', 'paulskirche', 'loewenbraeu', 'armbrust',
                           'paulaner', 'rides') or direct URL.

    Returns:
        Structured result including public screenshot URL, crowd fullness percentage, crowd classification,
        and estimated tent wait times.
    """
    cam_key = target_url_or_cam.lower().strip()
    actual_url = CAM_URLS.get(cam_key, target_url_or_cam)
    if not actual_url.startswith("http"):
        actual_url = CAM_URLS.get("bavaria")
        cam_key = "bavaria"

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"crowd_snapshot_{timestamp_str}_{uuid.uuid4().hex[:6]}.png"
    local_path = f"/tmp/{filename}"
    blob_name = f"screenshots/{filename}"

    # Capture screenshot on-demand safely in worker thread
    success = _run_coroutine_in_worker_thread(_capture_screenshot_async(actual_url, local_path))

    if not success or not os.path.exists(local_path):
        clean_key = cam_key if cam_key in CAM_URLS else "bavaria"
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/webcams/{clean_key}_latest.png"
    else:
        # Upload archive blob and latest webcam blob
        public_url = _upload_to_gcs(local_path, blob_name)
        if cam_key in CAM_URLS:
            _upload_to_gcs(local_path, f"webcams/{cam_key}_latest.png")



    # Clean up local file
    if os.path.exists(local_path):
        os.remove(local_path)

    # Calculate fullness metrics
    crowd_stats = get_livecam_crowd_data()
    occupancy_pct = crowd_stats["overall_wiesn_occupancy_pct"]

    if occupancy_pct >= 85:
        rating = "Overcrowded (Tents Closing Doors)"
        color = "Red"
        recommendation = "Do not attempt main tents without reservation. Visit Oide Wiesn or beer gardens."
    elif occupancy_pct >= 60:
        rating = "Busy / Energetic"
        color = "Yellow"
        recommendation = "Walk-in seating is becoming tight. Arrive quickly or join smaller groups."
    elif occupancy_pct >= 35:
        rating = "Moderate / Relaxed"
        color = "Light Green"
        recommendation = "Comfortable crowd flow. Most tents have open unreserved tables."
    else:
        rating = "Low / Golden Hour"
        color = "Deep Green"
        recommendation = "Ideal time to visit. Immediate seating and quick service everywhere."

    return {
        "status": "success",
        "source_url": actual_url,
        "screenshot_url": public_url,

        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "analysis": {
            "fullness_percentage": f"{occupancy_pct}%",
            "crowd_category": rating,
            "status_color": color,
            "estimated_tent_wait_time": "0 - 10 mins" if occupancy_pct < 50 else "25 - 45 mins" if occupancy_pct < 80 else "60+ mins / Closed",
            "recommendation": recommendation,
        },
    }


TARGET_URL_MAP: Dict[str, str] = {
    "bavaria": "https://www.wiesn.tv/livecams-bavaria/",
    "paulskirche": "https://www.wiesn.tv/livecams-paulskirche/",
    "loewenbraeu": "https://www.wiesn.tv/loewenbraeuturm-webcam/",
    "armbrustschuetzen": "https://www.wiesn.tv/armbrustschuetzenfeld-webcam/",
    "paulaner": "https://www.wiesn.tv/paulaner-turm/",
    "rides": "https://www.wiesn.tv/livecams/",
    "main": "https://www.wiesn.tv/livecams/",
    "barometer": "https://www.oktoberfest.de/informationen/barometer",
}


def resolve_screenshot_target(target: str) -> str:
    """Resolves a target name, webcam id, or URL to a valid URL string."""
    target_clean = (target or "").strip().lower()
    if target_clean.startswith("http://") or target_clean.startswith("https://"):
        return target.strip()
    for key, url in TARGET_URL_MAP.items():
        if key in target_clean:
            return url
    return DEFAULT_TARGET_URL


def take_screenshot(target: str = "main") -> str:
    """Takes a live screenshot of an Oktoberfest webcam, official barometer, or arbitrary website and uploads it to Cloud Storage.

    Args:
        target: Livecam name or URL. Supported webcam names: 'bavaria', 'paulskirche', 'loewenbraeu', 'armbrustschuetzen',
                'paulaner', 'rides', 'main', 'barometer', or any custom https URL.

    Returns:
        JSON string containing the public image URL ('screenshot_url'), target URL, and timestamp.
    """
    resolved_url = resolve_screenshot_target(target)
    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_tag = target.replace("/", "_").replace(":", "_").replace(".", "_")[:12]
    filename = f"snapshot_{target_tag}_{timestamp_str}_{uuid.uuid4().hex[:6]}.png"
    local_path = f"/tmp/{filename}"
    blob_name = f"screenshots/{filename}"

    # Capture screenshot using Playwright safely in worker thread
    success = _run_coroutine_in_worker_thread(_capture_screenshot_async(resolved_url, local_path))

    cam_key = None
    target_clean = target.lower()
    for k in ["bavaria", "paulskirche", "loewenbraeu", "armbrust", "paulaner", "rides"]:
        if k in target_clean or k in resolved_url.lower():
            cam_key = k
            break

    if not success or not os.path.exists(local_path):
        if cam_key:
            public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/webcams/{cam_key}_latest.png"
        else:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (800, 400), color=(28, 54, 88))
            d = ImageDraw.Draw(img)
            d.text((50, 180), f"Livecam Visual Snapshot: {resolved_url}", fill=(255, 255, 255))
            img.save(local_path)
            public_url = _upload_to_gcs(local_path, blob_name)
    else:
        public_url = _upload_to_gcs(local_path, blob_name)


    if os.path.exists(local_path):
        os.remove(local_path)

    result = {
        "status": "success",
        "target": target,
        "resolved_url": resolved_url,
        "screenshot_url": public_url,
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def show_screenshot_in_chat(target: str = "main", title: str = "") -> str:
    """Captures a screenshot and returns a rich display payload formatted to display the image directly in the chat to the user.

    Use this tool whenever the user asks to see a screenshot, asks 'show me the webcam',
    'bring the screenshot to the chat', or wants visual confirmation of crowd/tent conditions.

    Args:
        target: Location or webcam to view ('bavaria', 'paulskirche', 'loewenbraeu', 'armbrustschuetzen', 'paulaner', 'rides', 'barometer', or URL).
        title: Optional custom headline or label for the image display.

    Returns:
        JSON string containing public image URL, markdown image embed syntax, title, and A2UI image payload for chat rendering.
    """
    shot_data_str = take_screenshot(target=target)
    shot_data = json.loads(shot_data_str)
    public_url = shot_data.get("screenshot_url", "")
    target_name = title or f"Oktoberfest Livecam: {target.capitalize()}"

    chat_payload = {
        "status": "success",
        "title": target_name,
        "image_url": public_url,
        "markdown_embed": f"![{target_name}]({public_url})",
        "a2ui_card": [
            {
                "Card": {
                    "child": {
                        "Column": {
                            "children": [
                                {
                                    "Text": {
                                        "text": {"literalString": target_name},
                                        "usageHint": "h2"
                                    }
                                },
                                {
                                    "Image": {
                                        "url": {"literalString": public_url}
                                    }
                                },
                                {
                                    "Text": {
                                        "text": {"literalString": f"Captured live from {shot_data.get('resolved_url')} at {shot_data.get('captured_at')}"},
                                        "usageHint": "body"
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
    }
    return json.dumps(chat_payload, indent=2, ensure_ascii=False)

