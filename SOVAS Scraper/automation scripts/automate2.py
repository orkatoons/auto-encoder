import json
import time
import pyperclip
import keyboard
import re
import requests
import html
import random
from urllib.parse import unquote
from googlesearch import search
from bs4 import BeautifulSoup
import os

# File paths
base_dir = r"C:\Encode Tools\auto-encoder\SOVAS Scraper"
input_json_path = os.path.join(base_dir, "json data", "voice_actors.json")
output_json_path = os.path.join(base_dir, "json data", "final_data.json")
progress_path = os.path.join(base_dir, "json data", "progress2.json")

MAX_RATE_LIMIT_HITS = 3
COOLDOWN_TIME = 4800  # 80 minutes

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0)...",
    "Mozilla/5.0 (X11; Linux x86_64)...",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)...",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B)..."
]

# Load input JSON data
if not os.path.exists(input_json_path):
    print(f"❗ Input JSON file not found at {input_json_path}")
    exit(1)

with open(input_json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)  # Each dict should have "Name" and "Profile"

# Load progress
start_index = 0
if os.path.exists(progress_path):
    try:
        with open(progress_path, "r") as f:
            progress_data = json.load(f)
            start_index = progress_data.get("last_index", 0)
            print(f"🔄 Resuming from index: {start_index}")
    except Exception:
        print("⚠️ Could not read progress. Starting from beginning.")

pause_flag = [False]
keyboard.add_hotkey('F8', lambda: pause_flag.__setitem__(0, not pause_flag[0]))

def wait_if_paused():
    while pause_flag[0]:
        time.sleep(0.1)

def has_existing_email(person_data):
    """Check if the person already has an email in their data"""
    # Check if marked as unavailable
    if person_data.get("Email") == "unavailable" or person_data.get("Email_Status") == "unavailable":
        return True
    
    # Check the main Email field
    if person_data.get("Email") and person_data["Email"] not in [None, "", "null", "unavailable"]:
        return True
    
    # Check the Emails array
    emails = person_data.get("Emails", [])
    if isinstance(emails, list) and len(emails) > 0:
        # Filter out empty or invalid emails
        valid_emails = [email for email in emails if email and email not in [None, "", "null", "unavailable"]]
        if valid_emails:
            return True
    
    return False

def extract_emails_from_url(url):
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 429:
            print(f"🚨 429 Rate Limit from {url}")
            raise Exception("429 Rate Limit")

        soup = BeautifulSoup(response.text, 'html.parser')
        text = html.unescape(unquote(soup.get_text()))
        raw_emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        cleaned = []

        for email in raw_emails:
            email = email.strip().split()[0]
            if email.count('@') == 1 and len(email) <= 254:
                cleaned.append(email)

        return list(set(cleaned))  # Remove duplicates
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 429:
                raise Exception("429 Rate Limit")
        raise
    except Exception as e:
        if "429" in str(e):
            raise Exception("429 Rate Limit")
        return []

print("✅ Script running. Minimize this terminal but DO NOT close it.")

consecutive_rate_limit_hits = 0
google_search_count = 0  # Track actual Google searches performed

for i in range(start_index, len(data)):
    wait_if_paused()

    # Only do cooldown if 100 actual Google searches were completed
    if google_search_count > 0 and google_search_count % 100 == 0:
        print(f"\n🕒 Completed {google_search_count} Google searches. Cooling down for 80 minutes...")
        time.sleep(COOLDOWN_TIME)

    name = data[i].get("Name", "")
    if not name:
        print(f"❌ No name at index {i}, skipping...")
        continue

    # Check if person already has an email
    if has_existing_email(data[i]):
        print(f"⏭️ Skipping [{i + 1}/{len(data)}]: {name} - already has email")
        # Still save progress
        with open(progress_path, 'w') as f:
            json.dump({"last_index": i + 1}, f)
        continue

    query = f"@gmail.com {name} voice actor"
    print(f"\n🔍 Searching [{i + 1}/{len(data)}]: {query}")

    try:
        results = list(search(query, num_results=5))
        consecutive_rate_limit_hits = 0
        google_search_count += 1  # Increment counter only for actual searches
    except Exception as e:
        if "429" in str(e):
            print("⚠️ Google rate-limited. Cooling down 80 min...")
            consecutive_rate_limit_hits += 1
            time.sleep(COOLDOWN_TIME)
            if consecutive_rate_limit_hits >= MAX_RATE_LIMIT_HITS:
                print("🚫 Too many rate-limit hits. Exiting...")
                break
            continue
        else:
            print(f"❌ Google search failed: {e}")
            # Mark as unavailable due to search error
            data[i]['Email'] = "unavailable"
            data[i]['Email_Status'] = "unavailable"
            print("❌ Marked as unavailable due to search error.")
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            with open(progress_path, 'w') as f:
                json.dump({"last_index": i + 1}, f)
            continue

    time.sleep(random.uniform(3, 10))

    best_email = ""
    max_match_count = 0
    name_words = [w.lower() for w in name.split()]
    existing_emails = set(data[i].get("Emails", []))
    if isinstance(existing_emails, str):
        existing_emails = set([existing_emails])

    # Track if any URLs were successfully scraped
    successful_scrapes = 0
    total_urls = len(results)

    for url in results:
        print(f"🌐 Scraping: {url}")
        try:
            emails = extract_emails_from_url(url)
            consecutive_rate_limit_hits = 0
            successful_scrapes += 1
        except Exception as e:
            if "429" in str(e):
                print("⚠️ Scraping rate-limited. Cooling down 80 min...")
                consecutive_rate_limit_hits += 1
                time.sleep(COOLDOWN_TIME)
                if consecutive_rate_limit_hits >= MAX_RATE_LIMIT_HITS:
                    print("🚫 Too many rate-limit hits. Exiting...")
                    break
                continue
            else:
                print(f"❌ Error scraping URL: {e}")
                continue

        for email in emails:
            if email in existing_emails:
                continue
            local_part = email.split('@')[0].lower()
            match_count = sum(word in local_part for word in name_words)
            if match_count > max_match_count:
                best_email = email
                max_match_count = match_count

        time.sleep(random.uniform(1, 3))

    # If no URLs were successfully scraped, mark as unavailable
    if successful_scrapes == 0 and total_urls > 0:
        data[i]['Email'] = "unavailable"
        data[i]['Email_Status'] = "unavailable"
        print("❌ All URLs failed to scrape. Marked as unavailable.")
    elif best_email:
        existing_emails.add(best_email)
        data[i]['Emails'] = list(existing_emails)
        print(f"✅ Found Email: {best_email}")
    else:
        if not existing_emails:
            data[i]['Emails'] = []
        # Mark as unavailable so it can be skipped in future runs
        data[i]['Email'] = "unavailable"
        data[i]['Email_Status'] = "unavailable"
        print("❌ No email found. Marked as unavailable for future skips.")

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    with open(progress_path, 'w') as f:
        json.dump({"last_index": i + 1}, f)

print("\n🎉 Done! Progress saved.")
