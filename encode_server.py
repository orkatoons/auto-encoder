from flask import Flask, request, jsonify
from auto_encoder import start_encoding
from multiprocessing import Process
import os
import json
import glob

app = Flask(__name__)

job_id = None
filename = None
job_store = {}
STATUS_FILE = 'status.json'

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
        
        for item in items:
            full_path = os.path.join(path, item)
            
            # Skip hidden files and directories
            if item.startswith('.'):
                continue
                
            if os.path.isdir(full_path):
                # Recursively get subdirectory structure
                sub_structure = get_directory_structure(full_path)
                structure.append({
                    'name': item,
                    'type': 'directory',
                    'path': full_path,
                    'files': sub_structure
                })
            else:
                # Only include video files
                if item.lower().endswith(('.mkv', '.mp4', '.avi', '.mov')):
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
        # Base directory for encodes
        base_dir = "C:/Users/thevi/Videos"
        
        # Get the directory structure
        structure = get_directory_structure(base_dir)
        
        return jsonify({
            'status': 'success',
            'data': structure
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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
    
    p = Process(target=start_encoding, args=(filename, job_id))
    p.start()
    job_store[job_id] = p

    return jsonify({'status': 'started', 'job_id': job_id, 'filename': filename}), 200

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
                    return jsonify(status_data[job_id]), 200
                else:
                    return jsonify({
                        'filename': None,
                        'resolutions': {},
                        'updated_at': None
                    }), 200
            except json.JSONDecodeError:
                return jsonify({
                    'filename': None,
                    'resolutions': {},
                    'updated_at': None
                }), 200
    except Exception as e:
        print(f"Error reading status file: {str(e)}")
        return jsonify({
            'filename': None,
            'resolutions': {},
            'updated_at': None
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

if __name__ == '__main__':
    # Initialize status file on startup
    initialize_status_file()
    app.run(host='0.0.0.0', port=5001, debug=True)

