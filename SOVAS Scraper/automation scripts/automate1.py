import pyautogui
import time
import subprocess
import sys
import pygetwindow as gw

# Get start page and number of pages from command-line arguments
try:
    start_page = int(sys.argv[1])
    num_pages = int(sys.argv[2])
except (IndexError, ValueError):
    print("Usage: python automate1.py <start_page> <num_pages>")
    sys.exit(1)

save_dir = "C:\\Encode Tools\\auto-encoder\\SOVAS Scraper\\saved offline pages"

# Detect and activate Firefox window
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

# Main scraping loop
for page in range(start_page, start_page + num_pages):
    # Focus the address bar (Ctrl+L)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.5)

    # Type the URL with the current page number
    url = f"https://voice123.com/search?languages=1018&sort_by=top_reviewed_score&page={page}"
    pyautogui.typewrite(url)
    time.sleep(0.5)

    # Press Enter to navigate to the URL
    pyautogui.press('enter')
    time.sleep(5)  # Wait for the page to load

    # Save the page (Ctrl+S)
    pyautogui.hotkey('ctrl', 's')
    time.sleep(1)

    if page == start_page:
        # Tab 6 times to reach folder input
        for _ in range(6):
            pyautogui.press('tab')
            time.sleep(0.1)

        pyautogui.press('enter')  # Activate folder field
        time.sleep(0.5)

        pyautogui.typewrite(save_dir)  # Type the save directory
        time.sleep(0.5)

        pyautogui.press('enter')  # Confirm folder

        # Tab 7 times to reach Save button (Windows)
        for _ in range(7):
            pyautogui.press('tab')
            time.sleep(0.2)

        pyautogui.press('enter')  # Press Save
        time.sleep(1)
    else:
        # Just press Enter to save directly on subsequent pages
        pyautogui.press('enter')
        time.sleep(1)

    # Wait for save to complete
    time.sleep(5)

    # Run the profile scraper
    subprocess.run(
        ["python", "profilescraper.py"],
        cwd="C:/Encode Tools/auto-encoder/SOVAS Scraper/helper scripts"
    )

    time.sleep(2)  # Pause before next iteration
