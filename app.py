# These two lines must be the VERY FIRST executable lines for eventlet.
import eventlet
eventlet.monkey_patch()

# Now, we can import everything else
import os
import bcrypt
import logging
import threading
import queue
from functools import wraps
from flask import Flask, Response, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from dotenv import load_dotenv

from database import db
from broadcaster import Broadcaster
from audio_engine import AudioEngine
from youtube_handler import search_youtube, download_audio, get_video_details
from eventlet import tpool

# --- Basic Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", os.urandom(24))
# This is the key: flask_socketio will use the eventlet server
socketio = SocketIO(app, async_mode='eventlet')

# --- Global Instances for Audio Streaming ---
now_playing_queue = queue.Queue()
broadcaster = Broadcaster()
# The audio engine creates its own async DB connection
audio_engine = AudioEngine(broadcaster, now_playing_queue)


def create_initial_admin_user():
    """Synchronously creates the initial admin user if one doesn't exist."""
    admin_user = os.getenv("DJ_USERNAME")
    admin_pass = os.getenv("DJ_PASSWORD")
    if not all([admin_user, admin_pass]):
        logging.error("Missing DJ_USERNAME or DJ_PASSWORD. Cannot create admin user.")
        return
    try:
        user = db.get('users', {'username': admin_user})
        if not user:
            hashed_password = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt())
            db.create('users', {'username': admin_user, 'password': hashed_password, 'role': 'admin'})
            logging.info(f"Created initial admin user: {admin_user}")
    except Exception as e:
        logging.error(f"Could not create initial admin user: {e}")

def is_logged_in():
    return session.get('logged_in')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Websocket Emitter Thread ---
def now_playing_emitter():
    while True:
        song_info = now_playing_queue.get()
        socketio.emit('now_playing', song_info)
        logging.info(f"Emitted now_playing: {song_info.get('title') if song_info else 'Silence'}")

# --- Core Routes (All Synchronous) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = db.get('users', {'username': username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def listener_page():
    return render_template('listener.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/stream.mp3')
def audio_stream():
    client_queue = broadcaster.register()
    def generate():
        try:
            while True:
                chunk = client_queue.get()
                yield chunk
        finally:
            broadcaster.unregister(client_queue)
    return Response(generate(), mimetype='audio/mpeg')

# --- API Routes (Using tpool for blocking calls) ---
@app.route('/api/search')
@login_required
def search():
    query = request.args.get('q')
    if not query: return "Query required", 400
    results = tpool.execute(search_youtube, query)
    return jsonify(results)

@app.route('/api/playlist', methods=['GET', 'POST'])
@login_required
def handle_playlist():
    if request.method == 'GET':
        playlist = db.find('playlist', {}, sort=[("order", 1)])
        return jsonify(playlist)
    if request.method == 'POST':
        new_playlist_data = request.json
        if isinstance(new_playlist_data, list):
            for i, song in enumerate(new_playlist_data):
                song['order'] = i
            db.replace_collection('playlist', new_playlist_data)
            audio_engine.reload_playlist_from_db()
            socketio.emit('playlist_updated', new_playlist_data)
            return "Playlist updated", 200
        return "Invalid data format", 400

@app.route('/api/suggestions', methods=['GET', 'POST'])
def handle_suggestions():
    if request.method == 'GET':
        suggestions = db.find('suggestions', sort=[("votes", -1)])
        return jsonify(suggestions)
    if request.method == 'POST':
        data = request.json
        yt_id = data.get('yt_id')
        if not yt_id: return "YouTube ID is required", 400
        if db.get('suggestions', {'yt_id': yt_id}):
            return "Song has already been suggested", 409
        video_details = tpool.execute(get_video_details, yt_id)
        if not video_details: return "Could not find video details for this ID", 404
        suggestion = {"title": video_details.get('title', 'Untitled'), "yt_id": yt_id, "votes": 1, "voter_ips": [request.remote_addr]}
        db.create('suggestions', suggestion)
        all_suggestions = db.find('suggestions', sort=[("votes", -1)])
        socketio.emit('suggestions_updated', all_suggestions)
        return jsonify(suggestion), 201

@app.route('/api/suggestions/<suggestion_id>/vote', methods=['POST'])
def vote_for_suggestion(suggestion_id):
    voter_ip = request.remote_addr
    suggestion = db.get('suggestions', {'_id': suggestion_id})
    if not suggestion: return "Suggestion not found", 404
    if voter_ip in suggestion.get('voter_ips', []):
        return "You have already voted for this song", 403
    db.update('suggestions', {'_id': suggestion_id}, {'$inc': {'votes': 1}, '$addToSet': {'voter_ips': voter_ip}})
    all_suggestions = db.find('suggestions', sort=[("votes", -1)])
    socketio.emit('suggestions_updated', all_suggestions)
    return jsonify({"success": True})

@app.route('/api/promote_winner', methods=['POST'])
@login_required
def promote_winner():
    top_songs = db.find('suggestions', sort=[("votes", -1)], limit=1)
    if not top_songs: return "No suggestions to promote", 404
    winner = top_songs[0]
    if db.get('playlist', {'yt_id': winner['yt_id']}):
        db.delete_many('suggestions', {})
        socketio.emit('suggestions_updated', [])
        return f"'{winner['title']}' is already in the playlist. Suggestions cleared.", 200
    filepath = tpool.execute(download_audio, winner['yt_id'])
    if not filepath: return "Failed to download song audio", 500
    current_playlist = db.find('playlist', {})
    playlist_entry = {"title": winner['title'], "yt_id": winner['yt_id'], "filepath": filepath, "order": len(current_playlist)}
    db.create('playlist', playlist_entry)
    db.delete_many('suggestions', {})
    audio_engine.reload_playlist_from_db()
    new_playlist = db.find('playlist', {}, sort=[("order", 1)])
    socketio.emit('playlist_updated', new_playlist)
    socketio.emit('suggestions_updated', [])
    return f"'{winner['title']}' promoted to playlist!", 200


# --- Main Execution Block ---
if __name__ == '__main__':
    logging.info("Performing initial setup...")
    create_initial_admin_user()
    logging.info("Setup complete.")

    logging.info("Starting background threads...")
    audio_thread = threading.Thread(target=audio_engine.run, name="AudioEngineThread", daemon=True)
    audio_thread.start()
    socketio.start_background_task(target=now_playing_emitter)

    port = int(os.getenv("PORT", 5000))
    logging.info(f"\n>>> Starting server on http://localhost:{port} <<<")
    # This is the correct, cross-platform way to run an eventlet-based Socket.IO server
    socketio.run(app, host='0.0.0.0', port=port)