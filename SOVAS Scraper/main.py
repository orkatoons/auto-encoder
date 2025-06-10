import subprocess
import sys
import time
import os
import json
import contextlib

PROGRESS_FILE = "C:/Encode Tools/auto-encoder/SOVAS Scraper/json data/progress1.json"

def import_pyautogui_safely():
    with open(os.devnull, 'w') as devnull, contextlib.redirect_stderr(devnull):
        import pyautogui
    return pyautogui

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

def run_automate(script_path, start_page, num_pages):
    subprocess.run(
        ["python", script_path, str(start_page), str(num_pages)],
        stdout=sys.stdout,
        stderr=subprocess.DEVNULL,
        check=True
    )

if __name__ == "__main__":
    try:
        print("\nWelcome to the Sovas Scraper!\n")
        print("Please review these important instructions before we begin:")
        print("1.) The scraper runs in two phases:")
        print("   - Phase 1: Scrapes profiles from Voices123.com")
        print("   - Phase 2: Uses Google Search to find associated emails")
        print("2.) During Phase 1, ensure that only Firefox and this Command Prompt window are open, and do not switch away from them.")
        print("3.) Phase 2 runs in the background, so once it starts, you may navigate away from this window — but please DO NOT close it.")
        print("4.) Make sure you are logged into Voices123.com before starting.\n")

        suggested_start = load_last_page()
        start_page_input = input(f"Page to start from [default: {suggested_start}]: ").strip()
        start_page = int(start_page_input) if start_page_input else suggested_start

        num_pages = int(input("Enter the number of pages to scrape: "))
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        exit(1)

    automate1_path = "C:/Encode Tools/auto-encoder/SOVAS Scraper/automation scripts/automate1.py"
    automate2_path = "C:/Encode Tools/auto-encoder/SOVAS Scraper/automation scripts/automate2.py"

    print(f"\nStarting Phase 1 (pages {start_page} to {start_page + num_pages - 1})")
    run_automate(automate1_path, start_page, num_pages)

    # Update progress
    save_last_page(start_page + num_pages)

    pyautogui = import_pyautogui_safely()
    time.sleep(0.5)
    pyautogui.hotkey('alt', 'tab')

    print("Phase 1 has finished\n")

    print("Starting Phase 2")
    run_automate(automate2_path, start_page, num_pages)

    print("automate2.py finished. All automation tasks completed.")
