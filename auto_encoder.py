from tkinter import Tk, filedialog, Listbox, Button, Text, Scrollbar, Frame, END, Label, LEFT, RIGHT
import os
import sys
import threading
import subprocess
import time
import re
import requests
from pymkv import MKVFile

# ----------------- Configuration -----------------
FLASK_SERVER_URL = "http://localhost:5000"
HANDBRAKE_CLI = r"C:\Program Files (x86)\HandBrakeCLI-1.9.1-win-x86_64\HandBrakeCLI.exe"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1346557040683778119/cgpYKgRVTCAWRGu79b1fK27Non6MyYApaQMyXRl2qbIIjeolr_fGTeJHPAZ8Fw-PdvM9"
#TEST_DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1341674153404792852/rky38iFrH3h0_S1tzvt3E2Iugi8p1GuT0MmFPIb1DRmpb4lKkwjeHeYACjg6FnX4Ji3O"
PRESET_SETTINGS = {
    "480p": {"width": 854, "height": 480, "quality": 11},
    "576p": {"width": 1024, "height": 576, "quality": 13},
    "720p": {"width": 1280, "height": 720, "quality": 15},
    "1080p": {"width": 1920, "height": 1080, "quality": 17},
}

BITRATE_RANGES = {
    "480p": (1600, 2400),
    "576p": (2600, 3400),
    "720p": (5200, 6800)
}

crop_values = {
    "original": "0:0:0:0",
    "autocrop": "auto",
    "zoom_5": "5:5:5:5",
    "zoom_10": "10:10:10:10"
}

# ----------------- Utility Functions -----------------

def determine_encodes(file_path):
    filename = os.path.basename(file_path).lower()
    if "webdl" in filename:
        return ["720p"]
    elif "bluray" in filename:
        return ["720p", "576p", "480p"]
    else:
        return []

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
    data = {"content":message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=data)
        if response.status_code in (200, 204):
            log(f"✅ Webhook sent successfully.")
        else:
            log(f"❌ Failed to send webhook: {response.status_code} - {response.text}")
    except Exception as e:
        log("❌ Exception sending completion webhook: " + str(e))



def send_previews(preview_files):
    response = requests.post(f"{FLASK_SERVER_URL}/send_previews", json={"previews": preview_files})
    if response.status_code == 200:
        log("✅ Previews sent successfully to Flask.")
    else:
        log(f"❌ Failed to send previews: {response.text}")

def wait_for_approval():
    timeout = 12 * 60 * 60  # 12 hours
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{FLASK_SERVER_URL}/get_approval")
        data = response.json()
        if data.get("approved_crop"):
            log(f"✅ Approved crop received: {data['approved_crop']}")
            return data["approved_crop"]
        time.sleep(10)
    log("❌ Approval timed out.")
    return None

def get_bitrate(output_file):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
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

# ----------------- Core Functions -----------------

def get_cropping(input_file, res, cq=17):
    settings = PRESET_SETTINGS.get(res)
    if not settings:
        log(f"❌ No settings found for {res}, skipping...")
        return None

    preview_file = f"preview_{res}.mkv"
    snapshots = {
        "original": f"preview_snapshot_{res}_original.jpg",
        "autocrop": f"preview_snapshot_{res}_autocrop.jpg",
        "zoom_5": f"preview_snapshot_{res}_zoom_5.jpg",
        "zoom_10": f"preview_snapshot_{res}_zoom_10.jpg"
    }

    for key, crop in crop_values.items():
        snapshot_file = snapshots[key]
        crop_option = ["--crop", crop] if crop != "auto" else []
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
            "--start-at", "duration:10",
            "--stop-at", "duration:12"
        ] + crop_option

        log(f"\n🎬 Encoding preview snapshot for {res} with crop {key}...")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore")
        for line in process.stdout:
            sub_log(line, end="")  # Write subprocess output to subprocess log area
        process.wait()

        ffmpeg_cmd = [
            "ffmpeg", "-ss", "1", "-i", preview_file, "-vframes", "1", "-y", snapshot_file
        ]
        log(f"\n📸 Capturing snapshot: {snapshot_file}\n")
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            sub_log(line, end="")
        process.wait()
        log(f"📷 Snapshot saved as {snapshot_file}")

    send_previews(snapshots)
    approved_crop = wait_for_approval()
    log("Received cropping approval: " + str(approved_crop))
    return approved_crop

def encode_preview(input_file, res, cq, approved_crop):
    settings = PRESET_SETTINGS.get(res)
    if not settings:
        log(f"❌ No settings found for {res}, skipping...")
        return None

    preview_file = f"preview_{res}.mkv"
    snapshot_file = f"preview_{res}.jpg"
    command = [
        HANDBRAKE_CLI,
        "-i", input_file,
        "-o", preview_file,
        "--crop", crop_values[approved_crop],
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
        "--start-at", "duration:100",
        "--stop-at", "duration:250"
    ]
    log(f"\n🎬 Encoding 60-sec preview for {res} with CQ {cq} and crop {approved_crop}...\n")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",errors="ignore")
    for line in process.stdout:
        sub_log(line, end="")  # subprocess output to subprocess log area
    process.wait()

    bitrate = get_bitrate(preview_file)
    return bitrate

def adjust_cq_for_bitrate(input_file, res, approved_crop):
    min_bitrate, max_bitrate = BITRATE_RANGES[res]
    cq = 17
    while True:
        bitrate = encode_preview(input_file, res, cq, approved_crop)
        if bitrate is None:
            log("⚠️ Failed to encode preview.")
            return None

        log(f"🔍 Bitrate for {res} preview: {bitrate} Kbps")
        if min_bitrate <= bitrate <= max_bitrate:
            log(f"✅ Bitrate is in range ({min_bitrate}-{max_bitrate} Kbps)")
            return int(cq)
        elif bitrate > max_bitrate:
            cq += 2
        elif bitrate < min_bitrate:
            cq -= 2

        if cq < 9 or cq > 27:
            log("⚠️ CQ adjustment out of range. Using default CQ 17.")
            return 17


# --------------------Phase 2--------------------
def extract_audio(input_file, res):
    input_dir = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_folder = os.path.normpath(os.path.join(input_dir, base_name))
    os.makedirs(output_folder, exist_ok=True)

    # Determine the parent directory (one level up from the input file's directory)
    parent_dir = os.path.normpath(os.path.join(os.path.dirname(input_file), ".."))

    # Build the output directory by joining the parent_dir with the resolution folder
    output_dir = os.path.normpath(os.path.join(parent_dir, res))

    # Create the output directory if it doesn't already exist
    os.makedirs(output_dir, exist_ok=True)



    print("Input file:", input_file)
    print("Input dir:", input_dir)
    print("Base name:", base_name)
    print("Output folder:", output_folder)
    print(f"🎵 Detecting audio tracks for {base_name}...")

    # Run eac3to to list tracks
    list_cmd = ["eac3to", input_file]
    result = subprocess.run(list_cmd, capture_output=True, text=True)

    print(result.stdout)  # Show command output
    if result.stderr:
        print(result.stderr)

    # Find audio tracks
    tracks = re.findall(r"(\d+): .*?, (\d+\.\d) channels", result.stdout)
    if not tracks:
        print("⚠️ No audio tracks found!")
        return

    for track_number, channels in tracks:
        track_number = track_number.strip()
        channels = channels.strip()

        if channels in ["5.1", "7.1"]:
            bitrate = "448" if "480p" in input_file or "576p" in input_file else "640"
            output_audio = os.path.normpath(os.path.join(output_folder, f"{base_name}-{bitrate}.ac3"))
            # Construct the normalized output file path using os.path.join
            output_file = os.path.normpath(os.path.join(output_dir, f"{os.path.splitext(base_name)[0]}@{res}-{bitrate}.ac3"))
            extract_cmd = ["eac3to", f'"{input_file}"', f'{track_number}:"{output_file}"', f"-{bitrate}"]
            print("Running command:", " ".join(extract_cmd))  # Debugging
            process = subprocess.run(" ".join(extract_cmd), shell=True, capture_output=True, text=True)

            # Print standard output
            print("STDOUT:\n", process.stdout)

            # Print error output (if any)
            if process.stderr:
                print("STDERR:\n", process.stderr)
                send_webhook_message(f"❌ Audio extraction failed!")

            send_webhook_message(f"✅ Audio extraction complete for {base_name}@{res}")


        else:

            # Ensure the output folder exists

            #os.makedirs(output_folder, exist_ok=True)

            # Normalize and format paths correctly

            temp_audio = os.path.normpath(os.path.join(output_folder, "temp.aac"))

            final_audio = os.path.normpath(os.path.join(output_folder, f"{base_name}.m4a"))
            output_file = os.path.normpath(os.path.join(output_dir, f"{os.path.splitext(base_name)[0]}@{res}.m4a"))

            extract_cmd = f'eac3to "{input_file}" {track_number}:"{temp_audio}"'

            qaac_cmd = f'qaac64 -V 127 -i "{temp_audio}" --no-delay -o "{output_file}"'

            print(f"🎤 Extracting stereo/mono audio track {track_number}...")

            # Run extraction

            process = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)

            print("STDOUT:\n", process.stdout)

            if process.stderr:
                print("STDERR:\n", process.stderr)
                send_webhook_message(f"❌ Audio extraction failed!")

            print("🔄 Converting extracted audio with qaac...")

            # Run qaac conversion

            process = subprocess.run(qaac_cmd, shell=True, capture_output=True, text=True)

            print("STDOUT:\n", process.stdout)

            if process.stderr:
                print("STDERR:\n", process.stderr)

            # Cleanup temp file if extraction succeeded

            if os.path.exists(temp_audio):
                os.remove(temp_audio)

            send_webhook_message(f"✅ Audio extraction complete for {base_name}@{res}")

# --------------------Phase 3--------------------
def extract_subtitles(mkv_path):
    input_dir = os.path.dirname(mkv_path)
    base_name = os.path.splitext(os.path.basename(mkv_path))[0]

    mkv = MKVFile(mkv_path)
    print("MKV merge output:")
    print(mkv)

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

            cmd = ["mkvextract", "tracks", mkv_path, f"{track._track_id}:{output_file}"]
            print("Running command:", " ".join(cmd))
            subprocess.run(cmd)
            send_webhook_message(f"✅ Extracted subtitle track {track._track_id} for {base_name}")
        else:
            log(f"Unable to extract {track._track_id} with codec {track._track_codec} for {base_name}")

    print("Extraction complete!")

def encode_file(input_file, resolutions, status_callback):
    filename = os.path.basename(input_file)
    send_webhook_message(f"Beginning encoding for {filename} @ {resolutions}")
    extract_subtitles(input_file)

    for res in resolutions:
        status_callback(filename, res, "Starting...")
        settings = PRESET_SETTINGS.get(res)
        if not settings:
            log(f"❌ No settings found for {res}, skipping...")
            status_callback(filename, res, "Skipped (no settings)")
            continue
        extract_audio(input_file, res)

        approved_crop = get_cropping(input_file, res)
        if not approved_crop:
            log("⏩ Skipping final encoding due to lack of crop approval.")
            status_callback(filename, res, "Skipped (no crop)")
            continue

        cq = adjust_cq_for_bitrate(input_file, res, approved_crop)
        if cq is None:
            log(f"⏩ Final encoding for {res} was cancelled.")
            status_callback(filename, res, "Cancelled")
            continue
        send_webhook_message(f"Proceeding to Final Encode for {filename}@{res}")

        # Determine the parent directory (one level up from the input file's directory)
        parent_dir = os.path.normpath(os.path.join(os.path.dirname(input_file), ".."))

        # Build the output directory by joining the parent_dir with the resolution folder
        output_dir = os.path.normpath(os.path.join(parent_dir, res))

        # Create the output directory if it doesn't already exist
        #os.makedirs(output_dir, exist_ok=True)

        # Construct the normalized output file path using os.path.join
        output_file = os.path.normpath(os.path.join(output_dir, f"{os.path.splitext(filename)[0]}@{res}.mkv"))

        print("Output file path:", output_file)  # Debugging
        log(f"Output file path: {output_file}")  # Debugging

        command = [
            HANDBRAKE_CLI,
            "-i", input_file,
            "-o", output_file,
            "--crop", crop_values[approved_crop],
            "--encoder", "x264",
            "-a", "none",  # disable audio
            "-s", "none",  # disable subtitles
            "--quality", str(cq),
            "--width", str(settings["width"]),
            "--height", str(settings["height"]),
            "--encoder-preset", "placebo",
            "--encoder-profile", "high",
            "--encoder-level", "4.1",
            "--encopts",
            ("subme=10:deblock=-3,-3:me=umh:merange=32:mbtree=0:"
             "dct-decimate=0:fast-pskip=0:aq-mode=2:aq-strength=1.0:"
             "qcomp=0.60:psy-rd=1.1,0.00")
        ]
        status_callback(filename, res, "Encoding...")
        log(f"\n🚀 Starting final encode for {res}... at CQ {cq}\n")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",errors="ignore")
        for line in process.stdout:
            sub_log(line, end="")
        process.wait()

        if process.returncode == 0:
            log(f"\n✅ Successfully encoded: {output_file}\n")
            completion_bitrate = get_bitrate(output_file)
            send_completion_webhook(completion_bitrate, res, input_file)
            status_callback(filename, res, "Completed")
        else:
            log(f"\n❌ Encoding failed for {res}!\n")
            send_webhook_message(f"Encoding failed for {filename}@{res}")
            status_callback(filename, res, "Failed")

# ----------------- GUI Components -----------------

class TextRedirector(object):
    def __init__(self, widget):
        self.widget = widget
    def write(self, s):
        self.widget.configure(state="normal")
        self.widget.insert("end", s)
        self.widget.see("end")
        self.widget.configure(state="disabled")
    def flush(self):
        pass

def sub_log(message, end="\n"):
    global subprocess_text
    subprocess_text.configure(state="normal")
    subprocess_text.insert("end", message + end)
    subprocess_text.see("end")
    subprocess_text.configure(state="disabled")

def log(message, end="\n"):
    print(message, end=end)

class EncoderGUI:
    def __init__(self, master):
        self.master = master
        master.title("Automation Encoding Queue")

        self.left_frame = Frame(master)
        self.left_frame.pack(side=LEFT, fill="both", expand=True)

        self.file_listbox = Listbox(self.left_frame, width=50)
        self.file_listbox.grid(row=0, column=0, sticky="nsew")

        self.add_button = Button(self.left_frame, text="Select Files", command=self.select_files)
        self.add_button.grid(row=1, column=0, sticky="ew")

        self.start_button = Button(self.left_frame, text="Start Encoding", command=self.start_encoding)
        self.start_button.grid(row=2, column=0, sticky="ew")

        self.status_label = Label(self.left_frame, text="Encoding Status")
        self.status_label.grid(row=3, column=0, sticky="ew")

        self.status_listbox = Listbox(self.left_frame)
        self.status_listbox.grid(row=4, column=0, sticky="nsew")

        self.right_frame = Frame(master)
        self.right_frame.pack(side=RIGHT, fill="both", expand=True)

        self.console_frame = Frame(self.right_frame)
        self.console_frame.pack(fill="both", expand=True)
        self.log_text = Text(self.console_frame, wrap="word", state="disabled", height=15)
        self.log_text.pack(side=LEFT, fill="both", expand=True)
        self.log_scroll = Scrollbar(self.console_frame, command=self.log_text.yview, orient="vertical")
        self.log_scroll.pack(side=RIGHT, fill="y")
        self.log_text.config(yscrollcommand=self.log_scroll.set)

        self.subprocess_frame = Frame(self.right_frame)
        self.subprocess_frame.pack(fill="both", expand=True)
        global subprocess_text
        subprocess_text = Text(self.subprocess_frame, wrap="word", state="disabled", height=10)
        subprocess_text.pack(side=LEFT, fill="both", expand=True)
        self.subproc_scroll = Scrollbar(self.subprocess_frame, command=subprocess_text.yview, orient="vertical")
        self.subproc_scroll.pack(side=RIGHT, fill="y")
        subprocess_text.config(yscrollcommand=self.subproc_scroll.set)

        sys.stdout = TextRedirector(self.log_text)
        sys.stderr = TextRedirector(self.log_text)

        self.file_queue = []
        self.status_entries = {}

        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(4, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

    def update_status_entry(self, filename, res, status):
        key = (filename, res)
        entry_text = f"{filename} - {res} - {status}"
        if key in self.status_entries:
            index = self.status_entries[key]
            self.status_listbox.delete(index)
            self.status_listbox.insert(index, entry_text)
            self.status_entries[key] = index  # Update index in case of shifts
        else:
            index = self.status_listbox.size()
            self.status_listbox.insert(END, entry_text)
            self.status_entries[key] = index
        self.status_listbox.see(END)

    def select_files(self):
        file_paths = filedialog.askopenfilenames(title="Select video files to encode",
                                                 filetypes=[("Video Files", "*.mp4 *.mkv *.avi")])
        for path in file_paths:
            if path not in self.file_queue:
                self.file_queue.append(path)
                self.file_listbox.insert(END, path)

    def start_encoding(self):
        self.add_button.config(state="disabled")
        self.start_button.config(state="disabled")
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        while self.file_queue:
            current_file = self.file_queue.pop(0)
            self.file_listbox.delete(0)
            log(f"\n==================\nProcessing file: {current_file}")
            encodes = determine_encodes(current_file)
            if encodes:
                def status_callback(filename, res, status):
                    self.master.after(0, self.update_status_entry, filename, res, status)
                encode_file(current_file, encodes, status_callback)
            else:
                log(f"⚠️ No valid encode type detected for {current_file} (not WebDL or BluRay).")
        log("✅ All files processed.")
        self.add_button.config(state="normal")
        self.start_button.config(state="normal")

if __name__ == "__main__":
    root = Tk()
    gui = EncoderGUI(root)
    root.mainloop()
