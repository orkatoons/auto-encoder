import time
import pyperclip
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse, urlunparse
import os
import shutil
import json
from pywinauto.keyboard import send_keys

# Base directories
base_dir = "C:\\Encode Tools\\auto-encoder\\SOVAS Scraper"
saved_pages_dir = os.path.join(base_dir, "saved offline pages")
json_dir = os.path.join(base_dir, "json data")
html_file_path = os.path.join(saved_pages_dir, "Voice123 _ Find voice actors for your project.htm")

# Ensure output directory exists
os.makedirs(json_dir, exist_ok=True)
json_file = os.path.join(json_dir, "voice_actors.json")

# === Step 1: Copy content using pywinauto ===
time.sleep(2)  # Small delay to switch to browser manually  
send_keys("^a")  # Ctrl+A
time.sleep(0.5)
send_keys("^c")  # Ctrl+C
time.sleep(1)

# === Step 2: Extract Names from clipboard ===
clipboard_text = pyperclip.paste()
lines = clipboard_text.splitlines()

names = []
for i in range(69, 121, 3):  # Adjust line range if needed
    if i < len(lines):
        names.append(lines[i].strip())
    else:
        break

# === Step 3: Extract profile links from saved HTML ===
with open(html_file_path, 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

cards = soup.find_all("div", class_="md-card md-theme provider-card")

profiles = []
for card in cards:
    a_tag = card.find("a", class_="profile-anchor")
    if a_tag:
        full_url = a_tag.get("href")
        parsed_url = urlparse(full_url)
        clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
        profiles.append(clean_url)

# === Step 4: Combine names and profiles ===
combined_data = [
    {
        "Name": name,
        "Email": None,  # Placeholder for now
        "Work Samples": profiles[i] if i < len(profiles) else "",
        "Source": "voices123.com",
        "Phone No": None,
        "Job Title": "Voice Actor",
        "Company": None,
        "Industry": "voice acting"
    }
    for i, name in enumerate(names)
]

# === Step 5: Load existing JSON and avoid duplicates ===
existing_data = []
if os.path.exists(json_file):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except Exception as e:
        print(f"Error loading existing JSON: {e}")

# Create a set of existing names (case-insensitive) for faster lookup
existing_names = {entry["Name"].lower().strip() for entry in existing_data}

# Filter out duplicates based on name only (case-insensitive)
new_data = []
duplicate_count = 0
for entry in combined_data:
    name_lower = entry["Name"].lower().strip()
    if name_lower not in existing_names:
        new_data.append(entry)
        existing_names.add(name_lower)  # Add to set to prevent duplicates within new data
    else:
        duplicate_count += 1

# Merge existing data with new data
final_data = existing_data + new_data

# Additional safety check: remove any remaining duplicates in final_data
seen_names = set()
deduped_final_data = []
for entry in final_data:
    name_lower = entry["Name"].lower().strip()
    if name_lower not in seen_names:
        deduped_final_data.append(entry)
        seen_names.add(name_lower)
    else:
        print(f"⚠️ Removed duplicate: {entry['Name']}")

try:
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(deduped_final_data, f, indent=4, ensure_ascii=False)
    print(f"✅ Saved {len(new_data)} new entries, skipped {duplicate_count} duplicates (total: {len(deduped_final_data)}) to '{json_file}'")
except Exception as e:
    print(f"Error writing to JSON: {e}")

# === Step 6: Clean saved HTML folder ===
if os.path.exists(saved_pages_dir):
    for item in os.listdir(saved_pages_dir):
        item_path = os.path.join(saved_pages_dir, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"Failed to delete {item_path}. Reason: {e}")
