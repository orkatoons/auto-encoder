
# --------------------Helper: IMDb Title Lookup--------------------
import time
from imdb import IMDb, IMDbError
import os
import re


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
                    print(movie.keys())
                    ia.update(movie)
                    print(movie.keys())
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

filename = "Maine Pyaar Kyu Kiya"
'''
movie_data = find_movie(filename)  # or find_movie(output_file)
if movie_data:
    official_title = movie_data['original title']
    official_year = movie_data.get('year', '0000')
else:
                # Fallback if IMDb not found
    official_title = os.path.splitext(filename)[0]
    official_year = "0000"

print(official_title, official_year)'''
file_path = r"C:\Users\thevi\Documents\GeekyandtheBrain\auto_encoder\auto-encoder\bot.py"
grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
print(grandparent_dir)