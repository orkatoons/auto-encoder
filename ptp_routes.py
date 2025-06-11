from flask import Blueprint, request, jsonify
import os
import json
import subprocess
import re

# Create a Blueprint for PTP routes
ptp_bp = Blueprint('ptp', __name__)

def get_best_torrent_from_cli(movie_url):
    cmd = [
        "ptp", "search", movie_url,
        "--movie-format", "",  # disable movie header
        "--torrent-format", "{{Id}}||{{ReleaseName}}||{{Seeders}}||{{Magnet}}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ptp CLI failed: {res.stderr}")
    # Parse torrents
    torrents = []
    for line in res.stdout.strip().splitlines():
        parts = line.split("||")
        if len(parts) != 4:
            continue
        tid, name, seeders, magnet = parts
        seeders = int(seeders)
        if seeders < 1 or re.search(r'2160p|uhd', name, re.IGNORECASE):
            continue
        torrents.append({"Id": tid, "Name": name, "Seeders": seeders, "Magnet": magnet})
    # Filter for remux first, else Blu-ray
    for t in torrents:
        if "remux" in t["Name"].lower():
            return t
    for t in torrents:
        if any(x in t["Name"].lower() for x in ["bd50", "bd25", "bluray"]):
            return t
    return None

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

def handle_ptp_download(data):
    try:
        if not data:
            return {
                'status': 'error',
                'message': 'No data provided'
            }, 400

        link = data.get('link')
        name = data.get('name')
        year = data.get('year')

        if not all([link, name, year]):
            return {
                'status': 'error',
                'message': 'Missing required fields: link, name, or year'
            }, 400

        print(f"[FLASK] Download request received:")
        print(f"Link: {link}")
        print(f"Name: {name}")
        print(f"Year: {year}")

        try:
            # Get the best torrent for the movie
            best_torrent = get_best_torrent_from_cli(link)
            if not best_torrent:
                return {
                    'status': 'error',
                    'message': 'No suitable torrent found'
                }, 404

            # Extract the movie ID from the original link
            movie_id = link.split('id=')[-1].split('&')[0]
            
            # Construct the final torrent link
            final_link = f"https://passthepopcorn.me/torrents.php?id={movie_id}&torrentid={best_torrent['Id']}"
            
            print(f"[FLASK] Selected torrent: {best_torrent['Name']}")
            print(f"[FLASK] Release Name: {name}")
            print(f"[FLASK] Release Year: {year}")
            print(f"[FLASK] Seeders: {best_torrent['Seeders']}")
            print(f"[FLASK] Final link: {final_link}")

            return {
                'status': 'success',
                'message': 'Download request received',
                'data': {
                    'torrent_name': best_torrent['Name'],
                    'seeders': best_torrent['Seeders'],
                    'final_link': final_link,
                    'magnet': best_torrent['Magnet']
                }
            }

        except Exception as e:
            print(f"[FLASK] Error getting torrent: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error getting torrent: {str(e)}'
            }, 500

    except Exception as e:
        print(f"[FLASK] Error in handle_ptp_download: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }, 500

# Register routes with the blueprint
@ptp_bp.route('/movies', methods=['GET'])
def ptp_movies_route():
    return get_ptp_movies()

# Export the functions
__all__ = ['get_ptp_movies', 'handle_ptp_download']

'''W:\Freeleech\autostart>ptp search "https://passthepopcorn.me/torrents.php?id=382245" --movie-format ""
- x264/MKV/WEB/720p - MokshapatamHindi.2025.720p.Ultra.OTT.WEB-DL.AAC.2.0.H264-Telly - 1/3/0
- x264/MKV/WEB/1080p - MokshapatamHindi.2025.1080p.Ultra.OTT.WEB-DL.AAC.2.0.H264-Telly - 2/4/0'''