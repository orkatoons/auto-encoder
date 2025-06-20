import time
import subprocess
import sys
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

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
windows = Desktop(backend="uia").windows()

for w in windows:
    if "Mozilla Firefox" in w.window_text() and w.is_visible() and not w.is_minimized():
        firefox_window = w
        break

if not firefox_window:
    print("⚠️ Could not find Firefox window. Please make sure Firefox is open.")
    sys.exit(1)

firefox_window.set_focus()
time.sleep(1)  # Wait for the window to activate

# Main scraping loop
for page in range(start_page, start_page + num_pages):
    # Focus the address bar (Ctrl+L)
    send_keys('^l')  # Ctrl + L
    time.sleep(0.5)

    # Type the URL with the current page number
    url = f"https://voice123.com/search?languages=1018&sort_by=top_reviewed_score&page={page}"
    send_keys(url)
    time.sleep(0.5)

    # Press Enter to navigate to the URL
    send_keys('{ENTER}')
    time.sleep(5)  # Wait for the page to load

    # Save the page (Ctrl+S)
    send_keys('^s')
    time.sleep(1)

    if page == start_page:
        # Tab 6 times to reach folder input
        for _ in range(6):
            send_keys('{TAB}')
            time.sleep(0.1)

        send_keys('{ENTER}')  # Activate folder field
        time.sleep(0.5)

        send_keys(save_dir, with_spaces=True)
        time.sleep(0.5)

        send_keys('{ENTER}')  # Confirm folder

        # Tab 7 times to reach Save button
        for _ in range(7):
            send_keys('{TAB}')
            time.sleep(0.2)

        send_keys('{ENTER}')  # Press Save
        time.sleep(1)
    else:
        send_keys('{ENTER}')  # Save directly
        time.sleep(1)

    # Wait for save to complete
    time.sleep(5)

    # Run the profile scraper
    subprocess.run(
        ["python", "profilescraper.py"],
        cwd="C:/Encode Tools/auto-encoder/SOVAS Scraper/helper scripts"
    )

    time.sleep(2)  # Pause before next iteration
