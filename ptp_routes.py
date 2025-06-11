from flask import Blueprint, request, jsonify
import os
import json
import subprocess
import re
import requests
import qbittorrentapi
import time
from pathlib import Path

# Create a Blueprint for PTP routes
ptp_bp = Blueprint('ptp', __name__)

NODE_API_URL = 'http://geekyandbrain.ddns.net:3030/api'

def get_best_torrent_from_cli(movie_url):
    cmd = [
        "ptp", "search", movie_url,
        "--movie-format", "",  # disable movie header
        "--torrent-format", "{{Id}}||{{ReleaseName}}||{{Seeders}}||{{Source}}"
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
        tid, name, seeders, source = parts
        seeders = int(seeders)
        if seeders < 1 or re.search(r'2160p|uhd', name, re.IGNORECASE):
            continue
        torrents.append({"Id": tid, "Name": name, "Seeders": seeders, "Source": source})
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

def notify_download_complete(data):
    try:
        response = requests.post(f"{NODE_API_URL}/ptp/download/complete", json=data)
        if response.status_code != 200:
            print(f"[FLASK] Failed to notify download completion: {response.text}")
    except Exception as e:
        print(f"[FLASK] Error notifying download completion: {str(e)}")

def initialize_torrent(torrent_path, movie_name):
    """Initialize torrent download using qBittorrent"""
    try:
        # Connect to qBittorrent
        qbt = qbittorrentapi.Client(host='localhost', port=13337)
        
        # Attempt login
        try:
            qbt.auth_log_in()
        except qbittorrentapi.LoginFailed:
            print(f"[FLASK] Failed to login to qBittorrent")
            return False

        # Get the source directory path
        source_dir = str(Path("W:/Encodes") / movie_name / "source")
        
        # Add the torrent file and start it immediately
        try:
            result = qbt.torrents_add(
                torrent_files=[torrent_path],
                save_path=source_dir,  # Set download location to source folder
                paused=False
            )
            print(f"[FLASK] ✅ Torrent added and started for {movie_name}")
            print(f"[FLASK] Download location set to: {source_dir}")
            return True
        except Exception as ex:
            print(f"[FLASK] ❌ Failed to add torrent: {ex}")
            return False

    except Exception as e:
        print(f"[FLASK] Error initializing torrent: {str(e)}")
        return False

def download_torrent(final_link, movie_name):
    """Download torrent file using PTP CLI"""
    try:
        # Create base directory
        base_dir = Path("W:/Encodes")
        movie_dir = base_dir / movie_name
        source_dir = movie_dir / "source"
        
        # Create directories if they don't exist
        source_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to source directory
        os.chdir(str(source_dir))
        
        # Download torrent using PTP CLI
        cmd = ["ptp", "search", final_link, "-d"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[FLASK] Failed to download torrent: {result.stderr}")
            return None
            
        # Find the downloaded torrent file
        torrent_files = list(source_dir.glob("*.torrent"))
        if not torrent_files:
            print("[FLASK] No torrent file found after download")
            return None
            
        return str(torrent_files[0])
        
    except Exception as e:
        print(f"[FLASK] Error downloading torrent: {str(e)}")
        return None

def handle_ptp_download(data):
    try:
        if not data:
            return {
                'status': 'error',
                'message': 'No data provided'
            }

        link = data.get('link')
        name = data.get('name')
        year = data.get('year')

        if not all([link, name, year]):
            return {
                'status': 'error',
                'message': 'Missing required fields: link, name, or year'
            }

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
                }

            # Extract the movie ID from the original link
            movie_id = link.split('id=')[-1].split('&')[0]
            
            # Construct the final torrent link
            final_link = f"https://passthepopcorn.me/torrents.php?id={movie_id}&torrentid={best_torrent['Id']}"
            
            print(f"[FLASK] Selected torrent: {best_torrent['Name']}")
            print(f"[FLASK] Release Name: {name}")
            print(f"[FLASK] Release Year: {year}")
            print(f"[FLASK] Seeders: {best_torrent['Seeders']}")
            print(f"[FLASK] Final link: {final_link}")

            # Download torrent file
            torrent_path = download_torrent(final_link, name)
            if not torrent_path:
                return {
                    'status': 'error',
                    'message': 'Failed to download torrent file'
                }

            # Initialize torrent download
            if not initialize_torrent(torrent_path, name):
                return {
                    'status': 'error',
                    'message': 'Failed to initialize torrent download'
                }

            response_data = {
                'status': 'success',
                'message': 'Download request received',
                'data': {
                    'torrent_name': best_torrent['Name'],
                    'seeders': best_torrent['Seeders'],
                    'final_link': final_link,
                    'source': best_torrent['Source']
                }
            }

            # Notify Node.js backend of completion
            notify_download_complete(response_data)

            return response_data

        except Exception as e:
            print(f"[FLASK] Error getting torrent: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error getting torrent: {str(e)}'
            }

    except Exception as e:
        print(f"[FLASK] Error in handle_ptp_download: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

# Register routes with the blueprint
@ptp_bp.route('/movies', methods=['GET'])
def ptp_movies_route():
    return get_ptp_movies()

# Export the functions
__all__ = ['get_ptp_movies', 'handle_ptp_download']

