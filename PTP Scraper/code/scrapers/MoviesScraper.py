import pandas as pd
from bs4 import BeautifulSoup
import os
import time
import shutil
import json
import win32gui
import win32con
import win32process
import psutil
import pyautogui

INPUT_PATH = "C:/Encode Tools/auto-encoder/PTP Scraper/offline PTP pages/Browse Torrents __ PassThePopcorn.htm"
OUTPUT_JSON = "C:/Encode Tools/auto-encoder/PTP Scraper/movies_data.json"
COMPATIBLE_SOURCES = ["BD25", "BD50", "Remux", "DVD5", "DVD9"]

def find_firefox_window():
    """Find the Firefox window using process name"""
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'firefox' in proc.info['name'].lower():
                # Get the window handle for this process
                def callback(hwnd, pid):
                    if win32gui.IsWindowVisible(hwnd):
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if window_pid == pid:
                            return hwnd
                    return None
                
                hwnd = win32gui.EnumWindows(callback, proc.info['pid'])
                if hwnd:
                    return hwnd
        return None
    except Exception as e:
        print(f"Error finding Firefox window: {str(e)}")
        return None

def activate_firefox():
    """Activate the Firefox window and ensure it's fullscreen"""
    try:
        hwnd = find_firefox_window()
        if not hwnd:
            raise Exception("Could not find Firefox window")
        
        # Verify the window is still valid
        if not win32gui.IsWindow(hwnd):
            raise Exception("Window handle invalid")
        
        # Show and activate the window
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(1)
        
        # Maximize the window
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(1)
        
        return True
    except Exception as e:
        print(f"Error activating Firefox window: {str(e)}")
        return False

def fetch_content(input_path):
    try:
        with open(input_path, mode="r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error reading the local HTML file: {e}")
        return None

def parse_movies(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr", class_="basic-movie-list__details-row")

    movies = []

    for row in rows:
        try:
            title_element = row.find("a", class_="basic-movie-list__movie__title")
            title = title_element.text.strip()

            year_element = row.find("span", class_="basic-movie-list__movie__year")
            year = year_element.text.strip() if year_element else "Unknown Year"

            directors_element = row.find("span", class_="basic-movie-list__movie__director-list")
            directors = directors_element.text.replace("by ", "").strip() if directors_element else "Unknown Director"

            name = f"{title} [{year}] by {directors}"
            name = " ".join(name.split())

            torrent_rows = row.find_next_siblings("tr", class_="basic-movie-list__torrent-row")
            detected_formats = []
            valid_formats = []
            standard_def_resolutions = []
            hd_counts = {"720p": 0, "1080p": 0}
            contains_uhd = False

            for torrent_row in torrent_rows:
                torrent_info = torrent_row.find("a", class_="torrent-info-link")
                no_seeders_element = torrent_row.find("td", class_="no-seeders")
                dead_torrent = no_seeders_element is not None

                if torrent_info:
                    source_text = torrent_info.text.strip()

                    # Check for UHD content (2160p)
                    if "2160p" in source_text:
                        contains_uhd = True
                        break  # Skip this movie entirely

                    if "DVD9" in source_text and "VOB IFO" in source_text:
                        format_name = "DVD9 - VOB IFO"
                        if not dead_torrent:
                            valid_formats.append(format_name)
                            detected_formats.append(format_name)
                    elif "DVD" in source_text and "VOB IFO" in source_text:
                        format_name = "DVD5 - VOB IFO"
                        if not dead_torrent:
                            valid_formats.append(format_name)
                            detected_formats.append(format_name)
                    elif "Remux" in source_text:
                        format_name = "Remux"
                        if not dead_torrent:
                            valid_formats.append(format_name)
                            detected_formats.append(format_name)
                    elif "BD25" in source_text:
                        format_name = "BD25"
                        if not dead_torrent:
                            valid_formats.append(format_name)
                            detected_formats.append(format_name)
                    elif "BD50" in source_text:
                        format_name = "BD50"
                        if not dead_torrent:
                            valid_formats.append(format_name)
                            detected_formats.append(format_name)

                    if "720p" in source_text and not dead_torrent:
                        hd_counts["720p"] += 1
                    if "1080p" in source_text and not dead_torrent:
                        hd_counts["1080p"] += 1

                    if "480p" in source_text:
                        standard_def_resolutions.append("480p")
                    if "576p" in source_text:
                        standard_def_resolutions.append("576p")

            if contains_uhd:
                continue  # Skip movies with UHD (2160p) content

            if any(source in valid_formats for source in ["Remux", "BD25", "BD50", "DVD5 - VOB IFO", "DVD9 - VOB IFO"]):
                high_def = []

                # Only include 720p or 1080p if they are missing
                if hd_counts["720p"] == 0:
                    high_def.append("720p")
                if hd_counts["1080p"] == 0:
                    high_def.append("1080p")

                high_def_value = ", ".join(high_def) if high_def else "NULL"

                standard_def_value = "NULL"
                missing_sd_resolutions = [
                    resolution for resolution in ["480p", "576p"] if resolution not in standard_def_resolutions
                ]
                if missing_sd_resolutions:
                    standard_def_value = ", ".join(missing_sd_resolutions)

                movie_link = title_element["href"]
                if not movie_link.startswith("http"):
                    movie_link = f"https://passthepopcorn.me{movie_link}"

                if high_def_value != "NULL" or standard_def_value != "NULL":
                    movies.append({
                        "Name": name,
                        "Source": ", ".join(set(valid_formats)),
                        "Standard Definition": standard_def_value,
                        "High Definition": high_def_value,
                        "Link": movie_link,
                    })

        except Exception as e:
            print(f"Error parsing row: {e}")

    return movies

def save_to_json(movies, json_file):
    """Save movies data to a JSON file"""
    try:
        # Load existing data if file exists
        existing_data = []
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                print("Error reading existing JSON file, starting fresh")
                existing_data = []

        # Add new movies, avoiding duplicates
        new_movies = 0
        for movie in movies:
            if not any(existing.get("Name") == movie["Name"] for existing in existing_data):
                existing_data.append(movie)
                new_movies += 1

        # Save updated data
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        print(f"Successfully saved {new_movies} new movies to {json_file}")
    except Exception as e:
        print(f"Error saving to JSON file: {e}")

def delete_downloaded_files(save_path):
    print("Deleting saved HTML files and associated folders...")
    if os.path.exists(save_path):
        for file_name in os.listdir(save_path):
            file_path = os.path.join(save_path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                print(f"Deleted folder: {file_path}")

def main():
    # First ensure Firefox is active and fullscreen
    if not activate_firefox():
        print("Failed to activate Firefox window. Exiting...")
        return

    html = fetch_content(INPUT_PATH)
    if html:
        movies = parse_movies(html)
        save_to_json(movies, OUTPUT_JSON)
        delete_downloaded_files(os.path.dirname(INPUT_PATH))

if __name__ == "__main__":
    main()
