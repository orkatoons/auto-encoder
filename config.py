import os
import subprocess
import re


def extract_audio(input_file):
    # Ensure output folder exists
    input_dir = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_folder = os.path.normpath(os.path.join(input_dir, base_name))
    print("Outputs", input_dir, base_name)
    print(output_folder)

    # Run eac3to to list tracks
    print("Detecting audio tracks...")
    list_cmd = ["eac3to", input_file]
    result = subprocess.run(list_cmd, capture_output=True, text=True)
    output = result.stdout
    print(output)  # Show output to user

    # Find audio tracks
    tracks = re.findall(r"(\d+): .*?, (\d+\.\d) channels", output)
    if not tracks:
        print("No audio tracks found!")
        return

    for track_number, channels in tracks:
        track_number = track_number.strip()
        channels = channels.strip()

        if channels in ["5.1", "7.1"]:
            bitrate = "448" if "480p" in input_file or "576p" in input_file else "640"
            output_audio = os.path.normpath(os.path.join(output_folder, f"{base_name}-{bitrate}.ac3"))

            extract_cmd = ["eac3to", f'"{input_file}"', f'{track_number}:"{output_audio}"', f"-{bitrate}"]
            print("Running command:", " ".join(extract_cmd))  # Debugging
            subprocess.run(" ".join(extract_cmd), check=True, shell=True)

            #print(f"Extracting 5.1/7.1 audio track {track_number}...")
            #subprocess.run(extract_cmd, check=True, text=True)



        else:

            # Ensure the output folder exists

            os.makedirs(output_folder, exist_ok=True)

            # Normalize and format paths correctly

            temp_audio = os.path.normpath(os.path.join(output_folder, "temp.aac"))

            final_audio = os.path.normpath(os.path.join(output_folder, f"{base_name}.m4a"))

            extract_cmd = f'eac3to "{input_file}" {track_number}:"{temp_audio}"'

            qaac_cmd = f'qaac64 -V 127 -i "{temp_audio}" --no-delay -o "{final_audio}"'

            print(f"🎤 Extracting stereo/mono audio track {track_number}...")

            # Run extraction

            process = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)

            print("STDOUT:\n", process.stdout)

            if process.stderr:
                print("STDERR:\n", process.stderr)

            print("🔄 Converting extracted audio with qaac...")

            # Run qaac conversion

            process = subprocess.run(qaac_cmd, shell=True, capture_output=True, text=True)

            print("STDOUT:\n", process.stdout)

            if process.stderr:
                print("STDERR:\n", process.stderr)

            # Cleanup temp file if extraction succeeded

            if os.path.exists(temp_audio):
                os.remove(temp_audio)

    print("Audio extraction complete!")


# Example usage
input_mkv = r"C:\Users\thevi\Downloads\Season #8\803 - Nannies webdl.mkv"
output_dir = "output_audio"
extract_audio(input_mkv)


