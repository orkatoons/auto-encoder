import time
import os
import json
from datetime import datetime
import pyautogui
import win32gui
import win32con
import win32process
import psutil

class PTPScraper:
    def __init__(self):
        self.data_file = "ptp_data.json"
        self.initialize_data_file()
        self.browser_window = None

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

    def find_firefox_window(self):
        """Find the Firefox window using process name"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'firefox' in proc.info['name'].lower():
                    # Get the window handle for this process
                    def callback(hwnd, pid):
                        if win32gui.IsWindowVisible(hwnd):
                            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if window_pid == pid:
                                self.browser_window = hwnd
                                return False
                        return True
                    
                    win32gui.EnumWindows(callback, proc.info['pid'])
                    if self.browser_window:
                        return self.browser_window
            return None
        except Exception as e:
            print(f"Error finding Firefox window: {str(e)}")
            return None

    def activate_firefox(self):
        """Activate the Firefox window and navigate to PTP"""
        try:
            if not self.browser_window:
                self.find_firefox_window()
            
            if self.browser_window:
                # Verify the window is still valid
                if not win32gui.IsWindow(self.browser_window):
                    print("Window handle invalid, searching for new window...")
                    self.find_firefox_window()
                    if not self.browser_window:
                        raise Exception("Could not find a valid Firefox window")

                win32gui.ShowWindow(self.browser_window, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.browser_window)
                time.sleep(1)
                
                # Navigate to PTP
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.5)
                pyautogui.typewrite("https://passthepopcorn.me/torrents.php")
                pyautogui.press("enter")
                time.sleep(2)  # Wait for page to load
                return True
            return False
        except Exception as e:
            print(f"Error activating Firefox window: {str(e)}")
            return False

    def save_page(self, delay=3, first_tab=False):
        """Save the current page"""
        if not self.activate_firefox():
            raise Exception("Could not find Firefox window")
            
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
        """Navigate to the next page"""
        if not self.activate_firefox():
            raise Exception("Could not find Firefox window")
            
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

    def get_last_page_number(self):
        """Get the last available page number"""
        print("Fetching the last available page number...")
        if not self.activate_firefox():
            raise Exception("Could not find Firefox window")
            
        pyautogui.hotkey("ctrl", "l")
        time.sleep(1)
        pyautogui.typewrite("https://passthepopcorn.me/torrents.php")
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
        
        return 100  # Placeholder value

    def scrape_pages(self, start_page, num_pages):
        """Scrape multiple pages and store unique movies"""
        if not self.activate_firefox():
            raise Exception("Could not find Firefox window. Please ensure Firefox is running.")
            
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

if __name__ == "__main__":
    scraper = PTPScraper()
    print("Welcome to the PTP Scraper!")
    print("This version uses the existing Firefox window and stores data in a local JSON file.")
    
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
