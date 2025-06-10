from flask import Blueprint, request, jsonify
import os
import json

# Create a Blueprint for PTP routes
ptp_bp = Blueprint('ptp', __name__)

def get_ptp_movies():
    try:
        page = request.args.get('page', '1')
        items_per_page = 20
        
        # Read the output.json file - using absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'PTP Scraper', 'output.json')
        
        print(f"[FLASK] Looking for movies file at: {json_path}")
        
        if not os.path.exists(json_path):
            return jsonify({
                'status': 'error',
                'message': f'Movies data file not found at {json_path}'
            }), 404
            
        with open(json_path, 'r', encoding='utf-8') as f:
            movies = json.load(f)
            
        # Handle pagination
        if page.lower() == 'all':
            return jsonify({
                'status': 'success',
                'data': movies,
                'total': len(movies),
                'page': 'all'
            })
            
        try:
            page_num = int(page)
            if page_num < 1:
                return jsonify({
                    'status': 'error',
                    'message': 'Page number must be greater than 0'
                }), 400
                
            start_idx = (page_num - 1) * items_per_page
            end_idx = start_idx + items_per_page
            
            # Sort movies by Name to ensure consistent ordering
            sorted_movies = sorted(movies, key=lambda x: x.get('Name', ''), reverse=True)
            paginated_movies = sorted_movies[start_idx:end_idx]
            
            return jsonify({
                'status': 'success',
                'data': paginated_movies,
                'total': len(movies),
                'page': page_num,
                'total_pages': (len(movies) + items_per_page - 1) // items_per_page
            })
            
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid page number'
            }), 400
            
    except Exception as e:
        print(f"[FLASK] Error in get_ptp_movies: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Register routes with the blueprint
@ptp_bp.route('/movies', methods=['GET'])
def ptp_movies_route():
    return get_ptp_movies() 