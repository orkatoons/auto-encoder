from flask import Flask, request, jsonify
from auto_encoder import start_encoding
from multiprocessing import Process
import os
import json
import glob
import io
import sys
from datetime import datetime
from ptp_routes import ptp_bp, handle_ptp_download, get_ptp_movies
import subprocess
import threading
import requests
import shlex

app = Flask(__name__)

# Register the PTP blueprint with a URL prefix
app.register_blueprint(ptp_bp, url_prefix='/ptp')

job_id = None
filename = None
job_store = {}
STATUS_FILE = 'status.json'
LOG_DIR = 'encode_logs'
CONFIG_FILE = 'config.json'

def initialize_status_file():
    """Initialize the status.json file if it doesn't exist or is empty"""
    if not os.path.exists(STATUS_FILE) or os.path.getsize(STATUS_FILE) == 0:
        with open(STATUS_FILE, 'w') as f:
            json.dump({}, f)

def update_status(job_id, status_data):
    """Update the status.json file with new status data"""
    try:
        # Initialize file if needed
        initialize_status_file()
        
        # Read current status
        with open(STATUS_FILE, 'r') as f:
            try:
                current_status = json.load(f)
            except json.JSONDecodeError:
                current_status = {}
        
        # Update status for this job
        current_status[job_id] = status_data
        
        # Write back to file
        with open(STATUS_FILE, 'w') as f:
            json.dump(current_status, f, indent=2)
    except Exception as e:
        print(f"Error updating status file: {str(e)}")

def get_directory_structure(path):
    """
    Returns a dictionary containing the directory structure.
    Handles Windows paths correctly.
    """
    structure = []
    
    # Convert Windows path to proper format
    path = os.path.normpath(path)
    
    try:
        # List all items in the directory
        items = os.listdir(path)
        
        # Check if current directory has approval files
        has_approval = any(item.lower() in ['approval.txt', 'upload.txt'] for item in items)
        if has_approval:
            print(f"Found approval file in directory: {path}")
        
        for item in items:
            full_path = os.path.join(path, item)
            
            # Skip hidden files and directories
            if item.startswith('.'):
                continue
                
            if os.path.isdir(full_path):
                # Recursively get subdirectory structure
                sub_structure = get_directory_structure(full_path)
                
                # Check if any subdirectory has approval
                sub_has_approval = any(
                    sub_item.get('has_approval', False) 
                    for sub_item in sub_structure
                )
                
                if sub_has_approval:
                    print(f"Subdirectory has approval: {full_path}")
                
                dir_info = {
                    'name': item,
                    'type': 'directory',
                    'path': full_path,
                    'files': sub_structure,
                    'has_approval': has_approval or sub_has_approval
                }
                
                if dir_info['has_approval']:
                    print(f"Directory marked as approved: {full_path}")
                
                structure.append(dir_info)
            else:
                # Only include video files
                if item.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.txt')):
                    structure.append({
                        'name': item,
                        'type': 'file',
                        'path': full_path
                    })
    except Exception as e:
        print(f"Error reading directory {path}: {str(e)}")
        return []
        
    return structure

@app.route('/encode/directories', methods=['GET'])
def list_directories():
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Path parameter is required'
            }), 400

        structure = get_directory_structure(path)
        return jsonify({
            'status': 'success',
            'data': [{
                'name': os.path.basename(path),
                'path': path,
                'type': 'directory',
                'files': structure
            }]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def ensure_log_directory():
    """Ensure the log directory exists"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def get_log_file_path(job_id):
    """Get the path for a job's log file"""
    return os.path.join(LOG_DIR, f'encode_{job_id}.log')

def redirect_output_to_file(job_id):
    """Redirect stdout and stderr to a log file"""
    log_file = get_log_file_path(job_id)
    # Use UTF-8 encoding with error handling for the log file
    sys.stdout = open(log_file, 'a', encoding='utf-8', errors='replace', buffering=1)
    sys.stderr = sys.stdout

@app.route('/encode/start', methods=['POST'])
def start_encode():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    job_id = data.get('jobid')
    filename = data.get('filename')

    if not job_id or not filename:
        return jsonify({'error': 'Missing job_id or filename'}), 400

    print(f"Received job_id: {job_id}, filename: {filename}")
    
    # Import the determine_encodes function
    from auto_encoder import determine_encodes
    
    # Get the resolutions we'll actually encode
    resolutions = determine_encodes(filename)
    
    # Initialize status for this job with only the resolutions we'll encode
    initial_status = {
        'filename': filename,
        'resolutions': {
            res: {'status': 'Starting', 'progress': '0'}
            for res in resolutions
        },
        'updated_at': None
    }
    update_status(job_id, initial_status)
    
    # Ensure log directory exists
    ensure_log_directory()
    
    # Create a new process with output redirection
    p = Process(target=run_encoding_with_logging, args=(filename, job_id))
    p.start()
    job_store[job_id] = p

    return jsonify({'status': 'started', 'job_id': job_id, 'filename': filename}), 200

def run_encoding_with_logging(filename, job_id):
    """Run the encoding process with logging"""
    try:
        # Redirect output to log file
        redirect_output_to_file(job_id)
        # Run the encoding
        start_encoding(filename, job_id)
    finally:
        # Restore stdout/stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

@app.route('/encode/status/<job_id>', methods=['GET'])
def get_encoding_status(job_id):
    try:
        # Initialize status file if needed
        initialize_status_file()
        
        # Read status file
        with open(STATUS_FILE, 'r') as f:
            try:
                status_data = json.load(f)
                if job_id in status_data:
                    # Get the last 20 lines of logs if they exist
                    log_file = get_log_file_path(job_id)
                    log_lines = []
                    if os.path.exists(log_file):
                        with open(log_file, 'r', encoding='utf-8', errors='replace') as log_f:
                            log_lines = log_f.readlines()[-20:]  # Get last 20 lines
                    
                    status_data[job_id]['log_output'] = ''.join(log_lines)
                    return jsonify(status_data[job_id]), 200
                else:
                    return jsonify({
                        'filename': None,
                        'resolutions': {},
                        'updated_at': None,
                        'log_output': ''
                    }), 200
            except json.JSONDecodeError:
                return jsonify({
                    'filename': None,
                    'resolutions': {},
                    'updated_at': None,
                    'log_output': ''
                }), 200
    except Exception as e:
        print(f"Error reading status file: {str(e)}")
        return jsonify({
            'filename': None,
            'resolutions': {},
            'updated_at': None,
            'log_output': ''
        }), 200

@app.route('/encode/stop', methods=['POST'])
def stop_encoding():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No job_id provided'}), 400

    job_id = data.get('jobid')
    if job_id in job_store:
        p = job_store[job_id]
        p.terminate()
        del job_store[job_id]
        
        # Update status to show stopped
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r') as f:
                    status_data = json.load(f)
                if job_id in status_data:
                    status_data[job_id]['resolutions'] = {
                        res: {'status': 'Stopped', 'progress': '0'}
                        for res in status_data[job_id]['resolutions']
                    }
                    with open(STATUS_FILE, 'w') as f:
                        json.dump(status_data, f, indent=2)
            except Exception as e:
                print(f"Error updating status for stopped job: {str(e)}")
        
        return jsonify({'status': 'stopped', 'job_id': job_id}), 200
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/encode/logs/<job_id>', methods=['GET'])
def get_encoding_logs(job_id):
    """Get the logs for a specific encoding job"""
    try:
        log_file = get_log_file_path(job_id)
        if not os.path.exists(log_file):
            return jsonify({'error': 'Log file not found'}), 404
            
        with open(log_file, 'r') as f:
            logs = f.read()
            
        return jsonify({
            'status': 'success',
            'logs': logs
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def load_config():
    """Load the config file if it exists, create with defaults if it doesn't"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        default_config = {
            "baseDirectories": []
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    """Save the config to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@app.route('/encode/directories/config', methods=['GET'])
def get_config():
    """Get the current config"""
    try:
        config = load_config()
        return jsonify({
            'status': 'success',
            'data': config['baseDirectories']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/encode/directories/config/add', methods=['POST'])
def add_directory():
    """Add a new directory to config"""
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'path' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Name and path are required'
            }), 400

        config = load_config()
        
        # Check if directory already exists
        if any(dir['path'] == data['path'] for dir in config['baseDirectories']):
            return jsonify({
                'status': 'error',
                'message': 'Directory already exists in config'
            }), 400

        # Validate path exists and is accessible
        path = os.path.normpath(data['path'])
        if not os.path.exists(path):
            return jsonify({
                'status': 'error',
                'message': f'Directory "{path}" does not exist'
            }), 400

        try:
            os.listdir(path)
        except PermissionError:
            return jsonify({
                'status': 'error',
                'message': f'Permission denied accessing directory "{path}"'
            }), 400
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error accessing directory "{path}": {str(e)}'
            }), 400

        # Add new directory
        config['baseDirectories'].append({
            'name': data['name'],
            'path': path
        })
        save_config(config)

        return jsonify({
            'status': 'success',
            'data': config['baseDirectories']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/encode/directories/config/update', methods=['PUT'])
def update_directory():
    """Update an existing directory in config"""
    try:
        data = request.get_json()
        if not data or 'oldPath' not in data or (not data.get('newName') and not data.get('newPath')):
            return jsonify({
                'status': 'error',
                'message': 'Old path and at least one new value are required'
            }), 400

        config = load_config()
        
        # Find directory to update
        dir_index = next((i for i, dir in enumerate(config['baseDirectories']) 
                         if dir['path'] == data['oldPath']), None)
        
        if dir_index is None:
            return jsonify({
                'status': 'error',
                'message': 'Directory not found in config'
            }), 404

        # If new path is provided, validate it
        if data.get('newPath'):
            path = os.path.normpath(data['newPath'])
            if not os.path.exists(path):
                return jsonify({
                    'status': 'error',
                    'message': f'Directory "{path}" does not exist'
                }), 400

            try:
                os.listdir(path)
            except PermissionError:
                return jsonify({
                    'status': 'error',
                    'message': f'Permission denied accessing directory "{path}"'
                }), 400
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Error accessing directory "{path}": {str(e)}'
                }), 400

            config['baseDirectories'][dir_index]['path'] = path

        # Update name if provided
        if data.get('newName'):
            config['baseDirectories'][dir_index]['name'] = data['newName']

        save_config(config)

        return jsonify({
            'status': 'success',
            'data': config['baseDirectories']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/encode/directories/config/delete', methods=['DELETE'])
def delete_directory():
    """Delete a directory from config"""
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400

        config = load_config()
        
        # Find directory to delete
        dir_index = next((i for i, dir in enumerate(config['baseDirectories']) 
                         if dir['path'] == data['path']), None)
        
        if dir_index is None:
            return jsonify({
                'status': 'error',
                'message': 'Directory not found in config'
            }), 404

        # Remove directory
        config['baseDirectories'].pop(dir_index)
        save_config(config)

        return jsonify({
            'status': 'success',
            'data': config['baseDirectories']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_directory_contents(path, max_depth=3, current_depth=0):
    """
    Returns directory contents up to 3 levels deep.
    Excludes hidden folders and only includes specified file types.
    """
    if current_depth > max_depth:
        return []
        
    try:
        items = os.listdir(path)
        contents = []
        
        for item in items:
            # Skip hidden items
            if item.startswith('.'):
                continue
                
            full_path = os.path.join(path, item)
            
            if os.path.isdir(full_path):
                # For directories, get their contents if we haven't reached max depth
                sub_contents = get_directory_contents(full_path, max_depth, current_depth + 1) if current_depth < max_depth else []
                contents.append({
                    'name': item,
                    'path': full_path,
                    'type': 'directory',
                    'contents': sub_contents,
                    'items': len(sub_contents),
                    'depth': current_depth,
                    'has_more': current_depth == max_depth - 1  # Set has_more if we're at the second level
                })
            elif item.lower().endswith(('.txt', '.mkv', '.mp4')):
                contents.append({
                    'name': item,
                    'path': full_path,
                    'type': 'file'
                })
                
        return contents
    except Exception as e:
        print(f"Error reading directory {path}: {str(e)}")
        return []

@app.route('/encode/directories/browse', methods=['GET'])
def browse_directory():
    try:
        print("[FLASK] Received browse request")
        path = request.args.get('path', '')
        print(f"[FLASK] Path requested: {path}")
        
        # If no path provided, return all drives
        if not path:
            import win32api
            import win32file
            drives = []
            for drive in win32api.GetLogicalDriveStrings().split('\000')[:-1]:
                try:
                    drive_type = win32file.GetDriveType(drive)
                    drives.append({
                        'name': drive,
                        'path': drive,
                        'type': 'directory',
                        'isDrive': True,
                        'driveType': drive_type,
                        'contents': get_directory_contents(drive, max_depth=3)  # Load 3 levels for drives
                    })
                except Exception as e:
                    print(f"[FLASK] Error accessing drive {drive}: {str(e)}")
                    drives.append({
                        'name': drive,
                        'path': drive,
                        'type': 'directory',
                        'isDrive': True,
                        'driveType': drive_type,
                        'inaccessible': True
                    })
            print(f"[FLASK] Returning {len(drives)} drives")
            return jsonify({
                'status': 'success',
                'data': drives
            })
            
        # For specific paths, return contents up to 3 levels deep
        contents = get_directory_contents(path, max_depth=3)
        print(f"[FLASK] Returning {len(contents)} items for path {path}")
        return jsonify({
            'status': 'success',
            'data': contents
        })
    except Exception as e:
        print(f"[FLASK] Error in browse_directory: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/encode/directories/load_more', methods=['GET'])
def load_more_contents():
    try:
        path = request.args.get('path', '')
        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Path is required'
            }), 400

        print(f"[FLASK] Loading more contents for path: {path}")
        # When loading more, always load 3 levels deep from the requested path
        contents = get_directory_contents(path, max_depth=3)
        print(f"[FLASK] Returning {len(contents)} additional items for path {path}")
        return jsonify({
            'status': 'success',
            'data': contents
        })
    except Exception as e:
        print(f"[FLASK] Error in load_more_contents: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/ptp/scrape', methods=['POST'])
def start_ptp_scrape():
    try:
        data = request.get_json()
        if not data:
            print("❌ No data provided in request body")
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        page_offset = data.get('page_offset')
        total_pages = data.get('total_pages')
        mode = data.get('mode', 'Movies')

        if not page_offset or not total_pages:
            print("❌ Missing page_offset or total_pages")
            return jsonify({'status': 'error', 'message': 'page_offset and total_pages are required'}), 400

        try:
            page_offset = int(page_offset)
            total_pages = int(total_pages)
        except ValueError:
            print("❌ Non-integer values for page_offset or total_pages")
            return jsonify({'status': 'error', 'message': 'page_offset and total_pages must be integers'}), 400

        if page_offset <= 0 or total_pages <= 0:
            print("❌ Invalid values: page_offset and total_pages must be > 0")
            return jsonify({'status': 'error', 'message': 'page_offset and total_pages must be greater than 0'}), 400

        def parse_movie_block(movie_block):
            try:
                # Split into movie and its torrents
                parts = movie_block.strip().split('~~')
                if not parts:
                    print("⚠️ Empty block")
                    return None

                # First part is the movie info
                movie_info = parts[0].strip('~')
                if not movie_info:
                    print("⚠️ No movie info found")
                    return None

                print(f"\n🔎 Processing movie block")
                
                # Process all torrents for this movie
                best_torrent = None
                best_seeders = 0
                
                for torrent in parts[1:]:  # Skip the first part (movie info)
                    if not torrent.strip():
                        continue
                        
                    print("\n📋 Processing torrent...")
                    torrent_parts = torrent.strip().split('||')
                    if len(torrent_parts) < 6:
                        print("⚠️ Invalid torrent format")
                        continue

                    # Extract torrent information
                    source = torrent_parts[1]
                    resolution = torrent_parts[2]
                    release_name = torrent_parts[3]
                    seeders = int(torrent_parts[4])
                    link = torrent_parts[5]

                    print(f"🔍 Checking torrent: {source} | {resolution} | {release_name} | {seeders}")
                    
                    # Initialize check counter
                    total_checks = 0
                    passed_checks = 0
                    
                    # Check 1: Seeders
                    total_checks += 1
                    print(f"\nCheck 1: Seeders Check")
                    print(f"Looking for: seeders > 0")
                    print(f"Found: {seeders} seeders")
                    if seeders <= 0:
                        print("❌ Check 1: Failed - No seeders")
                        continue
                    else:
                        print("✅ Check 1: Passed - Has seeders")
                        passed_checks += 1

                    # Check 2: UHD/2160p
                    total_checks += 1
                    print(f"\nCheck 2: UHD Check")
                    print(f"Looking for: No '2160p' in resolution")
                    print(f"Found: Resolution contains '{resolution}'")
                    if '2160p' in resolution:
                        print("❌ Check 2: Failed - Contains 2160p")
                        continue
                    else:
                        print("✅ Check 2: Passed - No 2160p")
                        passed_checks += 1

                    # Check 3: Valid Source
                    total_checks += 1
                    valid_sources = {'DVD', 'Blu-ray', 'Remux', 'BD25', 'BD50'}
                    print(f"\nCheck 3: Source Validation")
                    print(f"Looking for: One of {valid_sources}")
                    print(f"Found: Source is '{source}'")
                    if not any(valid in source for valid in valid_sources):
                        print("❌ Check 3: Failed - Invalid source")
                        continue
                    else:
                        print("✅ Check 3: Passed - Valid source")
                        passed_checks += 1

                    # Check 4: DVD Format with VOB IFO
                    total_checks += 1
                    print(f"\nCheck 4: DVD Format Check")
                    print(f"Looking for: If DVD5/DVD9, must have 'VOB IFO'")
                    print(f"Found: Source '{source}' with release '{release_name}'")
                    if source.strip() in {'DVD5', 'DVD9'} and 'VOB IFO' not in release_name:
                        print("❌ Check 4: Failed - DVD without VOB IFO")
                        continue
                    else:
                        print("✅ Check 4: Passed - DVD format valid")
                        passed_checks += 1

                    # Check 5: Remux Format
                    total_checks += 1
                    print(f"\nCheck 5: Remux Format Check")
                    print(f"Looking for: 'Remux' in source or release name")
                    print(f"Found: Source '{source}' with release '{release_name}'")
                    if source.strip() == 'Remux' or 'Remux' in release_name:
                        source = 'Remux'
                        print("✅ Check 5: Passed - Remux format detected")
                    else:
                        print("✅ Check 5: Passed - Not a Remux")
                    passed_checks += 1

                    # Check 6: HD Resolution
                    total_checks += 1
                    resolutions_hd = {'720p', '1080p'}
                    print(f"\nCheck 6: HD Resolution Check")
                    print(f"Looking for: One of {resolutions_hd}")
                    print(f"Found: Resolution '{resolution}'")
                    hd_found = False
                    for hd in resolutions_hd:
                        if hd in resolution:
                            hd_found = True
                    if hd_found:
                        print("✅ Check 6: Passed - HD resolution found")
                    else:
                        print("❌ Check 6: Failed - No HD resolution")
                    passed_checks += 1

                    # Check 7: SD Resolution
                    total_checks += 1
                    resolutions_sd = {'480p', '576p'}
                    print(f"\nCheck 7: SD Resolution Check")
                    print(f"Looking for: One of {resolutions_sd}")
                    print(f"Found: Resolution '{resolution}'")
                    sd_found = False
                    for sd in resolutions_sd:
                        if sd in resolution:
                            sd_found = True
                    if sd_found:
                        print("✅ Check 7: Passed - SD resolution found")
                    else:
                        print("❌ Check 7: Failed - No SD resolution")
                    passed_checks += 1

                    print(f"\n📊 Torrent Check Summary: {passed_checks}/{total_checks} checks passed")

                    # If this torrent passed all checks and has more seeders than our current best
                    if passed_checks == total_checks and seeders > best_seeders:
                        best_torrent = {
                            'Name': release_name,
                            'Source': source.strip(),
                            'Standard Definition': None if not sd_found else '480p, 576p',
                            'High Definition': None if not hd_found else resolution,
                            'Link': link,
                            'date_added': datetime.now().isoformat()
                        }
                        best_seeders = seeders
                        print(f"🌟 New best torrent found with {seeders} seeders!")

                if best_torrent:
                    print(f"\n✅ Movie accepted with best torrent:")
                    print(f"📝 Name: {best_torrent['Name']}")
                    print(f"📝 Source: {best_torrent['Source']}")
                    print(f"📝 Resolution: {best_torrent['High Definition']}")
                    return best_torrent
                else:
                    print("❌ No eligible torrents found for this movie")
                    return None

            except Exception as e:
                print(f"❌ Error parsing block: {e}")
                return None

        # Load existing movies
        existing_movies = []
        try:
            with open('output.json', 'r', encoding='utf-8') as f:
                existing_movies = json.load(f)
            print(f"📁 Loaded {len(existing_movies)} existing movies")
        except Exception as e:
            print(f"⚠️ Could not load existing output.json: {e}")
            existing_movies = []

        # Create a set of existing movie names for quick lookup
        existing_movie_names = {movie['Name'] for movie in existing_movies}
        print(f"📊 Found {len(existing_movie_names)} unique existing movies")

        # Dictionary to store the best torrent for each movie
        new_movies = {}
        
        for page in range(page_offset, page_offset + total_pages):
            print(f"\n📄 Processing page {page}")
            cmd = f'ptp search "" -p {page} --movie-format "~{{{{Title}}}} [{{{{Year}}}}] by {{{{Directors}}}}" --torrent-format "~~||{{{{Source}}}}||{{{{Resolution}}}}||{{{{ReleaseName}}}}||{{{{Seeders}}}}||{{{{Link}}}}"'
            args = shlex.split(cmd)
            print(f"▶️ Running: {cmd}")
            try:
                result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if result.stderr:
                    print(f"⚠️ CLI stderr: {result.stderr.strip()}")
                output = result.stdout.strip()
                if not output:
                    print("⚠️ No output returned from CLI")
                    continue

                # Split into movie blocks
                movie_blocks = output.split('~')
                for block in movie_blocks:
                    if not block.strip():
                        continue
                    parsed = parse_movie_block('~' + block.strip())
                    if parsed:
                        movie_name = parsed['Name']
                        # Only add if we haven't seen this movie before
                        if movie_name not in existing_movie_names and movie_name not in new_movies:
                            print(f"➕ Adding new movie: {movie_name}")
                            new_movies[movie_name] = parsed
                            existing_movie_names.add(movie_name)
                        else:
                            print(f"🔁 Skipping duplicate movie: {movie_name}")

            except Exception as e:
                print(f"❌ Failed to run command on page {page}: {e}")

        # Combine existing and new movies
        all_movies = existing_movies + list(new_movies.values())
        
        try:
            with open('output.json', 'w', encoding='utf-8') as f:
                json.dump(all_movies, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved output.json with {len(all_movies)} total movies")
            print(f"📊 Added {len(new_movies)} new movies")
        except Exception as e:
            print(f"❌ Failed to save output.json: {e}")

        return jsonify({
            'status': 'success', 
            'added': len(new_movies), 
            'total': len(all_movies)
        })

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/ptp/movies', methods=['GET'])
def handle_movies():
    try:
        return get_ptp_movies()
    except Exception as e:
        print(f"[FLASK] Error in handle_movies route: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/ptp/download', methods=['POST'])
def handle_download():
    try:
        print("[FLASK] Received download request")
        data = request.get_json()
        print(f"[FLASK] Request data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        result = handle_ptp_download(data)
        status_code = 200 if result['status'] == 'success' else 400
        return jsonify(result), status_code
    except Exception as e:
        print(f"[FLASK] Error in handle_download route: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Initialize status file on startup
    initialize_status_file()
    app.run(host='0.0.0.0', port=5001, debug=True)

