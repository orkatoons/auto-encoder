import cv2
import numpy as np
from flask.cli import load_dotenv
from moviepy import VideoFileClip
import os
import requests
import os

load_dotenv()
# ========== SETTINGS ==========
PTPIMG_API_KEY = os.getenv("API_KEY") # replace with your actual key
UPLOAD_TO_PTPIMG = True  # Set to False to disable upload
# ==============================

def calculate_brightness(image):
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return np.mean(grayscale)

def calculate_contrast(image):
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return grayscale.std()

def is_well_lit(brightness, contrast, brightness_threshold=80, contrast_threshold=50):
    return brightness >= brightness_threshold and contrast >= contrast_threshold

def upload_to_ptpimg(file_path):
    with open(file_path, 'rb') as img_file:
        response = requests.post(
            'https://ptpimg.me/upload.php',
            files={'file-upload[0]': img_file},
            data={'api_key': PTPIMG_API_KEY}
        )
    if response.status_code == 200:
        resp_data = response.json()
        print(resp_data)
        image_code = resp_data[0]['code']
        return f"https://ptpimg.me/{image_code}.jpg"
    else:
        print(f"[ERROR] Upload failed for {file_path} - Status: {response.status_code}")
        return None

def extract_well_lit_screenshots(video_path, output_dir, num_screenshots=3, max_attempts=10, retry_gap=60):
    clip = VideoFileClip(video_path)
    duration = clip.duration
    segment_length = duration / num_screenshots
    best_screenshots = []

    os.makedirs(output_dir, exist_ok=True)

    for i in range(num_screenshots):
        segment_midpoint = (i + 0.5) * segment_length
        best_brightness = 0
        best_contrast = 0
        best_frame = None

        for attempt in range(max_attempts):
            current_time = segment_midpoint + attempt * retry_gap
            if current_time >= duration:
                break

            try:
                frame = clip.get_frame(current_time)
            except Exception as e:
                print(f"[ERROR] Failed to grab frame at {current_time:.2f}s: {e}")
                continue

            brightness = calculate_brightness(frame)
            contrast = calculate_contrast(frame)

            print(f"[INFO] Attempt {attempt + 1} - Time: {current_time:.2f}s - Brightness: {brightness:.2f}, Contrast: {contrast:.2f}")

            if is_well_lit(brightness, contrast):
                output_path = os.path.join(output_dir, f"screenshot_{i + 1}.png")
                cv2.imwrite(output_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                print(f"[INFO] Well-lit screenshot saved at: {output_path}")
                best_screenshots.append(output_path)
                break
            elif brightness + contrast > best_brightness + best_contrast:
                best_brightness = brightness
                best_contrast = contrast
                best_frame = frame

        if not best_screenshots or len(best_screenshots) < i + 1:
            output_path = os.path.join(output_dir, f"screenshot_{i + 1}.png")
            if best_frame is not None:
                cv2.imwrite(output_path, cv2.cvtColor(best_frame, cv2.COLOR_RGB2BGR))
                print(f"[WARNING] Saved best available frame at: {output_path}")
                best_screenshots.append(output_path)
            else:
                print(f"[ERROR] Could not save screenshot for segment {i + 1}")

    clip.close()
    print(f"[INFO] Screenshot extraction completed. Total screenshots: {len(best_screenshots)}")

    if UPLOAD_TO_PTPIMG:
        print("\n[INFO] Uploading screenshots to PTPImg...")
        for path in best_screenshots:
            url = upload_to_ptpimg(path)
            if url:
                print(f"[BBCode] [img]{url}[/img]")
            else:
                print(f"[UPLOAD FAILED] {path}")


# ======= Example usage =======
video_path = r'W:\Encodes\Final N Fool\720p\Fool.N.Final.0000.720p.WEB-DL.x264-HANDJOB.mkv'
output_dir = 'screenshots'
extract_well_lit_screenshots(video_path, output_dir)
