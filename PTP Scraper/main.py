import time
import os
import json
import pyautogui
import win32gui
import win32con
import win32process
import psutil
import subprocess

def find_firefox_window():
    """Find the Firefox window using multiple methods"""
    try:
        # Method 1: Try to find by class name
        hwnd = win32gui.FindWindow("MozillaWindowClass", None)
        if hwnd and win32gui.IsWindowVisible(hwnd):
            print("Found Firefox by class name")
            return hwnd

        # Method 2: Try to find by process
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'firefox' in proc.info['name'].lower():
                print(f"Found Firefox process: {proc.info['name']}")
                # Get the window handle for this process
                def callback(hwnd, pid):
                    if win32gui.IsWindowVisible(hwnd):
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if window_pid == pid:
                            return hwnd
                    return None
                
                hwnd = win32gui.EnumWindows(callback, proc.info['pid'])
                if hwnd:
                    print("Found Firefox window by process")
                    return hwnd

        # Method 3: Try to find by window title
        def find_by_title(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if "firefox" in title or "mozilla" in title:
                    print(f"Found Firefox by title: {title}")
                    return hwnd
            return None

        hwnd = win32gui.EnumWindows(find_by_title, None)
        if hwnd:
            return hwnd

        # Debug: List all visible windows
        print("\nDebug: Listing all visible windows:")
        def list_windows(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only print windows with titles
                    print(f"Window: {title}")
            return True
        win32gui.EnumWindows(list_windows, None)

        print("\nFirefox not found. Please ensure Firefox is running.")
        return None
    except Exception as e:
        print(f"Error finding Firefox window: {str(e)}")
        return None

def activate_firefox():
    """Activate the Firefox window and ensure it's fullscreen"""
    try:
        hwnd = find_firefox_window()
        if not hwnd:
            print("Firefox window not found. Please ensure Firefox is running and visible.")
            return False
        
        # Verify the window is still valid
        if not win32gui.IsWindow(hwnd):
            print("Window handle invalid. Trying to find Firefox again...")
            hwnd = find_firefox_window()
            if not hwnd:
                return False
        
        # Get window title for debugging
        title = win32gui.GetWindowText(hwnd)
        print(f"Activating Firefox window: {title}")
        
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

def ensure_firefox_running():
    """Ensure Firefox is running before proceeding"""
    print("Checking if Firefox is running...")
    if not find_firefox_window():
        print("Firefox not found. Please start Firefox and try again.")
        return False
    return True

def save_page(delay=3, first_tab=False):
    """Save the current page"""
    if not activate_firefox():
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

def navigate_to_next_tab(tab_number, mode, page_offset):
    """Navigate to the next page"""
    if not activate_firefox():
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

def run_test_script(mode):
    if mode == "Movies":
        script_path = "C:/Encode Tools/PTP Scraper/code/scrapers/MoviesScraper.py"

    print(f"Running {script_path}...")
    subprocess.run(["python", script_path], check=True)
    print(f"{mode} scraper finished.")

def auto_save_pages(total_pages, save_path, delay, mode, page_offset):
    print("Switching to the browser...")
    if not activate_firefox():
        raise Exception("Could not find Firefox window")
    time.sleep(delay)

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
    if not activate_firefox():
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
    print("-> Kindly make sure that Firefox is running and visible.")
    print("-> Also ensure that PTP is logged onto in Firefox.")
    print("-> Kindly do not navigate away from the browser window or do any other activity while this program is running.\n")
    
    if not ensure_firefox_running():
        print("Exiting...")
        exit(1)
        
    mode, total_pages, page_offset = get_mode()
    save_path = "C:/Encode Tools/PTP Scraper/offline PTP pages"
    delay = 2
    auto_save_pages(total_pages, save_path, delay, mode, page_offset)
