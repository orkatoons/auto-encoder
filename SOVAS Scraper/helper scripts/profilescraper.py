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
final_data_file = os.path.join(json_dir, "final_data.json")

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
existing_final_data = []

# Load from voice_actors.json if it exists
if os.path.exists(json_file):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except Exception as e:
        print(f"Error loading existing JSON: {e}")

# Load from final_data.json if it exists (for resuming)
if os.path.exists(final_data_file):
    try:
        with open(final_data_file, "r", encoding="utf-8") as f:
            existing_final_data = json.load(f)
        print(f"📂 Found existing final_data.json with {len(existing_final_data)} entries")
    except Exception as e:
        print(f"Error loading final_data.json: {e}")

# Combine existing data from both sources for deduplication
all_existing_entries = {(entry["Name"].lower(), entry["Work Samples"].lower()) for entry in existing_data}
all_existing_entries.update({(entry["Name"].lower(), entry["Work Samples"].lower()) for entry in existing_final_data})

# Deduplicate based on both Name and Profile (case-insensitive)
new_data = [
    entry for entry in combined_data 
    if (entry["Name"].lower(), entry["Work Samples"].lower()) not in all_existing_entries
]

# Merge with final_data.json if it exists, otherwise use voice_actors.json
if existing_final_data:
    final_data = existing_final_data + new_data
    output_file = final_data_file
    print(f"📂 Merging with existing final_data.json")
else:
    final_data = existing_data + new_data
    output_file = json_file

# Remove duplicates in final_data just in case
seen = set()
deduped_final_data = []
for entry in final_data:
    key = (entry["Name"].lower(), entry["Work Samples"].lower())
    if key not in seen:
        deduped_final_data.append(entry)
        seen.add(key)

try:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deduped_final_data, f, indent=4, ensure_ascii=False)
    print(f"Saved {len(new_data)} new entries (total: {len(deduped_final_data)}) to '{output_file}'")
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
