import os
import re
import subprocess
from imdb import IMDb
import json
# --------------------Helper: IMDb Title Lookup--------------------
def find_movie(filename):
    ia = IMDb()
    base_name = os.path.splitext(filename)[0]  # Remove file extension
    words = re.sub(r'[\._-]+', ' ', base_name).split()  # Normalize separators

    # Try stripping words from the right one by one
    for end in range(len(words), 0, -1):
        query = ' '.join(words[:end])
        print(f"Trying IMDb search: {query}")  # Debugging line

        results = ia.search_movie(query)
        if results:
            movie = results[0]  # Take the first result
            print(movie)
            print(f"✅ Found movie: {movie['title']} ({movie.get('year')})")
            return movie

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

    print(video_file,audio_files,subtitle_files,language,resolution,source_format,encoding_used,final_filename,file_title)
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
        default_subtitle = "yes" if language != "eng" else "no"

        cmd.extend([
            "--language", "0:eng",  # Assuming all subs are English
            "--forced-track", "0:no",  # FIX: changed from --forced-display
            "--default-track", f"0:{default_subtitle}",
            subtitle_file
        ])

    # Run the command
    print("Running command:", " ".join(cmd))
    subprocess.run(cmd)
    print("✅ Mutliplexing Completed")


# ---------------------------
# >>> ADD MULTIPLEXING CALL <<<
# ---------------------------


# 1. Find official IMDb data
movie_data = find_movie(filename)  # or find_movie(output_file)
if movie_data:
    official_title = movie_data['title']
    official_year = movie_data.get('year', '0000')
else:
    # Fallback if IMDb not found
    official_title = os.path.splitext(filename)[0]
    official_year = "0000"

# 2. Construct final output name (Step 13)
encoding_used = "x264"  # We used x264 in the HandBrake command
global encoding_source_format
language = detect_languages_ffmpeg(input_file)  # Adjust or auto-detect
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
