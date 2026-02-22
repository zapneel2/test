import requests
import os
import subprocess
import json
import time

GRAPH_VERSION = "v18.0"

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
SOURCE_IG_USER_ID = os.getenv("SOURCE_IG_USER_ID")
TARGET_IG_USER_ID = os.getenv("TARGET_IG_USER_ID")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_REF = os.getenv("GITHUB_REF_NAME")

MEDIA_FOLDER = "media"
POSTED_FILE = "posted_media.json"


# =========================
# Git Functions
# =========================

def git_commit():
    subprocess.run(["git", "config", "--global", "user.email", "action@github.com"])
    subprocess.run(["git", "config", "--global", "user.name", "github-actions"])
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", "Auto update"], check=False)
    subprocess.run(["git", "push"], check=False)


# =========================
# Storage
# =========================

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    with open(POSTED_FILE, "r") as f:
        return json.load(f)


def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =========================
# Instagram API
# =========================

def api_get(url, params):
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


def api_post(url, data):
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()


def check_publish_limit():
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{TARGET_IG_USER_ID}/content_publishing_limit"
    return api_get(url, {"access_token": ACCESS_TOKEN})


def get_source_media():
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{SOURCE_IG_USER_ID}/media"
    return api_get(url, {
        "fields": "id,media_type,media_url,caption,timestamp",
        "access_token": ACCESS_TOKEN
    })["data"]


def download_media(media):
    os.makedirs(MEDIA_FOLDER, exist_ok=True)

    ext = "jpg" if media["media_type"] == "IMAGE" else "mp4"
    filename = f"{media['id']}.{ext}"
    path = os.path.join(MEDIA_FOLDER, filename)

    content = requests.get(media["media_url"]).content
    with open(path, "wb") as f:
        f.write(content)

    return filename


def create_container(public_url, media):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{TARGET_IG_USER_ID}/media"

    payload = {
        "caption": media.get("caption", ""),
        "access_token": ACCESS_TOKEN
    }

    if media["media_type"] == "IMAGE":
        payload["image_url"] = public_url
    elif media["media_type"] == "VIDEO":
        payload["video_url"] = public_url
        payload["media_type"] = "VIDEO"
    else:
        return None  # Skip unsupported types

    return api_post(url, payload)["id"]


def publish_container(creation_id):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{TARGET_IG_USER_ID}/media_publish"
    return api_post(url, {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    })


# =========================
# Main
# =========================

def main():

    print("Checking publish limit...")
    print(check_publish_limit())

    posted_ids = load_posted()
    media_list = sorted(get_source_media(), key=lambda x: x["timestamp"])

    for media in media_list:

        if media["id"] in posted_ids:
            continue

        print("Processing:", media["id"])

        filename = download_media(media)
        git_commit()

        public_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_REF}/{MEDIA_FOLDER}/{filename}"

        creation_id = create_container(public_url, media)

        if not creation_id:
            continue

        if media["media_type"] == "VIDEO":
            print("Waiting for video processing...")
            time.sleep(30)

        publish_container(creation_id)

        posted_ids.append(media["id"])
        save_posted(posted_ids)
        git_commit()

        print("Published:", media["id"])


if __name__ == "__main__":
    main()
