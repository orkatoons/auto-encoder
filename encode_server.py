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

@app.route('/encode/directories/validate', methods=['POST'])
def validate_directory():
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Path parameter is required'
            }), 400

        path = data['path']
        path = os.path.normpath(path)
        
        # Check if path exists and is accessible
        if not os.path.exists(path):
            return jsonify({
                'status': 'error',
                'message': f'Directory "{path}" does not exist'
            }), 400
            
        # Try to list directory contents to verify access
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

        return jsonify({
            'status': 'success',
            'message': 'Directory is valid and accessible'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/encode/directories', methods=['GET'])
def list_directories():
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({
                'status': 'error',
                'message': 'Path parameter is required'
            }), 400

        # Normalize the path
        path = os.path.normpath(path)
        
        # Validate path exists and is accessible
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

if __name__ == '__main__':
    # Initialize status file on startup
    initialize_status_file()
    app.run(host='0.0.0.0', port=5001, debug=True)

