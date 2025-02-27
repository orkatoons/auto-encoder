# HandBrake Encoding Automation

## Overview
This script automates the encoding process using HandBrakeCLI. It includes functions for cropping, bitrate adjustment, encoding, and subtitle extraction. It also integrates with a local Flask server for approval handling and a Discord webhook for notifications.

## Requirements
### Software Dependencies
- **Python 3.x**
- **HandBrakeCLI** (Path: `C:\Program Files (x86)\HandBrakeCLI-1.9.1-win-x86_64\HandBrakeCLI.exe`)
- **FFmpeg** (For bitrate analysis and snapshot generation)
- **MKVToolNix** (For subtitle extraction)
- **Flask** (Local server for preview approvals)

### Python Packages
Install the required Python packages using:
```sh
pip install -r requirements.txt
```

## Configuration
Modify the following settings as per your environment:
```python
FLASK_SERVER_URL = "http://localhost:5000"
HANDBRAKE_CLI = r"C:\Program Files (x86)\HandBrakeCLI-1.9.1-win-x86_64\HandBrakeCLI.exe"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your_webhook_url"
```

## Features
1. **Determine Encodes**
   - Detects if the file is a WEB-DL or Blu-ray rip.
   - WEB-DL: Encodes only 1080p, 720p.
   - Blu-ray: Encodes 1080p, 720p, 576p, and 480p.

2. **Preview Generation & Approval System**
   - Generates previews with different crop values.
   - Uploads snapshots to a Discord server for approval.
   - Waits for manual approval before proceeding.

3. **Bitrate Testing & CQ Adjustment**
   - Runs a 60-second test encode.
   - Analyzes the resulting bitrate using FFmpeg.
   - Adjusts the Constant Quality (CQ) value dynamically until bitrate falls within an acceptable range.

4. **Final Encoding**
   - Uses the approved crop settings.
   - Encodes the full movie at the optimal CQ.

5. **Subtitle Extraction**
   - Uses MKVToolNix to extract subtitle tracks from MKV files.

6. **Discord Notifications**
   - Sends encoding completion updates to a Discord channel.

## Usage
1. **Run Flask Approval Server**
   ```sh
   python server.py
   ```

2. **Run Encoding Script**
   ```sh
   python auto_encode.py
   ```

3. **Run Discord Bot**
   ```sh
   python bot.py
   ```

## File Processing Flow
1. Select file(s) using GUI.
2. Determine encoding resolutions.
3. Generate preview snapshots for cropping approval.
4. Send previews to Flask server.
5. Wait for manual approval.
6. Run a 60-second preview encode to determine bitrate.
7. Adjust CQ dynamically to meet bitrate requirements.
8. Encode the full movie using optimized settings.
9. Extract subtitles (if applicable).
10. Notify via Discord webhook.

## Error Handling & Logging
- Logs encoding process output.
- Handles missing HandBrakeCLI or FFmpeg errors.
- Timeout mechanism for approvals (12 hours).
- Ensures CQ values remain within a reasonable range (10-25).

## Notes
- Make sure Flask is running before starting an encode.
- Keep HandBrakeCLI, FFmpeg, and MKVToolNix updated for best performance.

