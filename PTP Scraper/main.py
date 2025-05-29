import time
import os
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options

class PTPScraper:
    def __init__(self):
        self.data_file = "ptp_data.json"
        self.initialize_data_file()
        self.driver = None

    def initialize_data_file(self):
        """Initialize the JSON data file if it doesn't exist"""
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({"movies": []}, f)

    def load_existing_data(self):
        """Load existing data from the JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"movies": []}

    def save_data(self, data):
        """Save data to the JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def is_duplicate(self, movie_data, existing_data):
        """Check if a movie is already in the database"""
        for movie in existing_data["movies"]:
            if (movie.get("title") == movie_data.get("title") and 
                movie.get("year") == movie_data.get("year")):
                return True
        return False

    def setup_driver(self):
        """Set up the Selenium WebDriver for Firefox"""
        options = Options()
        options.add_argument('--start-maximized')
        self.driver = webdriver.Firefox(options=options)
        self.driver.get("https://passthepopcorn.me/torrents.php")
        time.sleep(2)  # Wait for page to load

    def process_page(self, page_number):
        """Process the current page and extract movie data"""
        try:
            # Wait for the movie list to be visible
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "torrent_table"))
            )

            # Get all movie rows
            movie_rows = self.driver.find_elements(By.CSS_SELECTOR, ".torrent_table tr:not(:first-child)")
            movies = []

            for row in movie_rows:
                try:
                    # Extract movie information
                    title_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
                    title = title_element.text
                    
                    # Extract year from title (assuming format "Movie Title (Year)")
                    year = None
                    if "(" in title and ")" in title:
                        year = title.split("(")[-1].split(")")[0]
                        title = title.split("(")[0].strip()

                    # Get quality and size
                    quality = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text
                    size = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)").text

                    movie_data = {
                        "title": title,
                        "year": year,
                        "quality": quality,
                        "size": size,
                        "upload_date": datetime.now().isoformat(),
                        "scraped_at": datetime.now().isoformat()
                    }
                    movies.append(movie_data)
                except Exception as e:
                    print(f"Error processing movie row: {str(e)}")
                    continue

            return movies
        except TimeoutException:
            print(f"Timeout waiting for page {page_number} to load")
            return []
        except Exception as e:
            print(f"Error processing page {page_number}: {str(e)}")
            return []

    def navigate_to_page(self, page_number):
        """Navigate to a specific page"""
        try:
            self.driver.get(f"https://passthepopcorn.me/torrents.php?page={page_number}")
            time.sleep(2)  # Wait for page to load
            return True
        except Exception as e:
            print(f"Error navigating to page {page_number}: {str(e)}")
            return False

    def get_last_page_number(self):
        """Get the last available page number"""
        try:
            self.driver.get("https://passthepopcorn.me/torrents.php")
            time.sleep(2)
            
            # Find the last page number
            pagination = self.driver.find_elements(By.CSS_SELECTOR, ".pagination a")
            if pagination:
                last_page = int(pagination[-2].text)  # Second to last element is usually the last page number
                return last_page
            return 1
        except Exception as e:
            print(f"Error getting last page number: {str(e)}")
            return 1

    def scrape_pages(self, start_page, num_pages):
        """Scrape multiple pages and store unique movies"""
        try:
            self.setup_driver()
            existing_data = self.load_existing_data()
            new_movies = []

            for page_number in range(start_page, start_page + num_pages):
                print(f"Processing page {page_number}...")
                if not self.navigate_to_page(page_number):
                    continue

                movies = self.process_page(page_number)
                for movie in movies:
                    if not self.is_duplicate(movie, existing_data):
                        new_movies.append(movie)
                        existing_data["movies"].append(movie)

                # Save after each page to prevent data loss
                self.save_data(existing_data)
                print(f"Page {page_number} processed. Found {len(movies)} movies, {len(new_movies)} new.")

            return len(new_movies)
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    scraper = PTPScraper()
    print("Welcome to the PTP Scraper!")
    print("This version uses Selenium with Firefox and stores data in a local JSON file.")
    
    while True:
        try:
            start_page = int(input("Which page would you like to start at? "))
            if start_page <= 0:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    while True:
        try:
            num_pages = int(input("How many pages would you like to scrape? "))
            if num_pages <= 0:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    print(f"\nStarting scrape from page {start_page} for {num_pages} pages...")
    new_movies = scraper.scrape_pages(start_page, num_pages)
    print(f"\nScraping complete! Added {new_movies} new unique movies to the database.")
