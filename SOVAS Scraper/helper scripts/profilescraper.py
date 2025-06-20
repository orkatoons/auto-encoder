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

print(f"🔍 DEBUG: Clipboard has {len(lines)} lines")
print(f"🔍 DEBUG: Extracting names from lines 69-121 (every 3rd line)")

names = []
for i in range(69, 121, 3):  # Adjust line range if needed
    if i < len(lines):
        name = lines[i].strip()
        names.append(name)
        print(f"   - Line {i}: '{name}'")
    else:
        print(f"   - Line {i}: Index out of range")
        break

print(f"🔍 DEBUG: Extracted {len(names)} names")

# === Step 3: Extract profile links from saved HTML ===
print(f"🔍 DEBUG: Reading HTML file: {html_file_path}")
print(f"🔍 DEBUG: HTML file exists: {os.path.exists(html_file_path)}")

with open(html_file_path, 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

cards = soup.find_all("div", class_="md-card md-theme provider-card")
print(f"🔍 DEBUG: Found {len(cards)} profile cards in HTML")

profiles = []
for i, card in enumerate(cards):
    a_tag = card.find("a", class_="profile-anchor")
    if a_tag:
        full_url = a_tag.get("href")
        parsed_url = urlparse(full_url)
        clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
        profiles.append(clean_url)
        print(f"   - Card {i+1}: {clean_url}")
    else:
        print(f"   - Card {i+1}: No profile anchor found")

print(f"🔍 DEBUG: Extracted {len(profiles)} profile URLs")

# === Step 4: Combine names and profiles ===
print(f"🔍 DEBUG: Combining {len(names)} names with {len(profiles)} profiles")

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

print(f"🔍 DEBUG: Created {len(combined_data)} combined entries")
for i, entry in enumerate(combined_data[:3]):  # Show first 3 entries
    print(f"   - Entry {i+1}: {entry['Name']} -> {entry['Work Samples']}")

# === Step 5: Load existing JSON and avoid duplicates ===
existing_data = []
existing_final_data = []

print(f"🔍 DEBUG: Loading existing data...")

# Load from voice_actors.json if it exists
if os.path.exists(json_file):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        print(f"🔍 DEBUG: Loaded {len(existing_data)} entries from voice_actors.json")
    except Exception as e:
        print(f"Error loading existing JSON: {e}")

# Load from final_data.json if it exists (for resuming)
if os.path.exists(final_data_file):
    try:
        with open(final_data_file, "r", encoding="utf-8") as f:
            existing_final_data = json.load(f)
        print(f"🔍 DEBUG: Loaded {len(existing_final_data)} entries from final_data.json")
    except Exception as e:
        print(f"Error loading final_data.json: {e}")
        existing_final_data = []

print(f"🔍 DEBUG: Data loading complete. Starting deduplication...")
print(f"🔍 DEBUG: About to start deduplication process...")

try:
    # Combine existing data from both sources for deduplication
    all_existing_entries = set()
    
    # Process existing_data with null checks - only require Name
    for entry in existing_data:
        name = entry.get("Name", "")
        if name:  # Only require name to be present
            work_samples = entry.get("Work Samples", "")
            key = (name.lower(), work_samples.lower() if work_samples else "")
            all_existing_entries.add(key)
    
    # Process existing_final_data with null checks - only require Name
    for entry in existing_final_data:
        name = entry.get("Name", "")
        if name:  # Only require name to be present
            work_samples = entry.get("Work Samples", "")
            key = (name.lower(), work_samples.lower() if work_samples else "")
            all_existing_entries.add(key)

    print(f"🔍 DEBUG: Total existing entries for deduplication: {len(all_existing_entries)}")

    # Show some sample existing entries for debugging
    print(f"🔍 DEBUG: Sample existing entries (first 5):")
    sample_count = 0
    for entry in existing_final_data[:5]:
        name = entry.get("Name", "")
        work_samples = entry.get("Work Samples", "")
        if name:
            key = (name.lower(), work_samples.lower() if work_samples else "")
            print(f"   - '{name}' -> '{work_samples}' (key: {key})")
            sample_count += 1
            if sample_count >= 5:
                break

    # Deduplicate based on Name (primary) and Work Samples (secondary)
    new_data = []
    duplicate_count = 0

    print(f"🔍 DEBUG: Checking each entry for duplicates...")

    for entry in combined_data:
        name = entry.get("Name", "")
        work_samples = entry.get("Work Samples", "")
        
        if name:  # Only require name to be present
            key = (name.lower(), work_samples.lower() if work_samples else "")
            print(f"🔍 DEBUG: Checking entry: '{name}' -> '{work_samples}'")
            print(f"🔍 DEBUG: Key: {key}")
            
            if key not in all_existing_entries:
                new_data.append(entry)
                print(f"   ✅ NEW: {name}")
            else:
                duplicate_count += 1
                print(f"   ❌ DUPLICATE: {name} (key found in existing data)")
        else:
            print(f"🔍 DEBUG: Skipping entry with missing name: '{name}' -> '{work_samples}'")

    print(f"🔍 DEBUG: Found {len(new_data)} new entries, {duplicate_count} duplicates")

    # Merge with final_data.json if it exists, otherwise use voice_actors.json
    if existing_final_data:
        final_data = existing_final_data + new_data
        output_file = final_data_file
        print(f"🔍 DEBUG: Merging with existing final_data.json")
    else:
        final_data = existing_data + new_data
        output_file = json_file
        print(f"🔍 DEBUG: Using voice_actors.json")

    print(f"🔍 DEBUG: Final data count before deduplication: {len(final_data)}")

    # Remove duplicates in final_data just in case
    seen = set()
    deduped_final_data = []
    for entry in final_data:
        name = entry.get("Name", "")
        work_samples = entry.get("Work Samples", "")
        if name:  # Only require name to be present
            key = (name.lower(), work_samples.lower() if work_samples else "")
            if key not in seen:
                deduped_final_data.append(entry)
                seen.add(key)
        else:
            # Skip entries with missing name
            print(f"🔍 DEBUG: Skipping entry with missing name in final dedup: '{name}' -> '{work_samples}'")

    print(f"🔍 DEBUG: Final data count after deduplication: {len(deduped_final_data)}")
    print(f"🔍 DEBUG: Saving to: {output_file}")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(deduped_final_data, f, indent=4, ensure_ascii=False)
        print(f"🔍 DEBUG: Successfully saved {len(new_data)} new entries (total: {len(deduped_final_data)}) to '{output_file}'")
    except Exception as e:
        print(f"Error writing to JSON: {e}")

except Exception as e:
    print(f"🔍 DEBUG: ERROR in deduplication process: {e}")
    import traceback
    traceback.print_exc()

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
