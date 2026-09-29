"""Webcam screenshot collector for Oktoberfest livecams.

Captures all 6 HD livecams from wiesn.tv, uploads them to the public Cloud Storage bucket
(gs://oktoberfest-guide-media-6cda819404e9/), and updates latest frames every 5 minutes.
"""

import os
import sys
import time
import datetime
import asyncio
from typing import Dict, List, Tuple
from google.cloud import storage
from playwright.async_api import async_playwright

GCS_BUCKET_NAME = "oktoberfest-guide-media-6cda819404e9"
PROJECT_ID = "qwiklabs-gcp-04-6cda819404e9"

WEBCAMS: List[Tuple[str, str, str]] = [
    ("bavaria", "Bavaria Statue & Ruhmeshalle", "https://www.wiesn.tv/livecams-bavaria/"),
    ("paulskirche", "St. Paul Church Tower", "https://www.wiesn.tv/livecams-paulskirche/"),
    ("loewenbraeu", "Löwenbräu-Turm Wirtsbudenstraße", "https://www.wiesn.tv/loewenbraeuturm-webcam/"),
    ("armbrust", "Armbrustschützenzelt Field", "https://www.wiesn.tv/armbrustschuetzenfeld-webcam/"),
    ("paulaner", "Paulaner-Turm Overview", "https://www.wiesn.tv/paulaner-turm/"),
    ("rides", "Schaustellerstraße Rides Boulevard", "https://www.wiesn.tv/livecams/"),
]


def get_gcs_bucket():
    client = storage.Client(project=PROJECT_ID)
    return client.bucket(GCS_BUCKET_NAME)


async def capture_webcams_batch(bucket) -> Dict[str, str]:
    results = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

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

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        for cam_id, label, url in WEBCAMS:
            temp_file = f"/tmp/cam_{cam_id}_{timestamp_str}.png"
            try:
                print(f"[{now.strftime('%H:%M:%S')}] Navigating to {label} ({url})...")
                await page.goto(url, timeout=25000, wait_until="load")
                await page.wait_for_timeout(1000)

                # Accept Datenschutz, Borlabs Cookie, and content unblock popups
                print(f"[{now.strftime('%H:%M:%S')}] Accepting Datenschutz / Cookie popups if present...")
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
                await page.wait_for_timeout(1000)

                
                # Wait 7 seconds for the mandatory 5-second pre-roll ad to finish playing
                print(f"[{now.strftime('%H:%M:%S')}] Waiting 7s for pre-roll ad to finish...")
                await page.wait_for_timeout(7000)

                # Align webcam player exactly in the middle of the screenshot
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
                await page.screenshot(path=temp_file, full_page=False)

                # Upload to GCS: 1. Timelapse archive, 2. Current latest
                archive_blob = f"timelapse/{cam_id}/{cam_id}_{timestamp_str}.png"
                latest_blob = f"webcams/{cam_id}_latest.png"

                blob_arch = bucket.blob(archive_blob)
                blob_arch.upload_from_filename(temp_file, content_type="image/png")

                blob_latest = bucket.blob(latest_blob)
                blob_latest.upload_from_filename(temp_file, content_type="image/png")

                public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{latest_blob}"
                results[cam_id] = public_url
                print(f" -> Uploaded: {public_url}")

            except Exception as e:
                print(f" -> Error capturing {cam_id}: {e}")
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

        await browser.close()

    return results


def run_collection(once: bool = False, interval_seconds: int = 300):
    print(f"=== Starting Webcam Collector (Interval: {interval_seconds}s, Bucket: {GCS_BUCKET_NAME}) ===")
    bucket = get_gcs_bucket()

    while True:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(capture_webcams_batch(bucket))
            loop.close()
            print(f"Batch completed: {len(results)} of {len(WEBCAMS)} webcams captured.")
        except Exception as e:
            print(f"Unexpected error in capture cycle: {e}")

        if once:
            break

        print(f"Sleeping for {interval_seconds} seconds (5 minutes) until next snapshot cycle...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    is_daemon = "--daemon" in sys.argv
    print(f"Running on-demand webcam snapshot (daemon mode: {is_daemon})...")
    run_collection(once=not is_daemon, interval_seconds=300)

