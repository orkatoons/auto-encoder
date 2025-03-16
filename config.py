import cv2
import numpy as np
import subprocess
import os

def make_even(value):
    return value if value % 2 == 0 else value + 1

def detect_black_bars(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    return x, y, w, h

def extract_frame(input_file, time_offset, frame_file):
    command = [
        'ffmpeg', '-ss', str(time_offset), '-i', input_file,
        '-frames:v', '1', '-q:v', '2', frame_file
    ]
    subprocess.run(command, check=True)

def encode_segment(input_file, output_file, crop_values, start_time, duration):
    command = [
        'HandBrakeCLI', '-i', input_file, '-o', output_file,
        '--crop', crop_values,
        '--start-at', f'seconds:{start_time}',
        '--stop-at', f'seconds:{duration}',
        '--encoder', 'x264', '--quality', '20',
        '--width', '1280', '--height', '720',
        '--encoder-preset', 'placebo',
        '--encoder-profile', 'high',
        '--encoder-level', '4.1',
        '--encopts',
        'subme=10:deblock=-3,-3:me=umh:merange=32:mbtree=0:'
        'dct-decimate=0:fast-pskip=0:aq-mode=2:aq-strength=1.0:'
        'qcomp=0.60:psy-rd=1.1,0.00'
    ]
    subprocess.run(command, check=True)

def process_video(input_file, start_time, duration, original_image, cropped_image):
    temp_frame = 'temp_frame.png'
    extract_frame(input_file, start_time, temp_frame)

    frame = cv2.imread(temp_frame)
    x, y, w, h = detect_black_bars(frame)

    # Calculate final crop values
    top_crop = y
    bottom_crop = frame.shape[0] - (y + h)
    left_crop = x
    right_crop = frame.shape[1] - (x + w)

    # Ensure all crop values are even
    top_crop = make_even(top_crop)
    bottom_crop = make_even(bottom_crop)
    left_crop = make_even(left_crop)
    right_crop = make_even(right_crop)

    crop_values = f'{top_crop}:{bottom_crop}:{left_crop}:{right_crop}'

    preview_video = 'preview.mp4'
    encode_segment(input_file, preview_video, crop_values, start_time, duration)

    extract_frame(input_file, start_time + duration / 2, original_image)
    extract_frame(preview_video, duration / 2, cropped_image)

    print(f'Cropping Values:')
    print(f'Top: {top_crop} pixels')
    print(f'Bottom: {bottom_crop} pixels')
    print(f'Left: {left_crop} pixels')
    print(f'Right: {right_crop} pixels')
    os.remove(temp_frame)
    os.remove(preview_video)

if __name__ == '__main__':
    input_file = r"W:\Encodes\Bhag Bhaagam\source\Bhagam.Bhag.2006.BluRay.1080p.DTS-HD.MA.5.1.AVC.REMUX-FraMeSToR.mkv"
    start_time = 1342  # Start at 30 seconds
    duration = 2     # Encode 2 seconds
    original_image = 'original_preview.jpg'
    cropped_image = 'cropped_preview.jpg'

    process_video(input_file, start_time, duration, original_image, cropped_image)

