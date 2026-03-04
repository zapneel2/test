import feedparser
import requests
import json
import os
import time
import random
import re
import instaloader

# ==============================
# CONFIGURATION
# ==============================

RSS_URL = "https://rss-bridge.org/bridge01/?action=display&bridge=InstagramBridge&context=Username&u=chennaimemez.in&media_type=all&format=Atom"

IG_USER_ID = "17841475919970444"
ACCESS_TOKEN = "EAAX7o2EBAS8BQ6S8fN6Glr6HCVB0QzweIEAIO8Ig5zVbQn8IZCrlYL9AaBW6KbM1EYmZAb9wYYm7n0zZATqoZAUC7Q9jtSxrUYshw31wCrU1EKyBr98nxKeukOLRaZCuBkmQigYbNZBljzEljTUSMXyn8WNZALlanEVshrDRMStYNf2THL67xwrZBkZB9ZCjYviryM"

STATE_FILE = "state.json"

# ==============================
# INSTALOADER INSTANCE
# ==============================

L = instaloader.Instaloader()

# ==============================
# LOAD STATE
# ==============================

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"posted_ids": []}

posted_ids = set(state["posted_ids"])

# ==============================
# FETCH RSS
# ==============================

feed = feedparser.parse(RSS_URL)

new_entries = []
for entry in reversed(feed.entries):
    if entry.id not in posted_ids:
        new_entries.append(entry)

if not new_entries:
    print("No new posts.")
    exit(0)

# ==============================
# RETRY HELPER
# ==============================

def retry_request(func, max_attempts=3):
    for attempt in range(max_attempts):
        result = func()
        if result:
            return result

        sleep_time = 5 * (2 ** attempt)
        print(f"Retrying in {sleep_time} sec...")
        time.sleep(sleep_time)

    return None

# ==============================
# VIDEO STATUS POLLING
# ==============================

def wait_for_video(container_id, timeout=300):

    start = time.time()

    while time.time() - start < timeout:

        url = f"https://graph.facebook.com/v19.0/{container_id}"

        params = {
            "fields": "status_code",
            "access_token": ACCESS_TOKEN
        }

        r = requests.get(url, params=params)
        data = r.json()

        status = data.get("status_code")

        if status == "FINISHED":
            return True

        if status == "ERROR":
            return False

        print("Video processing...")
        time.sleep(10)

    return False

# ==============================
# INSTAGRAM MEDIA EXTRACTION
# ==============================

def get_media_urls(post_url):

    try:

        shortcode = re.search(r'/p/([^/]+)/', post_url).group(1)

        post = instaloader.Post.from_shortcode(
            L.context,
            shortcode
        )

        if post.typename == "GraphSidecar":

            urls = [
                node.video_url if node.is_video else node.display_url
                for node in post.get_sidecar_nodes()
            ]

        else:

            urls = [
                post.video_url if post.is_video else post.url
            ]

        return urls

    except Exception as e:

        print("Instaloader extraction failed:", e)
        return []

# ==============================
# PROCESS POSTS
# ==============================

for entry in new_entries:

    post_url = entry.id
    caption = entry.title + f"\n\nOriginal: {post_url}"

    print(f"Processing {post_url}")

    media_urls = get_media_urls(post_url)

    if not media_urls:
        print("No media found")
        continue

    # Human-like delay
    time.sleep(random.randint(30, 120))

    for media_url in media_urls:

        is_video = media_url.endswith(".mp4")

        print("Uploading:", media_url)

        # -----------------------
        # CREATE CONTAINER
        # -----------------------

        def create_container():

            payload = {
                "video_url" if is_video else "image_url": media_url,
                "caption": caption,
                "access_token": ACCESS_TOKEN
            }

            r = requests.post(
                f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
                data=payload
            )

            data = r.json()

            return data.get("id")

        container_id = retry_request(create_container)

        if not container_id:
            print("Container creation failed.")
            continue

        # -----------------------
        # WAIT FOR VIDEO
        # -----------------------

        if is_video:

            if not wait_for_video(container_id):
                print("Video processing failed.")
                continue

        # -----------------------
        # PUBLISH
        # -----------------------

        def publish():

            r = requests.post(
                f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": ACCESS_TOKEN
                }
            )

            data = r.json()

            return data.get("id")

        publish_id = retry_request(publish)

        if not publish_id:
            print("Publish failed.")
            continue

        print("Uploaded media:", media_url)

    print("Successfully posted:", post_url)

    # -----------------------
    # UPDATE STATE
    # -----------------------

    posted_ids.add(post_url)

    state["posted_ids"] = list(posted_ids)

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

print("Run complete.")
