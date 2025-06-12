import time
import os
import subprocess
import sys
import requests
from datetime import datetime
import json
from pywinauto import Desktop, keyboard

def notify_completion(parsed_count):
    try:
        payload = {
            "message": f"PTP scraping completed successfully! Parsed {parsed_count} movies."
        }
        response = requests.post('http://geekyandbrain.ddns.net:3030/api/ptp/scrape/complete', json=payload)
        if response.status_code != 200:
            print(f"Warning: Failed to notify completion: {response.status_code}")
    except Exception as e:
        print(f"Warning: Error notifying completion: {str(e)}")


def activate_firefox():
    try:
        firefox = next((w for w in Desktop(backend="uia").windows() if "firefox" in w.window_text().lower() and w.is_visible()), None)
        if firefox:
            firefox.set_focus()
            time.sleep(1)
        else:
            print("Could not find Firefox window. Please make sure Firefox is open.")
            sys.exit(1)
    except Exception as e:
        print(f"Error activating Firefox: {e}")
        sys.exit(1)

def save_page(delay=3, first_tab=False):
    time.sleep(delay)
    print("Simulating Ctrl+S...")
    keyboard.send_keys("^s")  # Ctrl+S to open Save dialog
    time.sleep(2)

    if first_tab:
        print("Performing first-tab-specific actions...")
        for i in range(6):
            keyboard.send_keys("{TAB}")
            time.sleep(0.5)
        keyboard.send_keys("{ENTER}")
        time.sleep(1)
        keyboard.send_keys("C:\\Encode{SPACE}Tools\\auto-encoder\\PTP{SPACE}Scraper\\offline{SPACE}PTP{SPACE}pages")
        time.sleep(0.5)
        keyboard.send_keys("{ENTER}")
        time.sleep(1)
        for _ in range(8):
            keyboard.send_keys("{TAB}")
            time.sleep(0.2)
        time.sleep(0.5)
        keyboard.send_keys("{ENTER}")
        time.sleep(2)
    else:
        print("Simulating Enter to save...")
        time.sleep(1)
        keyboard.send_keys("{ENTER}")
        time.sleep(2)

    time.sleep(delay)

def navigate_to_next_tab(tab_number, mode, page_offset):
    print("Navigating to the desired page...")
    keyboard.send_keys("^l")  # Focus address bar
    time.sleep(1)

    if tab_number == 1:
        if mode == "Movies":
            keyboard.send_keys(f"https://passthepopcorn.me/torrents.php?page={page_offset}")
        keyboard.send_keys("{ENTER}")
    else:
        keyboard.send_keys("{RIGHT}")
        digits_to_erase = len(str(page_offset + tab_number - 2))  # previous number
        keyboard.send_keys("{BACKSPACE}" * digits_to_erase)
        keyboard.send_keys(str(page_offset + tab_number - 1))
        keyboard.send_keys(" {ENTER}")



def run_test_script(mode):
    if mode == "Movies":
        script_path = "C:/Encode Tools/auto-encoder/PTP Scraper/code/scrapers/MoviesScraper.py"
    print(f"Running {script_path}...")
    result = subprocess.run(["python", script_path], capture_output=True, text=True, check=True)
    output = result.stdout

    # Try extracting the count from the output
    total_parsed = 0
    for line in output.splitlines():
        if line.startswith("Total parsed movies:"):
            try:
                total_parsed = int(line.split(":")[1].strip())
            except ValueError:
                pass

    print(f"{mode} scraper finished. Parsed {total_parsed} movies.")
    return total_parsed



def auto_save_pages(total_pages, save_path, delay, mode, page_offset):
    print("Activating Firefox browser window...")
    activate_firefox()

    total_parsed = 0

    try:
        for page_number in range(1, total_pages + 1):
            print(f"Navigating to page {page_number}...")
            navigate_to_next_tab(page_number, mode, page_offset)

            print(f"Processing page {page_number}...")
            save_page(delay, first_tab=(page_number == 1))
            print(f"Page {page_number} saved.")

            parsed_this_round = run_test_script(mode)
            total_parsed += parsed_this_round

        print("All pages saved successfully!")
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        sys.exit(1)

    notify_completion(total_parsed)



def get_last_page_number():
    print("Fetching the last available page number...")
    activate_firefox()
    keyboard.send_keys("^l")
    time.sleep(1)
    keyboard.send_keys("https://passthepopcorn.me/torrents.php")
    keyboard.send_keys("{ENTER}")
    time.sleep(3)

    for _ in range(28):
        keyboard.send_keys("{TAB}")
    keyboard.send_keys("{ENTER}")
    time.sleep(1)

    keyboard.send_keys("^l")
    time.sleep(1)
    keyboard.send_keys("{RIGHT}")
    keyboard.send_keys("^c")  # Copy current URL
    time.sleep(1)

    activate_firefox()
    keyboard.send_keys("^v")
    time.sleep(1)
    keyboard.send_keys("{ENTER}")

def initialize_scraper(page_offset, total_pages, mode="Movies"):
    if page_offset <= 0:
        raise ValueError("Page offset must be greater than 0")
    if total_pages <= 0:
        raise ValueError("Total pages must be greater than 0")

    save_path = "C:/Encode Tools/auto-encoder/PTP Scraper/offline PTP pages"
    delay = 2

    print(f"Starting scraper with parameters:")
    print(f"- Mode: {mode}")
    print(f"- Page offset: {page_offset}")
    print(f"- Total pages: {total_pages}")

    auto_save_pages(total_pages, save_path, delay, mode, page_offset)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        page_offset = int(sys.argv[1])
        total_pages = int(sys.argv[2])
        mode = sys.argv[3] if len(sys.argv) > 3 else "Movies"
        initialize_scraper(page_offset, total_pages, mode)
    else:
        print("Please provide page_offset and total_pages as arguments")
        sys.exit(1)
