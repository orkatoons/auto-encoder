import pyautogui
import time
import os
import subprocess
import sys
import pygetwindow as gw
import argparse

def activate_firefox():
    firefox_window = None
    for w in gw.getAllWindows():
        if "Mozilla Firefox" in w.title and not w.isMinimized:
            firefox_window = w
            break
    if not firefox_window:
        print("⚠️ Could not find Firefox window. Please make sure Firefox is open.")
        sys.exit(1)
    firefox_window.activate()
    time.sleep(1)  # Wait for the window to activate

def save_page(delay=3, first_tab=False):
    time.sleep(delay)  
    print("Simulating Ctrl + S...")
    pyautogui.hotkey("ctrl", "s")
    time.sleep(delay)

    if first_tab:
        print("Performing first-tab-specific actions...")
        for _ in range(6):
            pyautogui.press("tab")
        pyautogui.press("enter")
        pyautogui.typewrite("C:\\Encode Tools\\auto-encoder\\PTP Scraper\\offline PTP pages") 
        pyautogui.press("enter")
        for _ in range(9):
            pyautogui.press("tab")
        pyautogui.press("enter")
    else:
        print("Simulating Enter...")
        pyautogui.press("enter")  

    time.sleep(delay)  

def navigate_to_next_tab(tab_number, mode, page_offset):
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

def run_test_script(mode):
    if mode == "Movies":
        script_path = "C:/Encode Tools/auto-encoder/PTP Scraper/code/scrapers/MoviesScraper.py"

    print(f"Running {script_path}...")
    subprocess.run(["python", script_path], check=True)
    print(f"{mode} scraper finished.")

def auto_save_pages(total_pages, save_path, delay, mode, page_offset):
    print("Activating Firefox browser window...")
    activate_firefox()

    for page_number in range(1, total_pages + 1):
        print(f"Navigating to page {page_number}...")
        navigate_to_next_tab(page_number, mode, page_offset) 
        
        print(f"Processing page {page_number}...")
        save_page(delay, first_tab=(page_number == 1))  
        print(f"Page {page_number} saved.")
        
        run_test_script(mode) 
    print("All pages saved successfully!")

def get_last_page_number():
    print("Fetching the last available page number...")
    activate_firefox()
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

    # These hotkeys seem unusual but retained from original code
    pyautogui.hotkey("ctrl","shiftright","shiftleft", "left")

    pyautogui.hotkey("ctrl", "c")
    time.sleep(1)

    activate_firefox()
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    pyautogui.press("enter")

def run_scraper(page_offset, total_pages, mode="Movies"):
    """
    Run the PTP scraper with specified parameters
    
    Args:
        page_offset (int): The page number to start scraping from
        total_pages (int): Number of pages to scrape
        mode (str): Scraping mode (default: "Movies")
    """
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
    return {"status": "success", "message": "Scraping completed successfully"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PTP Scraper')
    parser.add_argument('--page-offset', type=int, required=True, help='Page number to start scraping from')
    parser.add_argument('--total-pages', type=int, required=True, help='Number of pages to scrape')
    parser.add_argument('--mode', type=str, default='Movies', help='Scraping mode (default: Movies)')
    
    args = parser.parse_args()
    
    try:
        run_scraper(args.page_offset, args.total_pages, args.mode)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
