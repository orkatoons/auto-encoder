import json
import time
import pyperclip
import keyboard
import re
import requests
import html
import random
import shutil
from urllib.parse import unquote
from googlesearch import search
from bs4 import BeautifulSoup
import os

# File paths
base_dir = r"C:\Encode Tools\auto-encoder\SOVAS Scraper"
voice_actors_path = os.path.join(base_dir, "json data", "voice_actors.json")
final_data_path = os.path.join(base_dir, "json data", "final_data.json")
progress_path = os.path.join(base_dir, "json data", "progress2.json")
saved_pages_dir = os.path.join(base_dir, "saved offline pages")

MAX_RATE_LIMIT_HITS = 1  # Changed to 1 to end on first rate limit
MAX_SEARCHES_BEFORE_RATE_LIMIT = 5  # Allow 5 searches before rate limit
COOLDOWN_TIME = 4800  # 80 minutes (but we won't use this anymore)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0)...",
    "Mozilla/5.0 (X11; Linux x86_64)...",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)...",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B)..."
]

def notify_completion(scraped_pages):
    try:
        payload = {
            "message": f"SOVAS scraping completed successfully! Scraped {scraped_pages} pages."
        }
        response = requests.post('http://geekyandbrain.ddns.net:3030/api/sovas/scrape/complete', json=payload)
        if response.status_code != 200:
            print(f"Warning: Failed to notify completion: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Warning: Error notifying completion: {str(e)}")

def cleanup_html_files():
    """Clean up saved HTML files at the end"""
    if os.path.exists(saved_pages_dir):
        try:
            for item in os.listdir(saved_pages_dir):
                item_path = os.path.join(saved_pages_dir, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            print("🧹 Cleaned up saved HTML files")
        except Exception as e:
            print(f"⚠️ Failed to clean up HTML files: {e}")

# Load voice_actors.json data
if not os.path.exists(voice_actors_path):
    print(f"❗ Voice actors JSON file not found at {voice_actors_path}")
    exit(1)

with open(voice_actors_path, 'r', encoding='utf-8') as f:
    voice_actors_data = json.load(f)

# Load final_data.json (create if doesn't exist)
final_data = []
if os.path.exists(final_data_path):
    try:
        with open(final_data_path, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
    except Exception:
        print("⚠️ Could not read final_data.json, starting fresh")

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

def needs_email_search(person_data):
    """Check if the person needs email search (email is null or unavailable)"""
    email = person_data.get("Email")
    return email is None or email == "unavailable"

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
google_search_count = 0
emails_found_count = 0

try:
    for i in range(start_index, len(voice_actors_data)):
        wait_if_paused()

        name = voice_actors_data[i].get("Name", "")
        if not name:
            print(f"❌ No name at index {i}, skipping...")
            continue

        # Check if person needs email search
        if not needs_email_search(voice_actors_data[i]):
            print(f"⏭️ Skipping [{i + 1}/{len(voice_actors_data)}]: {name} - already has email")
            # Still save progress
            with open(progress_path, 'w') as f:
                json.dump({"last_index": i + 1}, f)
            continue

        query = f"@gmail.com {name} voice actor"
        print(f"\n🔍 Searching [{i + 1}/{len(voice_actors_data)}]: {query}")

        try:
            results = list(search(query, num_results=5))
            consecutive_rate_limit_hits = 0
            google_search_count += 1
        except Exception as e:
            if "429" in str(e):
                print("🚨 Google rate-limited. Ending session and saving progress...")
                # Save current state and exit
                with open(voice_actors_path, 'w', encoding='utf-8') as f:
                    json.dump(voice_actors_data, f, ensure_ascii=False, indent=4)
                with open(progress_path, 'w') as f:
                    json.dump({"last_index": i}, f)
                print(f"🎉 Session ended. Processed {google_search_count} searches, found {emails_found_count} emails.")
                cleanup_html_files()
                exit(0)
            else:
                print(f"❌ Google search failed: {e}")
                # Mark as unavailable due to search error
                voice_actors_data[i]['Email'] = "unavailable"
                print("❌ Marked as unavailable due to search error.")
                continue

        time.sleep(random.uniform(3, 10))

        best_email = ""
        max_match_count = 0
        name_words = [w.lower() for w in name.split()]

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
                    print("🚨 Scraping rate-limited. Ending session and saving progress...")
                    # Save current state and exit
                    with open(voice_actors_path, 'w', encoding='utf-8') as f:
                        json.dump(voice_actors_data, f, ensure_ascii=False, indent=4)
                    with open(progress_path, 'w') as f:
                        json.dump({"last_index": i}, f)
                    print(f"🎉 Session ended. Processed {google_search_count} searches, found {emails_found_count} emails.")
                    cleanup_html_files()
                    exit(0)
                else:
                    print(f"❌ Error scraping URL: {e}")
                    continue

            for email in emails:
                local_part = email.split('@')[0].lower()
                match_count = sum(word in local_part for word in name_words)
                if match_count > max_match_count:
                    best_email = email
                    max_match_count = match_count

            time.sleep(random.uniform(1, 3))

        # Update voice_actors.json and final_data.json based on results
        if successful_scrapes == 0 and total_urls > 0:
            voice_actors_data[i]['Email'] = "unavailable"
            print("❌ All URLs failed to scrape. Marked as unavailable.")
        elif best_email:
            voice_actors_data[i]['Email'] = best_email
            emails_found_count += 1
            print(f"✅ Found Email: {best_email}")
            
            # Add complete entry to final_data.json at the top
            complete_entry = voice_actors_data[i].copy()
            final_data.insert(0, complete_entry)  # Insert at the beginning
        else:
            voice_actors_data[i]['Email'] = "unavailable"
            print("❌ No email found. Marked as unavailable for future skips.")

        # Save both files after each entry
        with open(voice_actors_path, 'w', encoding='utf-8') as f:
            json.dump(voice_actors_data, f, ensure_ascii=False, indent=4)
        with open(final_data_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        with open(progress_path, 'w') as f:
            json.dump({"last_index": i + 1}, f)

        # Check if we've reached the search limit
        if google_search_count >= MAX_SEARCHES_BEFORE_RATE_LIMIT:
            print(f"🎯 Reached {MAX_SEARCHES_BEFORE_RATE_LIMIT} searches. Ending session...")
            break

    print(f"\n🎉 Done! Processed {google_search_count} searches, found {emails_found_count} emails.")

except KeyboardInterrupt:
    print("\n⚠️ Script interrupted by user. Saving progress...")
    with open(voice_actors_path, 'w', encoding='utf-8') as f:
        json.dump(voice_actors_data, f, ensure_ascii=False, indent=4)
    with open(progress_path, 'w') as f:
        json.dump({"last_index": i + 1}, f)

finally:
    # Always clean up
    cleanup_html_files()
