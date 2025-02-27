import os
import subprocess
from pymkv import MKVFile

# Define your input MKV file
mkv_path = r"C:\Users\thevi\Downloads\Voyager S06E01 Equinox Part II  [1080p x265 10bit Joy].mkv"

# Use the same directory as the MKV file for output.
input_dir = os.path.dirname(mkv_path)
# Get the base filename (without extension)
base_name = os.path.splitext(os.path.basename(mkv_path))[0]

# Load the MKV file using pymkv (which calls mkvmerge)
mkv = MKVFile(mkv_path)
print("MKV merge output:")
print(mkv)

# Loop through all tracks and extract subtitle tracks
for track in mkv.tracks:
    print("Found track:", track)
    if track.track_type == "subtitles":
        # Decide on the output extension based on the subtitle codec.
        # For PGS subtitles, use ".sup"
        # For SubRip/SRT subtitles, use ".srt"
        # For VobSub, extraction will generate a pair (.idx and .sub) if you specify ".idx"
        if track._track_codec == "PGS":
            out_ext = "sup"
        elif track._track_codec == "SubRip/SRT":
            out_ext = "srt"
        elif track._track_codec == "VobSub":
            out_ext = "idx"
        else:
            out_ext = "txt"  # fallback

        language = track._language if track._language else "unknown"
        # Build output filename: original base name plus subtitle info.
        output_file = os.path.join(input_dir, f"{base_name}_subtitle_{track._track_id}_{language}.{out_ext}")

        # Build and run the mkvextract command:
        # mkvextract tracks <mkv_file> <track_id>:<output_file>
        cmd = ["mkvextract", "tracks", mkv_path, f"{track._track_id}:{output_file}"]
        print("Running command:", " ".join(cmd))
        subprocess.run(cmd)
        print(f"✅ Extracted subtitle track {track._track_id} to {output_file}")
    else:
        print(f"Skipping track {track._track_id} with codec {track._track_codec}")

print("Extraction complete!")
