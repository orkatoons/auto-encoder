from tkinter import Tk, filedialog, Listbox, Button, Text, Scrollbar, Frame, END, Label, LEFT, RIGHT
import os
import sys
import threading
import subprocess
import time
import re
import requests
from pymkv import MKVFile
import numpy as np
from imdb import IMDb, IMDbError
import json
import config
import cv2
from dotenv import load_dotenv
import logging
from datetime import datetime
logging.basicConfig(level=logging.INFO)

import sys
sys.stdout.reconfigure(encoding='utf-8')


# ----------------- Configuration -----------------
load_dotenv()
HANDBRAKE_CLI = os.getenv("HANDBRAKE_CLI")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
FFMPEG = os.getenv("FFMPEG")
FFPROBE = os.getenv("FFPROBE")
MEDIAINFO_PATH = os.getenv("MEDIAINFO_PATH")
MKVEXTRACT = os.getenv("MKVEXTRACT")
PTPIMG_API_KEY = os.getenv("API_KEY")
UPLOAD_TO_PTPIMG = True

PRESET_SETTINGS = {
    "480p": {"width": 854, "height": 480, "quality": 11, "ratio": "16:9"},
    "576p": {"width": 1024, "height": 576, "quality": 13, "ratio": "16:9"},
    "720p": {"width": 1280, "height": 720, "quality": 15, "ratio": "16:9"},
    "1080p": {"width": 1920, "height": 1080, "quality": 17, "ratio": "16:9"},
}

BITRATE_RANGES = {
        "480p": (1500, 2500),
        "576p": (2500, 3500),
        "720p": (5000, 7000),
}

cropping_start_times = [300, 1000, 1500, 2500]

encode_preview_start_section = ["seconds:300", "seconds:1500", "seconds:2500"]

cq_range = [9, 27]

encoding_source_format = None

APPROVAL_FILENAME = "approval.txt"

STATUS_FILE = 'status.json'


# ----------------- Utility Functions -----------------

def update_resolution_status(job_id, filename, resolution, status, progress):
    """
    Update the status of the encoding job in the status file.
    """
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
    else:
        status_data = {}

    if job_id not in status_data:
        status_data[job_id] = {
            "filename": filename,
            "resolutions": {}
        }
    
    if resolution not in status_data[job_id]["resolutions"]:
        status_data[job_id]["resolutions"][resolution] = {}
    
    status_data[job_id]["resolutions"][resolution].update({
        "status": status,
        "progress": progress
    })
    status_data[job_id]["updated_at"] = datetime.utcnow().isoformat()

    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, indent=2, ensure_ascii=False)


def send_completion_webhook(completion_bitrate, resolution, input_file):
    message = f"✅ Completed encoding for {input_file} @ {resolution} \n⏩ Bitrate: {completion_bitrate} kbps"
    data = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=data)
        if response.status_code in (200, 204):
            log(f"✅ Completion webhook sent successfully for {input_file} at {resolution}.")
        else:
            log(f"❌ Failed to send webhook: {response.status_code} - {response.text}")
    except Exception as e:
        log("❌ Exception sending completion webhook: " + str(e))
    return True


def send_webhook_message(message):
    data = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=data)
        if response.status_code in (200, 204):
            log(f"✅ Webhook sent successfully.")
        else:
            log(f"❌ Failed to send webhook: {response.status_code} - {response.text}")
    except Exception as e:
        log("❌ Exception sending completion webhook: " + str(e))


def get_bitrate(output_file):
    try:
        cmd = [
            FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        bitrate = int(result.stdout.strip()) // 1000
        log(f"Bitrate is {bitrate} Kbps")
        return bitrate
    except Exception as e:
        log("Error extracting bitrate: " + str(e))
        return None

# ----------------- Cropping Functions -----------------

def make_even(value):
    return value if value % 2 == 0 else value + 1

def detect_black_bars(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 5, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    return x, y, w, h


def extract_frame(input_file, start_time, temp_frame):
    print("Getting frame")
    ffmpeg_cmd = [
        "ffmpeg", "-i", input_file, "-ss", str(start_time), "-vframes", "1", "-y", temp_frame
    ]

    process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)



def get_cropping(settings, input_file, cropped_image, res, cq=17):
    send_webhook_message(f"Beginning Cropping for {input_file}")

    if not settings:
        log(f"❌ No settings found for {res}, skipping...")
        return None

    # Define four start times for consistency check
    start_times = cropping_start_times

    crops = []

    for start_time in start_times:
        temp_frame = f'temp_frame_{start_time}_{res}.png'
        print("Extracting frame")
        extract_frame(input_file, start_time, temp_frame)
        frame = cv2.imread(temp_frame)
        x, y, w, h = detect_black_bars(frame)

        # Calculate crop values
        top_crop = make_even(y)
        bottom_crop = make_even(frame.shape[0] - (y + h))
        left_crop = make_even(x)
        right_crop = make_even(frame.shape[1] - (x + w))

        print(f"Crop values for frame at {start_time}s: ")
        print(f"Top: {top_crop}, Bottom: {bottom_crop}, Left: {left_crop}, Right: {right_crop}")

        crops.append((top_crop, bottom_crop, left_crop, right_crop))

        # Compute median crop values for consistency
    crops_array = np.array(crops)
    median_crop = np.median(crops_array, axis=0).astype(int)
    final_crop_values = f'{median_crop[0]}:{median_crop[1]}:{median_crop[2]}:{median_crop[3]}'

    preview_file = f"preview_{res}.mkv"

    command = [
        HANDBRAKE_CLI,
        "-i", input_file,
        "-o", preview_file,
        "--encoder", "x264",
        "--quality", str(cq),
        "--width", str(settings["width"]),
        "--height", str(settings["height"]),
        "--encoder-preset", "placebo",
        "--encoder-profile", "high",
        "--encoder-level", "4.1",
        "--encopts",
        ("subme=10:deblock=-3,-3:me=umh:merange=32:mbtree=0:"
         "dct-decimate=0:fast-pskip=0:aq-mode=2:aq-strength=1.0:"
         "qcomp=0.60:psy-rd=1.0,0.00"),
        '--start-at', f'seconds:{start_times[1]}',  # Using the second start time for preview
        '--stop-at', 'seconds:2',
        "--crop", final_crop_values
    ]

    log(f"🎬 Encoding preview snapshot for {res}...")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                               errors="ignore")
    for line in process.stdout:
        sub_log(line, end="")
    process.wait()

    ffmpeg_cmd = [
        "ffmpeg", "-ss", "1", "-i", preview_file, "-vframes", "1", "-y", cropped_image
    ]
    log(f"📸 Capturing cropped snapshot: {cropped_image}")
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        sub_log(line, end="")
    process.wait()
    log(f"📷 Snapshot saved as {cropped_image}")

    os.remove(preview_file)

    # Send final detected crop values to Discord
    discord_message = (
        f"📏 Final consistent cropping values for {res}:\n"
        f"Top: {median_crop[0]}px\n"
        f"Bottom: {median_crop[1]}px\n"
        f"Left: {median_crop[2]}px\n"
        f"Right: {median_crop[3]}px"
    )
    send_webhook_message(discord_message)

    return final_crop_values


def encode_preview(input_file, res, cq, approved_crop):
    settings = PRESET_SETTINGS.get(res)
    if not settings:
        log(f"❌ No settings found for {res}, skipping...")
        return None

    start_section = encode_preview_start_section  # Start, Middle, End
    bitrates = []
    CQs = []

    for start in start_section:
        while True:
            preview_file = f"preview_{res}_{start}.mkv"
            command = [
                HANDBRAKE_CLI,
                "-i", input_file,
                "-o", preview_file,
                "--crop", approved_crop,
                "--encoder", "x264",
                "--quality", str(cq),
                "--width", str(settings["width"]),
                "--height", str(settings["height"]),
                "--encoder-preset", "placebo",
                "--encoder-profile", "high",
                "--encoder-level", "4.1",
                "--encopts",
                ("subme=10:deblock=-3,-3:me=umh:merange=32:mbtree=0:"
                 "dct-decimate=0:fast-pskip=0:aq-mode=2:aq-strength=1.0:"
                 "qcomp=0.60:psy-rd=1.1,0.00"),
                "--start-at", start,
                "--stop-at", f'seconds:100'
            ]

            log(f"\n🎬 Encoding preview for {res} with CQ {cq} @ {start} seconds...\n")
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore")
            for line in process.stdout:
                sub_log(line, end="")
            process.wait()

            bitrate = get_bitrate(preview_file)

            if bitrate:
                min_bitrate, max_bitrate = BITRATE_RANGES[res]
                if bitrate < min_bitrate:
                    cq -= 1
                elif bitrate > max_bitrate:
                    cq += 1
                else:
                    bitrates.append(bitrate)
                    CQs.append(cq)
                    break  # Move to the next section once it's in range
            else:
                log("⚠️ No valid bitrate found, retrying with adjusted CQ.")

    if bitrates:
        avg_bitrate = round(sum(bitrates) / len(bitrates))
        return cq, avg_bitrate
    else:
        log("⚠️ No valid bitrates found.")
        return None


def adjust_cq_for_bitrate(input_file, res, approved_crop):
    min_bitrate, max_bitrate = BITRATE_RANGES[res]
    cq = 17
    while True:
        cq, bitrate = encode_preview(input_file, res, cq, approved_crop)
        print("CQ is", cq, "Bitrate is ", bitrate)
        if bitrate is None:
            log("⚠️ Failed to encode preview.")
            return None

        log(f"🔍 Bitrate for {res} preview: {bitrate} Kbps")
        if min_bitrate <= bitrate <= max_bitrate:
            log(f"✅ Bitrate is in range ({min_bitrate}-{max_bitrate} Kbps)")
            return int(cq)
        elif bitrate > max_bitrate:
            cq += 1
        elif bitrate < min_bitrate:
            cq -= 1

        if cq < int(cq_range[0]) or cq > int(cq_range[1]):
            log("⚠️ CQ adjustment out of range. Using default CQ 17.")
            return 17


def run_final_encode(input_file, output_file, approved_crop, cq, settings, final_encode_log, res, attempts=1, max_attempts=5):
    min_bitrate, max_bitrate = BITRATE_RANGES[res]
    send_webhook_message(f"Beginning encode {attempts} with cq {cq}")
    command = [
        HANDBRAKE_CLI,
        "-i", input_file,
        "-o", output_file,
        "--crop", approved_crop,
        "--non-anamorphic",
        "--encoder", "x264",
        "-a", "none",  # disable audio
        "-s", "none",  # disable subtitles
        "--quality", str(cq),
        "--width", str(settings["width"]),
        "--encoder-preset", "placebo",
        "--encoder-profile", "high",
        "--encoder-level", "4.1",
        "--encopts",
        (
            "subme=10:deblock=-3,-3:me=umh:merange=32:mbtree=0:"
            "dct-decimate=0:fast-pskip=0:aq-mode=2:aq-strength=1.0:"
            "qcomp=0.60:psy-rd=1.1,0.00"
        )
    ]
    log(f"\n🚀 Starting final encode for {res}... at CQ {cq}\n")
    with open(final_encode_log, "w", encoding="utf-8", errors="ignore") as log_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="ignore")
        for line in process.stdout:
            sub_log(line, end="")
            log_file.write(line)
            log_file.flush()
        process.wait()

    bitrate = get_bitrate(output_file)
    send_webhook_message(f"Encoding attempt #{attempts} completed at {bitrate} with cq {cq} ")
    print("Final ranges are: ",min_bitrate, bitrate, max_bitrate)
    if min_bitrate <= bitrate <= max_bitrate:
        return True
    elif attempts > max_attempts:
        send_webhook_message("Failed to get desried final bitrate in 5 attempts aborting")
        return False
    elif bitrate > max_bitrate:
        return run_final_encode(input_file, output_file, approved_crop, cq + 1, settings, final_encode_log, res, attempts= attempts+1)
    elif bitrate < min_bitrate:
        return run_final_encode(input_file, output_file, approved_crop, cq -1, settings, final_encode_log, res)

# --------------------Phase 2 (Audio)--------------------
def extract_audio(input_file, res):
    """
    Extracts the best available audio track using eac3to:
    - Prioritizes lossless (DTS-HD MA > TrueHD > LPCM > FLAC)
    - Falls back to best lossy (highest channel count)
    Returns path to the extracted audio file (single best track).
    """
    global temp_audio, qaac_cmd
    input_dir = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    parent_dir = os.path.normpath(os.path.join(input_dir, ".."))
    output_dir = os.path.normpath(os.path.join(parent_dir, res))
    os.makedirs(output_dir, exist_ok=True)

    lossless_codecs = ["DTS-HD MA", "TrueHD", "LPCM", "FLAC"]

    print(f"🎵 Scanning audio tracks for {base_name}...")

    # Get track list
    list_cmd = ["eac3to", input_file]
    result = subprocess.run(list_cmd, capture_output=True, text=True)
    stdout = result.stdout
    if result.stderr:
        print(result.stderr)

    # Match tracks
    track_lines = re.findall(r"(\d+): (.+?)\s*\n", stdout)
    if not track_lines:
        print("⚠️ No audio tracks found!")
        return []

    # Sort by priority: lossless preferred, fallback to best lossy by channel count
    def track_priority(line):
        track_num, desc = line
        for i, codec in enumerate(lossless_codecs):
            if codec in desc:
                return 0, i  # Lossless found, lower index = higher priority
        match = re.search(r"(\d+\.\d) channels", desc)
        channels = float(match.group(1)) if match else 0
        return 1, -channels  # Lossy, prefer more channels

    sorted_tracks = sorted(track_lines, key=track_priority)
    best_track_num, best_desc = sorted_tracks[0]
    print(f"🎯 Best track: {best_track_num} - {best_desc}")

    # Extract best track
    is_lossless = any(codec in best_desc for codec in lossless_codecs)
    is_surround = any(x in best_desc for x in ["5.1", "7.1"])

    if is_lossless:
        if is_surround:
            bitrate = "448" if ("480p" in input_file or "576p" in input_file) else "640"
            output_file = os.path.normpath(
                os.path.join(output_dir, f"{base_name}@{res}-{bitrate}.ac3")
            )
            extract_cmd = f'eac3to "{input_file}" {best_track_num}:"{output_file}" -{bitrate}'
        else:
            temp_audio = os.path.join(output_dir, "temp.aac")
            output_file = os.path.normpath(os.path.join(output_dir, f"{base_name}@{res}.m4a"))
            extract_cmd = f'eac3to "{input_file}" {best_track_num}:"{temp_audio}"'
            qaac_cmd = f'qaac64 -V 127 -i "{temp_audio}" --no-delay -o "{output_file}"'
    else:
        ext = "ac3" if is_surround else "m4a"
        output_file = os.path.normpath(os.path.join(output_dir, f"{base_name}@{res}.{ext}"))
        extract_cmd = f'eac3to "{input_file}" {best_track_num}:"{output_file}"'

    print("🔧 Extracting audio...")
    result = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
        send_webhook_message("❌ Audio extraction failed!")
        return []

    if is_lossless and not is_surround:
        print("🎛 Converting with qaac...")
        result = subprocess.run(qaac_cmd, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

    send_webhook_message(f"✅ Audio extraction complete: {output_file}")
    return [output_file]

# --------------------Phase 3 (Subtitles)--------------------
def extract_subtitles(mkv_path):
    """
    Extracts subtitle tracks using mkvextract and returns a list of paths to the extracted subtitle files.
    """
    input_dir = os.path.dirname(mkv_path)
    base_name = os.path.splitext(os.path.basename(mkv_path))[0]

    mkv = MKVFile(mkv_path)
    print("MKV merge output:")
    print(mkv)

    subtitle_paths = []

    for track in mkv.tracks:
        print("Found track:", track)
        if track.track_type == "subtitles":
            if "PGS" in track._track_codec:
                out_ext = "sup"
            elif "SubRip" in track._track_codec or "SRT" in track._track_codec:
                out_ext = "srt"
            elif "VobSub" in track._track_codec:
                out_ext = "idx"
            else:
                out_ext = "txt"

            language = track._language if track._language else "unknown"
            output_file = os.path.join(
                input_dir,
                f"{base_name}_subtitle_{track._track_id}_{language}.{out_ext}"
            )

            cmd = [MKVEXTRACT, "tracks", mkv_path, f"{track._track_id}:{output_file}"]
            print("Running command:", " ".join(cmd))
            subprocess.run(cmd)
            send_webhook_message(f"✅ Extracted subtitle track {track._track_id} for {base_name}")

            subtitle_paths.append(output_file)
        else:
            log(f"Unable to extract {track._track_id} with codec {track._track_codec} for {base_name}")

    print("Extraction complete!")
    return subtitle_paths


# --------------------Helper: IMDb Title Lookup--------------------


def find_movie(filename):
    max_retries = 3
    retry_delay_minutes = 30
    ia = IMDb()
    base_name = os.path.splitext(filename)[0]
    words = re.sub(r'[\._-]+', ' ', base_name)
    words = re.sub(
        r'\b(1080p|720p|480p|BluRay|WEB-DL|HDRip|DVDRip|x264|x265|HEVC|AAC|DTS|HD)\b',
        '', words, flags=re.IGNORECASE
    ).split()

    for end in range(len(words), 0, -1):
        query = ' '.join(words[:end])
        print(f"Trying IMDb search: {query}")

        for attempt in range(max_retries):
            try:
                results = ia.search_movie(query)
                if results:
                    movie = results[0]
                    ia.update(movie)
                    year = movie.get('year', 'Unknown')
                    print(f"✅ Found movie: {movie.get('title', 'Unknown Title')} ({year})")
                    return movie
                break  # If no results, skip to next shorter query
            except (IMDbError, Exception) as e:
                print(f"⚠️ IMDb fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Retrying after {retry_delay_minutes} minutes...")
                    time.sleep(retry_delay_minutes * 60)

    print("❌ No IMDb match found.")
    return None


def detect_languages_ffmpeg(input_file):
    """
    Detects languages of audio tracks using FFmpeg.
    Returns the most common or first detected language (default: 'eng').
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-select_streams", "a",
        "-of", "json", input_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stderr:
        print("Error:", result.stderr)
        return "eng"  # Default to English if detection fails

    # Parse JSON output
    data = json.loads(result.stdout)
    audio_languages = []

    for stream in data.get("streams", []):
        lang = stream.get("tags", {}).get("language", "unknown")
        if lang != "unknown":
            audio_languages.append(lang)

    # Pick the most common or first detected language
    return audio_languages[0] if audio_languages else "eng"


# --------------------Phase 4 (Multiplexing)--------------------
def multiplex_file(
    video_file,
    audio_files,
    subtitle_files,
    language,  # Main language of the film (e.g., 'eng', 'hin', 'undf')
    resolution,
    source_format,
    encoding_used,
    final_filename,
    file_title
):
    print(f"""
    Video File       : {video_file}
    Audio Files      : {audio_files}
    Subtitle Files   : {subtitle_files}
    Language         : {language}
    Resolution       : {resolution}
    Source Format    : {source_format}
    Encoding Used    : {encoding_used}
    Final Filename   : {final_filename}
    File Title       : {file_title}
    """)

    """
    Combines video, audio, and subtitle files into a final MKV using mkvmerge.
    """

    # Base command
    cmd = [
        "mkvmerge", "-o", final_filename,
        "--title", file_title,
        "--no-global-tags", "--no-chapters",
        video_file
    ]

    # Add audio tracks with appropriate language settings
    for audio_file in audio_files:
        default_audio = "yes" if language != "undf" else "no"

        cmd.extend([
            "--language", f"0:{language}",
            "--default-track", f"0:{default_audio}",
            audio_file
        ])

    # Add subtitle tracks
    for subtitle_file in subtitle_files:
        # Extract language code from filename (e.g., "_eng.srt")
        match = re.search(r'_([a-z]{2,3})\.[a-z]+$', subtitle_file)
        subtitle_lang = match.group(1) if match else "und"

        # Only set as default if movie is in English and subtitle is also English
        default_subtitle = "yes" if language == "eng" and subtitle_lang == "eng" else "no"

        cmd.extend([
            "--language", f"0:{subtitle_lang}",
            "--forced-track", "0:no",
            "--default-track", f"0:{default_subtitle}",
            subtitle_file
        ])

    # Run the command
    print("Running command:", " ".join(cmd))
    subprocess.run(cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="ignore")
    for line in process.stdout:
        print(line, end="")

    send_webhook_message("✅ Mutliplexing Completed")


# --------------------Phase 5 (Screenshots)--------------------
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




# --------------------Phase 6 (Approval Doc)--------------------
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




# --------------------Main Encoding Function--------------------
def encode_file(input_file, resolutions, job_id):
    filename = os.path.basename(input_file)
    original_filename = os.path.splitext(os.path.basename(input_file))[0]
    send_webhook_message(f"Beginning encoding for {filename} @ {resolutions}")

    # Extract subtitles & store paths
    subtitle_files = extract_subtitles(input_file)
    asubtitle_files = extract_subtitles(input_file)
    report_progress(filename, 5)
    for res in resolutions:
        update_resolution_status(job_id, filename, res, f"Extracted Subtitles", "3")
        status_callback(filename, res, "Starting...")
        settings = PRESET_SETTINGS.get(res)
        metadata = config.parse_video_metadata(input_file, settings)
        settings["width"] = metadata["width"]
        settings["height"] = metadata["height"]

        if not settings:
            log(f"❌ No settings found for {res}, skipping...")
            status_callback(filename, res, "Skipped (no settings)")
            continue

        # Extract audio & store paths
        update_resolution_status(job_id, filename, res, f"Extracting Audio", "5")
        audio_files = extract_audio(input_file, res)
        print("Audio extracted")
        update_resolution_status(job_id, filename, res, f"Extracted Audio", "8")
        update_resolution_status(job_id, filename, res, f"Getting Cropping values", "9")
        approved_crop = get_cropping(settings, input_file, f"preview_snapshot_{res}.png", res)
        if not approved_crop:
            log("⏩ Skipping final encoding due to lack of crop approval.")
            status_callback(filename, res, "Skipped (no crop)")
            continue

        update_resolution_status(job_id, filename, res, f"Cropping values extracted", "15")
        update_resolution_status(job_id, filename, res, f"Checking for Optimal CQ", "17")
        cq = adjust_cq_for_bitrate(input_file, res, approved_crop)
        if cq is None:
            log(f"⏩ Final encoding for {res} was cancelled.")
            status_callback(filename, res, "Cancelled")
            continue
        update_resolution_status(job_id, filename, res, f"Found Optimal CQ", "20")
        send_webhook_message(f"Proceeding to Final Encode for {filename}@{res}")
        update_resolution_status(job_id, filename, res, f"Proceeding to final encode", "25")

        parent_dir = os.path.normpath(os.path.join(os.path.dirname(input_file), ".."))

        output_dir = os.path.normpath(os.path.join(parent_dir, res))

        # Construct the normalized output file path using os.path.join
        output_file = os.path.normpath(
            os.path.join(output_dir, f"{os.path.splitext(filename)[0]}@{res}.mkv")
        )

        final_encode_log = os.path.join(output_dir, "handbrake_encode_log.txt")

        print("Output file path:", output_file)  # Debugging
        log(f"Output file path: {output_file}")  # Debugging

        # Run HandBrake CLI for final encoding

        output = run_final_encode(input_file, output_file, approved_crop, cq, settings, final_encode_log, res)

        if output:
            update_resolution_status(job_id, filename, res, f"Final video encoding completed", "75")
            log(f"\n✅ Successfully encoded: {output_file}\n")
            completion_bitrate = get_bitrate(output_file)

            status_callback(filename, res, "Completed")
            update_resolution_status(job_id, filename, res, f"Starting Multiplexing", "76")
            # ---------------------------
            # >>> ADD MULTIPLEXING CALL <<<
            # ---------------------------
            # 1. Find official IMDb data
            grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(input_file)))
            movie_data = find_movie(grandparent_dir)  # or find_movie(output_file)
            if movie_data:
                official_title = movie_data['original title']
                official_year = movie_data.get('year', '0000')
            else:
                # Fallback if IMDb not found
                official_title = os.path.splitext(filename)[0]
                official_year = "0000"

            # 2. Construct final output name (Step 13)
            encoding_used = "x264"  # We used x264 in the HandBrake command
            global encoding_source_format
            language = detect_languages_ffmpeg(input_file)         # Adjust or auto-detect
            final_filename = os.path.join(
                output_dir,
                f"{official_title.replace(' ', '.')}."
                f"{official_year}.{res}.{encoding_source_format}.{encoding_used}-HANDJOB.mkv"
            )

            # 3. Construct the file title (Step 14)
            file_title = f"{official_title} [{official_year}] {res} {encoding_source_format} - HJ"

            # 4. Run the multiplex
            multiplex_file(
                video_file=output_file,
                audio_files=audio_files,
                subtitle_files=subtitle_files,
                language=language,
                resolution=res,
                source_format=encoding_source_format,
                encoding_used=encoding_used,
                final_filename=final_filename,
                file_title=file_title
            )
            update_resolution_status(job_id, filename, res, f"Completed Multiplexing", "85")
            #---------------Screenshots---------------
            output_dir = os.path.normpath(os.path.join(parent_dir, res))
            screenshot_output_dir = os.path.join(output_dir, "screenshots")
            send_webhook_message("Extracting Screenshots for ptp upload")
            screenshot_bbcodes = config.extract_screenshots(screenshot_output_dir, final_filename)
            update_resolution_status(job_id, filename, res, f"Extracted Screenshots", "90")
            send_webhook_message("Creating Approval Document")
            update_resolution_status(job_id, filename, res, f"Creating Upload Doc", "91")
            log("Extracting MediaInfo...")
            mediainfo_text = config.extract_mediainfo(final_filename)

            log("\nSearching PTP...")
            movie_title = official_title.replace('.', ' ')

            print(f"Sending {movie_title}, {official_year}, {final_filename}, {original_filename}")

            ptp_url = config.get_ptp_permalink(movie_title, official_year, final_filename, original_filename)
            update_resolution_status(job_id, filename, res, f"Fetching Torrent Details", "95")
            # Step 4: Get movie sources
            log("\nGetting torrent sources")
            ptp_sources = config.find_movie_source_cli(ptp_url)

            # Step 5: Generate approval file
            log("\nGenerating approval document...")
            approval_output_dir = os.path.join(output_dir, "approval.txt")
            upload_output_dir = os.path.join(output_dir, "upload.txt")
            config.generate_approval_form(ptp_url, mediainfo_text, screenshot_bbcodes, approval_output_dir, final_encode_log)
            config.generate_upload_form(ptp_url, mediainfo_text, screenshot_bbcodes, ptp_sources, upload_output_dir, movie_title)
            update_resolution_status(job_id, filename, res, f"Completed", "100")
            print(f"\nProcess complete! Approval file saved to {APPROVAL_FILENAME}")
            send_completion_webhook(completion_bitrate, res, input_file)


        else:
            log(f"\n❌ Encoding failed for {res}!\n")
            send_webhook_message(f"Encoding failed for {filename}@{res}")
            status_callback(filename, res, "Failed")

def determine_encodes(file_path):
    """
    Determines the encoding resolutions based on the filename.
    - BluRay sources get ["720p", "576p", "480p"].
    - Everything else gets only ["720p"].
    """
    global encoding_source_format
    source_keywords = [
        ("bluray", "BluRay"), ("blu-ray", "BluRay"), ("brrip", "BluRay"),
        ("bdrip", "BluRay"), ("bd25", "BluRay"), ("bd50", "BluRay"),
        ("remux", "BluRay"), ("web-dl", "WEB-DL"), ("webdl", "WEB-DL"),
        ("webrip", "WEB-DL"), ("amzn", "WEB-DL"), ("netflix", "WEB-DL"),
        ("hdrip", "WEB-DL"), ("dvdrip", "WEB-DL"), ("hdtv", "WEB-DL")
    ]

    filename = os.path.basename(file_path).lower()

    # Detect source format
    source_format = "Unknown"
    for keyword, fmt in source_keywords:
        if keyword in filename:
            source_format = fmt
            encoding_source_format = fmt
            break  # Stop at first match

    # Assign resolutions based on format
    if source_format == "BluRay":
        return ["720p", "576p", "480p"]
    else:
        return ["720p"]
    

def log(message, end="\n"):
    logging.info(message)

def sub_log(message, end="\n"):
    logging.info(message)

def status_callback(filename, res, status):
    log(f"Status for {filename}@{res}: {status}")

def report_progress(filename, percent):
    print(f"PROGRESS::{filename}::{percent}")  # Goes to Node stdout
    sys.stdout.flush()
    time.sleep(0.5)

def start_encoding(file, job_id=None):
    resolutions = determine_encodes(file)
    encode_file(file, resolutions, job_id)
    log(f"Encoding completed for {file}")
    try:
        requests.post("http://geekyandbrain.ddns.net:3030/api/encode/complete", json={
            "jobid": job_id,
            "filename": file,
            "status": "completed"
        })
    except Exception as e:
        print(f"Failed to notify completion: {e}")

if __name__ == "__main__":
    # Get the file path from the command-line argument
    start_encoding(r"W:\Encodes\Bajirao Mastani\source\Bajirao Mastani 2015 1080p Blu-ray Remux AVC TrueHD 7.1 - KRaLiMaRKo.mkv")