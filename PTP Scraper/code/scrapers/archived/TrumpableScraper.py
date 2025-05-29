import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import shutil
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

INPUT_PATH = "C:/Encode Tools/PTP Scraper/offline PTP pages/Trumpable __ PassThePopcorn.htm"
FILTER_CRITERIA = ["Remux", "BD", "DVD", "DVD9"]
GOOGLE_SHEET_NAME = "to encode"  
CREDENTIALS_FILE = "C:/Encode Tools/PTP Scraper/code/creds/gen-lang-client-0724418887-959d16f690f0.json" 

def fetch_content(input_path):
    if os.path.exists(input_path):
        try:
            with open(input_path, mode="r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            print(f"Error reading the local HTML file: {e}")
            return None
    else:
        try:
            response = requests.get(input_path)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching the webpage: {e}")
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

            authors = row.find_all("a", class_="artist-info-link")
            author_names = ", ".join([author.text.strip() for author in authors])

            movie_name = f"{title} {year} by {author_names}"

            movie_link_element = row.find("a", class_="basic-movie-list__movie__title")
            movie_link = movie_link_element["href"] if movie_link_element else "N/A"

            resolution_element = row.find("a", class_="torrent-info-link")
            resolution_text = resolution_element.text.strip() if resolution_element else ""

            sources = [part.strip() for part in resolution_text.split("/") if part.strip()]

            if "DVD" in sources and "VOB IFO" in resolution_text:
                sources = [source if source != "DVD" else "DVD-VOB IFO" for source in sources]

            if "DVD" in sources and "VOB IFO" not in resolution_text:
                continue 

            filtered_sources = [source for source in sources if any(criteria in source for criteria in FILTER_CRITERIA)]
            resolution_cleaned = ", ".join(filtered_sources)

            if not resolution_cleaned:
                continue

            movies.append({"Movie": movie_name, "Link": movie_link, "Resolution": resolution_cleaned})
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
            sheet.append_row(["Movie", "Source", "Link"])

        existing_records = sheet.get_all_records()
        if not existing_records:
            sheet.append_row(["Movie", "Source", "Link"])

        for movie in movies:
            cleaned_movie_name = " ".join(movie["Movie"].split())
            sheet.append_row([cleaned_movie_name, movie["Resolution"], movie["Link"]])

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
        save_to_google_sheets(movies, spreadsheet_name="to encode", sheet_title="Trumpable Tab", credentials_file=CREDENTIALS_FILE)
        delete_downloaded_files(os.path.dirname(INPUT_PATH))

if __name__ == "__main__":
    main()
