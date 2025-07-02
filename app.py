# These two lines must be the VERY FIRST executable lines for eventlet.
import eventlet
eventlet.monkey_patch()

# Now, we can import everything else
import os
import asyncio
import bcrypt
import logging
import threading
import queue
from flask import Flask, Response, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from dotenv import load_dotenv
from pymongo import MongoClient

from database import db
from broadcaster import Broadcaster
from audio_engine import AudioEngine
from youtube_handler import search_youtube, download_audio, get_video_details

# --- Basic Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", os.urandom(24))
socketio = SocketIO(app, async_mode='eventlet')

# --- Global Instances for Audio Streaming ---
now_playing_queue = queue.Queue()
broadcaster = Broadcaster()
# Pass db instance and the update queue to the audio engine
audio_engine = AudioEngine(broadcaster, db, now_playing_queue)


def create_initial_admin_user_sync():
    """Synchronously creates the initial admin user if one doesn't exist."""
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME")
    admin_user = os.getenv("DJ_USERNAME")
    admin_pass = os.getenv("DJ_PASSWORD")
    if not all([mongo_uri, db_name, admin_user, admin_pass]):
        logging.error("Missing environment variables for database setup. Cannot create admin user.")
        return
    try:
        client = MongoClient(mongo_uri)
        db_sync = client[db_name]
        user = db_sync.users.find_one({'username': admin_user})
        if not user:
            hashed_password = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt())
            db_sync.users.insert_one({'username': admin_user, 'password': hashed_password, 'role': 'admin'})
            logging.info(f"Created initial admin user: {admin_user}")
        client.close()
    except Exception as e:
        logging.error(f"Could not connect to MongoDB for initial setup: {e}")

def is_logged_in():
    return session.get('logged_in')

# --- Websocket Emitter Thread ---
def now_playing_emitter():
    """
    A background thread that listens for 'now playing' updates from the
    audio engine and emits them to all clients via Socket.IO.
    """
    while True:
        song_info = now_playing_queue.get() # This will block until an item is available
        socketio.emit('now_playing', song_info)
        logging.info(f"Emitted now_playing: {song_info.get('title') if song_info else 'Silence'}")


# --- Core Routes ---
@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = await db.get('users', {'username': username})
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
def dashboard():
    if not is_logged_in(): return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/stream.mp3')
def audio_stream():
    """The live audio stream endpoint. Uses the Broadcaster."""
    client_queue = broadcaster.register()
    def generate():
        try:
            while True:
                chunk = client_queue.get()
                yield chunk
        finally:
            broadcaster.unregister(client_queue)
    return Response(generate(), mimetype='audio/mpeg')

# --- API Routes ---

@app.route('/api/search')
async def search():
    if not is_logged_in(): return "Unauthorized", 401
    query = request.args.get('q')
    if not query: return "Query required", 400
    
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, search_youtube, query)
    return jsonify(results)

@app.route('/api/playlist', methods=['GET', 'POST'])
async def handle_playlist():
    if not is_logged_in(): return "Unauthorized", 401
    
    if request.method == 'GET':
        playlist = await db.find('playlist', {}, sort=[("order", 1)])
        return jsonify(playlist)
    
    if request.method == 'POST':
        new_playlist_data = request.json
        if isinstance(new_playlist_data, list):
            # Add an 'order' field to maintain sequence
            for i, song in enumerate(new_playlist_data):
                song['order'] = i
            await db.replace_collection('playlist', new_playlist_data)
            audio_engine.reload_playlist_from_db()
            socketio.emit('playlist_updated', new_playlist_data)
            return "Playlist updated", 200
        return "Invalid data format", 400

@app.route('/api/suggestions', methods=['GET', 'POST'])
async def handle_suggestions():
    if request.method == 'GET':
        suggestions = await db.find('suggestions', sort=[("votes", -1)])
        return jsonify(suggestions)
    
    if request.method == 'POST':
        data = request.json
        yt_id = data.get('yt_id')
        if not yt_id: return "YouTube ID is required", 400
        
        existing = await db.get('suggestions', {'yt_id': yt_id})
        if existing: return "Song has already been suggested", 409

        loop = asyncio.get_running_loop()
        video_details = await loop.run_in_executor(None, get_video_details, yt_id)
        if not video_details: return "Could not find video details for this ID", 404

        suggestion = {
            "title": video_details.get('title', 'Untitled'),
            "yt_id": yt_id,
            "votes": 1,
            "voter_ips": [request.remote_addr]
        }
        await db.create('suggestions', suggestion)
        
        # Emit update to all clients
        all_suggestions = await db.find('suggestions', sort=[("votes", -1)])
        socketio.emit('suggestions_updated', all_suggestions)
        return jsonify(suggestion), 201

@app.route('/api/suggestions/<suggestion_id>/vote', methods=['POST'])
async def vote_for_suggestion(suggestion_id):
    voter_ip = request.remote_addr
    suggestion = await db.get('suggestions', {'_id': suggestion_id})
    if not suggestion: return "Suggestion not found", 404
    if voter_ip in suggestion.get('voter_ips', []):
        return "You have already voted for this song", 403
    
    await db.update('suggestions', {'_id': suggestion_id}, {'$inc': {'votes': 1}, '$addToSet': {'voter_ips': voter_ip}})
    
    # Emit update to all clients
    all_suggestions = await db.find('suggestions', sort=[("votes", -1)])
    socketio.emit('suggestions_updated', all_suggestions)
    return jsonify({"success": True})

@app.route('/api/promote_winner', methods=['POST'])
async def promote_winner():
    if not is_logged_in(): return "Unauthorized", 401
    
    top_songs = await db.find('suggestions', sort=[("votes", -1)], limit=1)
    if not top_songs: return "No suggestions to promote", 404
    winner = top_songs[0]

    if await db.get('playlist', {'yt_id': winner['yt_id']}):
        await db.delete_many('suggestions', {})
        socketio.emit('suggestions_updated', [])
        return f"'{winner['title']}' is already in the playlist. Suggestions cleared.", 200

    loop = asyncio.get_running_loop()
    filepath = await loop.run_in_executor(None, download_audio, winner['yt_id'])
    if not filepath: return "Failed to download song audio", 500

    current_playlist = await db.find('playlist', {})
    playlist_entry = {
        "title": winner['title'],
        "yt_id": winner['yt_id'],
        "filepath": filepath,
        "order": len(current_playlist) # Add to the end
    }
    await db.create('playlist', playlist_entry)
    await db.delete_many('suggestions', {})
    
    # Signal updates
    audio_engine.reload_playlist_from_db()
    new_playlist = await db.find('playlist', {}, sort=[("order", 1)])
    socketio.emit('playlist_updated', new_playlist)
    socketio.emit('suggestions_updated', [])
    
    return f"'{winner['title']}' promoted to playlist!", 200


# --- Main Execution Block ---
if __name__ == '__main__':
    logging.info("Performing initial setup...")
    create_initial_admin_user_sync()
    logging.info("Setup complete.")

    logging.info("Starting background threads...")
    # Start the audio engine in a daemon thread
    audio_thread = threading.Thread(target=audio_engine.run, name="AudioEngineThread", daemon=True)
    audio_thread.start()

    # Start the websocket emitter for 'now playing' updates
    socketio.start_background_task(target=now_playing_emitter)

    port = int(os.getenv("PORT", 5000))
    logging.info(f"\n>>> Starting server on http://localhost:{port} <<<")
    
    # use_reloader=False is important to prevent running the setup and threads twice.
    # Debug mode is still active for code changes in the main Flask thread.
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)