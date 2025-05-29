import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
import shutil

INPUT_PATH = "C:/Encode Tools/PTP Scraper/offline PTP pages/Browse Torrents __ PassThePopcorn.htm"
GOOGLE_SHEET_NAME = "to encode" 
SHEET_TITLE = "Movies Tab" 
CREDENTIALS_FILE = "C:/Encode Tools/PTP Scraper/code/creds/gen-lang-client-0724418887-959d16f690f0.json" 
COMPATIBLE_SOURCES = ["BD25", "BD50", "Remux", "DVD", "DVD9"]


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
            standard_def_resolutions = []
            hd_counts = {"720p": 0, "1080p": 0}
            trumpable_hd = []

            for torrent_row in torrent_rows:
                torrent_info = torrent_row.find("a", class_="torrent-info-link")
                if torrent_info:
                    source_text = torrent_info.text.strip()

                    if "DVD9" in source_text:
                        if "VOB IFO" in source_text:
                            detected_formats.append("DVD9-VOB IFO")
                        else:
                            continue
                    elif "DVD" in source_text:
                        if "VOB IFO" in source_text:
                            detected_formats.append("DVD-VOB IFO")
                        else:
                            continue

                    if "720p" in source_text:
                        hd_counts["720p"] += 1
                        if "Trumpable" in source_text:
                            trumpable_hd.append("720p (T)")
                    elif "1080p" in source_text:
                        hd_counts["1080p"] += 1
                        if "Trumpable" in source_text:
                            trumpable_hd.append("1080p (T)")

                    if "480p" in source_text:
                        standard_def_resolutions.append("480p")
                    elif "576p" in source_text:
                        standard_def_resolutions.append("576p")

                    for source in COMPATIBLE_SOURCES:
                        if source in source_text and source not in ["DVD", "DVD9"]:
                            detected_formats.append(source)

            if not any(format in detected_formats for format in ["Remux", "BD25", "BD50"]):
                high_def_value = "NULL"
            else:
                high_def = []
                if hd_counts["720p"] == 0:
                    high_def.append("720p")
                if hd_counts["1080p"] == 0:  
                    high_def.append("1080p")
                high_def.extend(trumpable_hd) 
                high_def_value = ", ".join(high_def) if high_def else "NULL"

            missing_sd_resolutions = [
                resolution for resolution in ["480p", "576p"] if resolution not in standard_def_resolutions
            ]
            if missing_sd_resolutions:
                standard_def_value = ", ".join(missing_sd_resolutions)
            else:
                standard_def_value = "NULL"

            if detected_formats and not (standard_def_value == "NULL" and high_def_value == "NULL"):
                movie_link = title_element["href"]
                if not movie_link.startswith("http"):
                    movie_link = f"https://passthepopcorn.me{movie_link}"

                movies.append({
                    "Name": name,
                    "Source": ", ".join(set(detected_formats)), 
                    "Standard Definition": standard_def_value,
                    "High Definition": high_def_value,
                    "Link": movie_link,
                })

        except Exception as e:
            print(f"Error parsing row: {e}")

    return movies


def save_to_google_sheets(movies, spreadsheet_name, sheet_title, credentials_file):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open(spreadsheet_name)

        try:
            sheet = spreadsheet.worksheet(sheet_title)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=sheet_title, rows="100", cols="20")
            sheet.append_row(["Name", "Source", "Standard Definition", "High Definition", "Link"])

        existing_records = sheet.get_all_records()
        if not existing_records:
            sheet.append_row(["Name", "Source", "Standard Definition", "High Definition", "Link"])

        for movie in movies:
            sheet.append_row([
                movie["Name"],
                movie["Source"],
                movie["Standard Definition"],
                movie["High Definition"],
                movie["Link"],
            ])

        print(f"Successfully appended {len(movies)} movies to sheet '{sheet_title}' in Google Sheet '{spreadsheet_name}'")
    except Exception as e:
        print(f"Error saving to Google Sheets: {e}")


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
    print("30 second delay for Google Sheet cooldown")
    time.sleep(30)
    

def main():
    html = fetch_content(INPUT_PATH)
    if html:
        movies = parse_movies(html)
        save_to_google_sheets(movies, spreadsheet_name="to encode", sheet_title="Movies Tab", credentials_file=CREDENTIALS_FILE)
        delete_downloaded_files(os.path.dirname(INPUT_PATH))


if __name__ == "__main__":
    main()
