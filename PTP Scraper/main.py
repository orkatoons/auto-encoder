import pyautogui
import time
import os
import json
from datetime import datetime

class PTPScraper:
    def __init__(self):
        self.data_file = "ptp_data.json"
        self.initialize_data_file()

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

    def save_page(self, delay=3, first_tab=False):
        time.sleep(delay)  
        print("Simulating Ctrl + S...")
        pyautogui.hotkey("ctrl", "s")
        time.sleep(delay)

        if first_tab:
            print("Performing first-tab-specific actions...")
            for _ in range(6):
                pyautogui.press("tab")
            pyautogui.press("enter")
            pyautogui.typewrite("C:\\Encode Tools\\PTP Scraper\\offline PTP pages") 
            pyautogui.press("enter")
            for _ in range(9):
                pyautogui.press("tab")
            pyautogui.press("enter")
        else:
            print("Simulating Enter...")
            pyautogui.press("enter")  

        time.sleep(delay)  

    def navigate_to_next_tab(self, tab_number, mode, page_offset):
        print("Navigating to the desired page...")
        pyautogui.hotkey("ctrl", "l")
        time.sleep(1) 

        if tab_number == 1:
            if mode == "Movies":
                pyautogui.typewrite(f"https://passthepopcorn.me/torrents.php?page={page_offset}")
            pyautogui.press("enter")
        else:
            pyautogui.press("right")
            pyautogui.press("backspace")
            pyautogui.typewrite(str(page_offset + tab_number - 1))
            pyautogui.press("space")
            pyautogui.press("enter")

    def process_saved_page(self, page_number):
        """Process the saved page and extract movie data"""
        # This is where you would implement the actual page processing logic
        # For now, we'll return a mock movie entry
        return {
            "title": f"Movie from page {page_number}",
            "year": 2024,
            "quality": "1080p",
            "size": "10GB",
            "upload_date": datetime.now().isoformat(),
            "scraped_at": datetime.now().isoformat()
        }

    def scrape_pages(self, start_page, num_pages):
        """Scrape multiple pages and store unique movies"""
        print("Switching to the browser...")
        pyautogui.hotkey("alt", "tab")
        time.sleep(2)

        existing_data = self.load_existing_data()
        new_movies = []

        for page_number in range(1, num_pages + 1):
            print(f"Navigating to page {page_number}...")
            self.navigate_to_next_tab(page_number, "Movies", start_page)
            
            print(f"Processing page {page_number}...")
            self.save_page(2, first_tab=(page_number == 1))
            
            # Process the saved page and get movie data
            movie_data = self.process_saved_page(page_number)
            
            # Check for duplicates and add if new
            if not self.is_duplicate(movie_data, existing_data):
                new_movies.append(movie_data)
                existing_data["movies"].append(movie_data)
            
            # Save after each page to prevent data loss
            self.save_data(existing_data)
            
        return len(new_movies)

    def get_last_page_number(self):
        print("Fetching the last available page number...")
        pyautogui.hotkey("alt", "tab")
        time.sleep(1)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(1)
        pyautogui.typewrite(f"https://passthepopcorn.me/torrents.php")
        pyautogui.press("enter")
        time.sleep(3)   
        for _ in range(28):
            pyautogui.press("tab")
        pyautogui.press("enter")
        time.sleep(1)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(1)
        pyautogui.press("right")

        pyautogui.hotkey("ctrl","shiftright","shiftleft", "left")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(1)
        pyautogui.hotkey("alt", "tab")
        time.sleep(1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")
        
        # Return the last page number (you'll need to implement this)
        return 100  # Placeholder value

def open_google_sheet():
    print("Opening Google Sheet...")
    pyautogui.hotkey("ctrl", "t")  # Open a new tab
    time.sleep(1)
    pyautogui.typewrite("https://docs.google.com/spreadsheets/d/1YrbR0725cmF6AGcvYFBYh11nES3ZEpGgumbuZ5nZRHw/edit?usp=sharing")
    pyautogui.press("enter")

def get_mode():
    mode = "Movies"
    total_pages = 1
    page_offset = 1

    while True:
        page_offset1 = int(input("Which page would you like to start at: "))
        if page_offset1 <= 0 or page_offset1 != int(page_offset1):
            print("Invalid number.")
        else:
            page_offset = page_offset1
            break

    while True:
        total_pages1 = input("Enter the number of pages you wish to be scraped ('All' to get the last page): ").strip().lower()
        
        if total_pages1 == "all":
            get_last_page_number()
            while True:
                try:
                    total_pages1 = int(input("Scrape how many pages from the last page?: "))
                    if total_pages1 <= 0:
                        print("Invalid number. Enter a positive integer.")
                    else:
                        total_pages = total_pages1
                        break
                except ValueError:
                    print("Invalid input. Please enter a valid number.")
            break

        try:
            total_pages1 = int(total_pages1)
            if total_pages1 <= 0:
                print("Invalid amount.")
            else:
                total_pages = total_pages1
                break
        except ValueError:
            print("Invalid input. Enter a number or 'All'.")

    return mode, total_pages, page_offset

if __name__ == "__main__":
    print("Welcome to the PTP Scraper!\n")
    print("-> Kindly make sure that this terminal and a browser are the only applications open on this desktop. ")
    print("-> Also ensure that PTP is logged onto on your browser.")
    print("-> Kindly do not navigate away from the browser window or do any other activity while this program is running.\n")
    mode, total_pages, page_offset = get_mode()
    save_path = "C:/Encode Tools/PTP Scraper/offline PTP pages"
    delay = 2
    auto_save_pages(total_pages, save_path, delay, mode, page_offset)
    open_google_sheet()
