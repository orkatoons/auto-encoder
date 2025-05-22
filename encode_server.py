from flask import Flask, request, jsonify
from auto_encoder import start_encoding
from multiprocessing import Process
import os
import json
import glob
import io
import sys
from datetime import datetime

app = Flask(__name__)

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

if __name__ == '__main__':
    # Initialize status file on startup
    initialize_status_file()
    app.run(host='0.0.0.0', port=5001, debug=True)

