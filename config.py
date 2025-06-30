import cv2
import numpy as np
import os
import requests
import subprocess
import shlex
import re
from moviepy import VideoFileClip
from ptpapi import API, login as ptp_login
from flask.cli import load_dotenv


load_dotenv()

# ========== CONFIGURATION ==========
# Media file configuration
SOURCE_FILE_PATH = r"W:\Encodes\Bhagam Bhag\source\Bhagam.Bhag.2006.BluRay.1080p.DTS-HD.MA.5.1.AVC.REMUX-FraMeSToR.mkv"
MOVIE_TITLE = "Bhagam Bhag"
RELEASE_YEAR = 2006

# Path configuration
MEDIAINFO_PATH = r"C:\Program Files\MediaInfo_CLI_25.03_Windows_x64\MediaInfo.exe"
SCREENSHOT_OUTPUT_DIR = "screenshots"
APPROVAL_FILENAME = "approved.txt"

# PTP configuration
PTPIMG_API_KEY = os.getenv("API_KEY")  # Set in .env file
UPLOAD_TO_PTPIMG = True


# ====================================

def extract_mediainfo(source_file):
    """Extract technical metadata using MediaInfo CLI"""
    try:
        result = subprocess.run(
            [MEDIAINFO_PATH, source_file],
            capture_output=True,
            text=True,
            check=True
        )
        print(result)
        return result.stdout
    except Exception as e:
        print(f"MediaInfo Error: {str(e)}")
        return None

def parse_video_metadata(source_file_path, settings):
    """Extract metadata and adjust target height based on aspect ratio."""
    mediainfo_text = extract_mediainfo(source_file_path)

    metadata = {}

    # Raw metadata extraction
    width_match = re.search(r"Width\s+:\s+(\d+)\s+pixels", mediainfo_text)
    height_match = re.search(r"Height\s+:\s+(\d+)\s+pixels", mediainfo_text)
    aspect_ratio_match = re.search(r"Display aspect ratio\s+:\s+([\d.]+:\d+)", mediainfo_text)

    if width_match:
        metadata['source_width'] = int(width_match.group(1))
    if height_match:
        metadata['source_height'] = int(height_match.group(1))
    if aspect_ratio_match:
        metadata['aspect_ratio'] = aspect_ratio_match.group(1)
    else:
        raise ValueError("Aspect ratio not found in metadata.")

    # Target width from preset
    target_width = settings["width"]

    # Compute target height
    try:
        num, denom = map(float, metadata["aspect_ratio"].split(":"))
        target_height = int(round(target_width / (num / denom)))
    except Exception as e:
        raise ValueError(f"Failed to compute height from aspect ratio: {e}")

    metadata["width"] = target_width
    metadata["height"] = target_height

    return metadata


def calculate_brightness(image):
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return np.mean(grayscale)


def calculate_contrast(image):
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return grayscale.std()


def is_well_lit(brightness, contrast, brightness_threshold=80, contrast_threshold=50):
    return brightness >= brightness_threshold and contrast >= contrast_threshold


def upload_to_ptpimg(file_path):
    """Upload image to ptpimg.me and return BBCode"""
    with open(file_path, 'rb') as img_file:
        response = requests.post(
            'https://ptpimg.me/upload.php',
            files={'file-upload[0]': img_file},
            data={'api_key': PTPIMG_API_KEY}
        )
    if response.status_code == 200:
        return f"[img]https://ptpimg.me/{response.json()[0]['code']}.jpg[/img]"
    return None


def extract_screenshots(SCREENSHOT_OUTPUT_DIR, SOURCE_FILE_PATH, resolution=None):
    """Extract and upload screenshots (skipping first 5 minutes)"""
    clip = VideoFileClip(SOURCE_FILE_PATH)
    duration = clip.duration
    screenshot_data = []

    # Skip first 300 seconds (5 minutes)
    start_offset = 300 if duration > 300 else 0
    usable_duration = duration - start_offset

    # Define different sections for different resolutions
    resolution_sections = {
        "480p": [0.1, 0.4, 0.7],  # Early, middle, late sections
        "576p": [0.2, 0.5, 0.8],  # Slightly different sections
        "720p": [0.15, 0.45, 0.75],  # Different middle sections
        "1080p": [0.25, 0.55, 0.85]  # Later sections
    }
    
    # Use resolution-specific sections if available, otherwise use default
    if resolution and resolution in resolution_sections:
        section_offsets = resolution_sections[resolution]
        print(f"Using {resolution}-specific screenshot sections: {section_offsets}")
    else:
        # Default sections (original behavior)
        section_offsets = [0.33, 0.66, 1.0]
        print(f"Using default screenshot sections for {resolution}: {section_offsets}")

    os.makedirs(SCREENSHOT_OUTPUT_DIR, exist_ok=True)

    for i in range(3):
        best_time = None
        best_score = -1

        # Calculate section bounds with offset based on resolution
        if i == 0:
            section_start = start_offset
            section_end = start_offset + section_offsets[0] * usable_duration
        elif i == 1:
            section_start = start_offset + section_offsets[0] * usable_duration
            section_end = start_offset + section_offsets[1] * usable_duration
        else:  # i == 2
            section_start = start_offset + section_offsets[1] * usable_duration
            section_end = start_offset + section_offsets[2] * usable_duration

        # Sample 5 points in this section of usable video
        for t in np.linspace(section_start, section_end, num=5):
            try:
                frame = clip.get_frame(t)
                score = calculate_brightness(frame) + calculate_contrast(frame)
                if score > best_score:
                    best_score = score
                    best_time = t
            except Exception as e:
                print(f"Frame error at {t:.2f}s: {e}")

        if best_time is not None:
            # Include resolution in screenshot filename for uniqueness
            if resolution:
                out_path = os.path.join(SCREENSHOT_OUTPUT_DIR, f"screenshot_{resolution}_{i+1}.png")
            else:
                out_path = os.path.join(SCREENSHOT_OUTPUT_DIR, f"screenshot_{i+1}.png")
            clip.save_frame(out_path, t=best_time)
            screenshot_data.append(out_path)

    clip.close()

    # Upload screenshots
    bbcodes = []
    for path in screenshot_data:
        if UPLOAD_TO_PTPIMG:
            bbcode = upload_to_ptpimg(path)
            if bbcode:
                bbcodes.append(bbcode)

    return bbcodes



def find_torrent_id_cli(movie_title, source_filename, original_filename):
    """
    Uses the ptp CLI to search for movie_title, then picks the torrent whose
    ReleaseName matches source_filename (exactly or via substring).
    Returns the torrent ID as a string, or None if not found.
    """
    source_filename = os.path.splitext(os.path.basename(source_filename))[0].strip()
    # Normalize source filename: remove spaces and convert to lowercase
    normalized_source = source_filename.replace(" ", "").lower()
    print(f"[DEBUG] Source filename: {source_filename}")
    print(f"[DEBUG] Normalized source: {normalized_source}")

    cmd = f'ptp search "{movie_title}" --torrent-format="{{{{Id}}}} - {{{{ReleaseName}}}}"'
    args = shlex.split(cmd)

    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"[ERROR] ptp search failed: {stderr.strip()}")
            return None

    except Exception as e:
        print(f"[ERROR] Exception during subprocess: {e}")
        return None

    pattern = re.compile(r'^\s*(\d+)\s*-\s*(.+?)\s*$')

    for line in stdout.splitlines():
        print(f"[DEBUG] Parsing line: {line}")
        match = pattern.match(line)
        if not match:
            continue
        torrent_id, release_name = match.group(1), match.group(2).strip()
        # Normalize release name: remove spaces and convert to lowercase
        normalized_release = release_name.replace(" ", "").lower()
        print(f"[DEBUG] Normalized release: {normalized_release}")
        
        if (normalized_release == normalized_source or 
            normalized_source in normalized_release or 
            normalized_release in normalized_source):
            print(f"[INFO] Match found: {torrent_id} -> {release_name}")
            return torrent_id

    print("[WARN] No matching torrent found in CLI output.")
    return None


def get_ptp_permalink(movie_title, release_year, source_filename, original_filename):
    """
    Combines API lookup for the PTP movie ID with CLI-based torrent ID extraction.
    Falls back to API-based torrent lookup if CLI fails.
    """
    # First, get the movie ID via the API
    ptp_login()
    api = API()
    filters = {'searchstr': movie_title, 'year': str(release_year)}
    results = api.search(filters=filters)
    if not results:
        print("[ERROR] No movie found via API.")
        return None

    movie = results[0]
    movie_id = movie['Id']

    # Next, try the CLI approach to get torrent ID
    torrent_id = find_torrent_id_cli(movie_title, source_filename, original_filename)
    print(torrent_id)
    # Build the final URL
    if torrent_id:
        return f"https://passthepopcorn.me/torrents.php?id={movie_id}&torrentid={torrent_id}"
    else:
        return f"https://passthepopcorn.me/torrents.php?id={movie_id}"


def find_movie_source_cli(torrent_link):

    cmd = f'ptp search "{torrent_link}"'
    args = shlex.split(cmd)
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        print(stdout)


        match = re.search(r"^- (.+?) - ", stdout.strip())

        if match:
            print("Matching source")
            raw_format = match.group(1).strip()
            spaced_format = raw_format.replace("/", " / ")
            print("returning spaced format ", spaced_format)
            return spaced_format
        else:
            print("No match found.")
        return None

    except Exception as e:
        print(f"[ERROR] Exception during subprocess: {e}")
        return None





def generate_upload_form(ptp_url, mediainfo_text, screenshot_bbcodes, ptp_sources, approval_file, movie_title):
    """Generate approval.txt in final BBCode format for forum use"""

    bbcode_screenshots = "\n".join(screenshot_bbcodes)

    content = f"""[align=center][b][size=8] [color=#3d85c6]HANDJOB Encode[/color] [/size][/b][/align]
[hr][align=center][size=3]Encode with: [color=#c5c5c5][i][url={ptp_url}] {movie_title} - {ptp_sources}[/url][/i][/color][/size][/align][hr]
[pre]

[/pre]
[mediainfo] {mediainfo_text} [/mediainfo]
[pre]

[/pre]
[align=center][img]https://ptpimg.me/9w353i.png[/img]
[pre]

[/pre] 
{bbcode_screenshots} 
[pre]

[/pre]
[img]https://ptpimg.me/s91993.png[/img][/align]"""

    with open(approval_file, 'w', encoding='utf-8') as f:
        f.write(content)


def generate_approval_form(ptp_url, mediainfo_text, screenshot_bbcodes, approval_file, handbrake_log):
    """Generate approval.txt in final BBCode format for forum use"""

    bbcode_screenshots = "\n".join(screenshot_bbcodes)

    # Read the HandBrake log file contents
    try:
        with open(handbrake_log, 'r', encoding='utf-8', errors='ignore') as f:
            handbrake_log_content = f.read()
    except Exception as e:
        handbrake_log_content = f"Error reading HandBrake log file: {str(e)}"

    content = f"""Requesting approval for encode of {ptp_url}

    [mediainfo]{mediainfo_text}[/mediainfo]
    
    [hide=Encode Screenshots]{bbcode_screenshots}[/hide]
    
    [hide=HandBrake log][code]{handbrake_log_content}[/code][/hide]"""

    with open(approval_file, 'w', encoding='utf-8') as f:
        f.write(content)



def main():
    # Step 1: Get technical metadata
    print("Extracting MediaInfo...")
    mediainfo_text = extract_mediainfo(SOURCE_FILE_PATH)

    metadata = parse_video_metadata(SOURCE_FILE_PATH)
    print(metadata)

    # Step 2: Create and upload screenshots
    print("\nExtracting screenshots...")
    screenshot_bbcodes = extract_screenshots(SCREENSHOT_OUTPUT_DIR, SOURCE_FILE_PATH)

    # Step 3: Get PTP permalink
    print("\nSearching PTP...")
    ptp_url = get_ptp_permalink(MOVIE_TITLE, RELEASE_YEAR, SOURCE_FILE_PATH)

    #Step 4: Get movie sources
    print("\nGetting torrent sources")
    ptp_sources = find_movie_source_cli(ptp_url)
    print(ptp_sources)

    # Step 4: Generate approval file
    print("\nGenerating approval document...")
    generate_approval_form(ptp_url, mediainfo_text, screenshot_bbcodes, ptp_sources)

    print(f"\nProcess complete! Approval file saved to {APPROVAL_FILENAME}")


if __name__ == "__main__":
    main()