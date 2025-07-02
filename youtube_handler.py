import yt_dlp
import os

# Ensure the cache directory exists
CACHE_DIR = "music_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def search_youtube(query, max_results=5):
    """Searches YouTube and returns a list of video details."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': f"ytsearch{max_results}",
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(query, download=False)
            return search_result.get('entries', [])
    except Exception:
        return []

def get_video_details(video_id):
    """Fetches details for a single video ID without downloading."""
    ydl_opts = {'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f'http://www.youtube.com/watch?v={video_id}', download=False)
            return {'id': info.get('id'), 'title': info.get('title', 'Untitled Video')}
        except Exception as e:
            print(f"Error fetching details for {video_id}: {e}")
            return None

def download_audio(video_id):
    """Downloads audio for a given video_id and returns the file path."""
    # Use os.path.join for cross-platform compatibility
    file_path = os.path.join(CACHE_DIR, f"{video_id}.mp3")
    
    # If already cached, return the path immediately
    if os.path.exists(file_path):
        return file_path

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(CACHE_DIR, f'{video_id}.%(ext)s'),
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            return file_path
        except Exception as e:
            print(f"Error downloading {video_id}: {e}")
            return None