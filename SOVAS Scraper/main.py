import subprocess
import sys
import time
import os
import json
import requests
from pywinauto.keyboard import send_keys
import shutil

PROGRESS_FILE = "C:/Encode Tools/auto-encoder/SOVAS Scraper/json data/progress1.json"

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

def load_last_page():
    if not os.path.exists(PROGRESS_FILE):
        return 180  # Default
    try:
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("last_page", 180)
    except Exception:
        return 180  # Fallback on error

def save_last_page(last_page):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"last_page": last_page}, f)

def reset_email_progress():
    """Reset email discovery progress to start from beginning for new entries"""
    progress2_path = "C:/Encode Tools/auto-encoder/SOVAS Scraper/json data/progress2.json"
    if os.path.exists(progress2_path):
        try:
            os.remove(progress2_path)
            print("🔄 Reset email discovery progress to process new entries")
        except Exception as e:
            print(f"Warning: Could not reset email progress: {e}")

def cleanup_html_files():
    """Clean up downloaded HTML files after scraping"""
    saved_pages_dir = "C:/Encode Tools/auto-encoder/SOVAS Scraper/saved offline pages"
    if os.path.exists(saved_pages_dir):
        try:
            for item in os.listdir(saved_pages_dir):
                item_path = os.path.join(saved_pages_dir, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                    print(f"🗑️ Deleted: {item}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"🗑️ Deleted directory: {item}")
            print("✅ HTML cleanup completed")
        except Exception as e:
            print(f"Warning: Error during HTML cleanup: {e}")
    else:
        print("ℹ️ No saved pages directory found")

def run_automate(script_path, start_page, num_pages):
    subprocess.run(
        ["python", script_path, str(start_page), str(num_pages)],
        stdout=sys.stdout,
        stderr=subprocess.DEVNULL,
        check=True
    )

def run_automate_with_tracking(script_path, start_page, num_pages, initial_count):
    """Run automate1.py and track new entries after each page"""
    total_new_entries = 0
    
    for page in range(start_page, start_page + num_pages):
        print(f"\n--- Processing page {page} ---")
        
        # Run single page scrape
        subprocess.run(
            ["python", script_path, str(page), "1"],
            stdout=sys.stdout,
            stderr=subprocess.DEVNULL,
            check=True
        )
        
        # Check for new entries after this page
        json_dir = "C:/Encode Tools/auto-encoder/SOVAS Scraper/json data"
        final_data_file = os.path.join(json_dir, "final_data.json")
        
        if os.path.exists(final_data_file):
            try:
                with open(final_data_file, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
                    current_count = len(current_data)
                    new_this_page = current_count - initial_count - total_new_entries
                    if new_this_page > 0:
                        print(f"📊 Page {page}: Found {new_this_page} new voice actors")
                        total_new_entries += new_this_page
                    else:
                        print(f"📊 Page {page}: No new voice actors found")
            except Exception as e:
                print(f"Warning: Could not check data after page {page}: {e}")
    
    return total_new_entries

def initialize_scraper(start_page, num_pages):
    try:
        automate1_path = "C:/Encode Tools/auto-encoder/SOVAS Scraper/automation scripts/automate1.py"
        automate2_path = "C:/Encode Tools/auto-encoder/SOVAS Scraper/automation scripts/automate2.py"
        
        # Check current data count before scraping
        json_dir = "C:/Encode Tools/auto-encoder/SOVAS Scraper/json data"
        final_data_file = os.path.join(json_dir, "final_data.json")
        initial_count = 0
        
        if os.path.exists(final_data_file):
            try:
                with open(final_data_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    initial_count = len(existing_data)
                    print(f"📊 Current database has {initial_count} voice actors")
            except Exception as e:
                print(f"Warning: Could not read existing data: {e}")

        print(f"\nStarting Phase 1 (pages {start_page} to {start_page + num_pages - 1})")
        new_entries = run_automate_with_tracking(automate1_path, start_page, num_pages, initial_count)

        save_last_page(start_page + num_pages)

        time.sleep(0.5)
        send_keys('%{TAB}')

        print("Phase 1 has finished\n")

        # Only run Phase 2 if new entries were found
        if new_entries > 0:
            print(f"🚀 Starting Phase 2 to find emails for {new_entries} new voice actors")
            reset_email_progress()  # Reset progress to process new entries
            run_automate(automate2_path, start_page, num_pages)
            print("automate2.py finished. All automation tasks completed.")
            notify_completion(new_entries)
        else:
            print("✅ No new voice actors found. Skipping Phase 2 (email discovery).")
            notify_completion(0)

        # Clean up HTML files
        cleanup_html_files()

    except Exception as e:
        print(f"Error during SOVAS scraping: {e}")
        # Clean up HTML files even if there's an error
        cleanup_html_files()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        try:
            start_page = int(sys.argv[1])
            num_pages = int(sys.argv[2])
            initialize_scraper(start_page, num_pages)
        except ValueError:
            print("Invalid input. Please enter numeric values for start_page and num_pages.")
            sys.exit(1)
    else:
        print("Usage: python main.py <start_page> <num_pages>")
        sys.exit(1)
