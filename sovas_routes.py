from flask import Blueprint, jsonify, request
import json
import os
import subprocess
import threading
import sys

sovas_bp = Blueprint('sovas', __name__)

def initialize_sovas_scraper(start_page, num_pages):
    """
    Initialize the SOVAS scraper with the given parameters.
    Runs the scraper in a separate thread to avoid blocking the API.
    """
    try:
        # Get the absolute path to main.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(current_dir, 'SOVAS Scraper', 'main.py')
        
        # Verify the script exists
        if not os.path.exists(main_script):
            return {
                'status': 'error',
                'message': f'Scraper script not found at {main_script}'
            }
        
        # Run the scraper in a separate thread to avoid blocking
        def run_scraper():
            try:
                print(f"🚀 Starting SOVAS scraper: pages {start_page} to {start_page + num_pages - 1}")
                subprocess.run([
                    sys.executable,
                    main_script,
                    str(start_page),
                    str(num_pages)
                ], check=True)
                print(f"✅ SOVAS scraper completed: pages {start_page} to {start_page + num_pages - 1}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Error running SOVAS scraper: {str(e)}")
            except Exception as e:
                print(f"❌ Exception in SOVAS scraper: {str(e)}")

        thread = threading.Thread(target=run_scraper)
        thread.daemon = True  # Thread will exit when main process exits
        thread.start()
        
        return {
            'status': 'success',
            'message': f'SOVAS scraper initialized successfully. Processing pages {start_page} to {start_page + num_pages - 1}',
            'data': {
                'start_page': start_page,
                'num_pages': num_pages,
                'end_page': start_page + num_pages - 1
            }
        }
        
    except Exception as e:
        print(f"Error initializing SOVAS scraper: {str(e)}")
        return {
            'status': 'error',
            'message': f'Failed to initialize SOVAS scraper: {str(e)}'
        }

def get_sovas_paginated_data(page=1, page_size=50):
    """
    Fetch paginated data from final_data.json.
    Returns a dictionary with the paginated data and metadata.
    If page_size is None, returns all entries.
    """
    try:
        # Base directory for SOVAS scraper
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SOVAS Scraper', 'json data')
        final_data_path = os.path.join(base_dir, 'final_data.json')
        progress1_path = os.path.join(base_dir, 'progress1.json')
        
        print(f"DEBUG: Looking for final_data.json at: {final_data_path}")
        print(f"DEBUG: File exists: {os.path.exists(final_data_path)}")
        
        # Load all data from final_data.json
        all_data = []
        if os.path.exists(final_data_path):
            try:
                with open(final_data_path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                print(f"DEBUG: Successfully loaded {len(all_data)} entries from final_data.json")
            except Exception as e:
                print(f"Error reading final_data.json: {str(e)}")
                return {
                    'status': 'error',
                    'message': f'Failed to read final_data.json: {str(e)}',
                    'data': {
                        'voice_actors': [],
                        'pagination': {
                            'current_page': page,
                            'page_size': page_size or 'all',
                            'total_entries': 0,
                            'total_pages': 0,
                            'has_next': False,
                            'has_prev': False
                        }
                    }
                }
        else:
            print(f"DEBUG: final_data.json not found at {final_data_path}")
        
        # Load progress1.json for additional context
        progress_data = {"last_page": 180}  # Default fallback
        if os.path.exists(progress1_path):
            try:
                with open(progress1_path, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
            except Exception as e:
                print(f"Error reading progress1.json: {str(e)}")
        
        total_entries = len(all_data)
        print(f"DEBUG: Total entries: {total_entries}")
        print(f"DEBUG: Requested page_size: {page_size}")
        print(f"DEBUG: Requested page: {page}")
        
        # Handle fetching all entries
        if page_size is None:
            paginated_data = all_data
            total_pages = 1
            has_next = False
            has_prev = False
            start_index = 0
            end_index = total_entries
            print(f"DEBUG: Fetching ALL entries ({len(paginated_data)} entries)")
        else:
            # Normal pagination logic
            total_pages = (total_entries + page_size - 1) // page_size  # Ceiling division
            
            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages
            
            # Calculate start and end indices
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            
            # Get the paginated data
            paginated_data = all_data[start_index:end_index]
            
            # Calculate pagination metadata
            has_next = page < total_pages
            has_prev = page > 1
            
            print(f"DEBUG: Paginated data: {len(paginated_data)} entries (start: {start_index}, end: {end_index})")
        
        return {
            'status': 'success',
            'data': {
                'voice_actors': paginated_data,
                'progress': progress_data,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size or 'all',
                    'total_entries': total_entries,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_prev': has_prev,
                    'start_index': start_index + 1 if total_entries > 0 else 0,
                    'end_index': min(end_index, total_entries)
                }
            }
        }
        
    except Exception as e:
        print(f"Error in get_sovas_paginated_data: {str(e)}")
        return {
            'status': 'error',
            'message': f'Failed to fetch paginated SOVAS data: {str(e)}',
            'data': {
                'voice_actors': [],
                'progress': {"last_page": 180},
                'pagination': {
                    'current_page': page,
                    'page_size': page_size or 'all',
                    'total_entries': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False,
                    'start_index': 0,
                    'end_index': 0
                }
            }
        }

@sovas_bp.route('/sovas/initialize', methods=['POST'])
def handle_sovas_initialize():
    """
    API endpoint to initialize the SOVAS scraper.
    Takes start_page and num_pages as JSON parameters.
    Returns 200 when initialized successfully.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        start_page = data.get('start_page')
        num_pages = data.get('num_pages')

        if start_page is None or num_pages is None:
            return jsonify({
                'status': 'error',
                'message': 'start_page and num_pages are required'
            }), 400

        try:
            start_page = int(start_page)
            num_pages = int(num_pages)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'start_page and num_pages must be integers'
            }), 400

        if start_page <= 0 or num_pages <= 0:
            return jsonify({
                'status': 'error',
                'message': 'start_page and num_pages must be greater than 0'
            }), 400

        if start_page > 500:
            return jsonify({
                'status': 'error',
                'message': 'start_page cannot be greater than 500'
            }), 400

        result = initialize_sovas_scraper(start_page, num_pages)
        status_code = 200 if result['status'] == 'success' else 500
        return jsonify(result), status_code

    except Exception as e:
        print(f"Error in handle_sovas_initialize route: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sovas_bp.route('/sovas/data', methods=['GET'])
def handle_sovas_paginated_data():
    """
    API endpoint to fetch paginated SOVAS scraper data.
    Supports pagination with page and page_size parameters.
    Defaults to first page with 50 items if no parameters provided.
    Use page_size=all or page_size=0 to get all entries.
    """
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        page_size_param = request.args.get('page_size', '50')
        
        # Handle special case for getting all entries
        if page_size_param.lower() in ['all', '0']:
            page_size = None  # Will fetch all entries
            page = 1  # Reset to page 1 when getting all entries
        else:
            try:
                page_size = int(page_size_param)
                if page_size < 1 or page_size > 1000:  # Increased limit for flexibility
                    page_size = 50
            except ValueError:
                page_size = 50
        
        # Validate page number
        if page < 1:
            page = 1
        
        result = get_sovas_paginated_data(page, page_size)
        status_code = 200 if result['status'] == 'success' else 500
        return jsonify(result), status_code
    except Exception as e:
        print(f"Error in handle_sovas_paginated_data route: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 