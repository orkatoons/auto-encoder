import pandas as pd
from bs4 import BeautifulSoup
import os
import time
import shutil
import json
from datetime import datetime

INPUT_PATH = "C:/Encode Tools/auto-encoder/PTP Scraper/offline PTP pages/Browse Torrents __ PassThePopcorn.htm"
OUTPUT_JSON = "C:/Encode Tools/auto-encoder/PTP Scraper/output.json"
COMPATIBLE_SOURCES = ["BD25", "BD50", "Remux", "DVD5", "DVD9"]

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

                    if "2160p" in source_text:
                        contains_uhd = True
                        break

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
                continue

            if any(source in valid_formats for source in COMPATIBLE_SOURCES):
                high_def = []
                if hd_counts["720p"] == 0:
                    high_def.append("720p")
                if hd_counts["1080p"] == 0:
                    high_def.append("1080p")

                high_def_value = ", ".join(high_def) if high_def else "NULL"

                missing_sd_resolutions = [
                    resolution for resolution in ["480p", "576p"] if resolution not in standard_def_resolutions
                ]
                standard_def_value = ", ".join(missing_sd_resolutions) if missing_sd_resolutions else "NULL"

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

def save_to_json(movies, output_file):
    existing_movies = []
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_movies = json.load(f)
        except Exception as e:
            print(f"Error reading existing JSON file: {e}")
            existing_movies = []

    # Add timestamp to new movies
    for movie in movies:
        movie["date_added"] = current_timestamp

    existing_links = {movie["Link"] for movie in existing_movies}
    new_movies = [movie for movie in movies if movie["Link"] not in existing_links]

    all_movies = existing_movies + new_movies

    # Sort by date_added in descending order (newest first)
    all_movies.sort(key=lambda x: x.get("date_added", ""), reverse=True)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_movies, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(new_movies)} new entries (total: {len(all_movies)}) to '{output_file}'")
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
    html = fetch_content(INPUT_PATH)
    if html:
        movies = parse_movies(html)
        save_to_json(movies, OUTPUT_JSON)
        delete_downloaded_files(os.path.dirname(INPUT_PATH))

if __name__ == "__main__":
    main()
