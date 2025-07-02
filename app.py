import os
import asyncio
import bcrypt
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from dotenv import load_dotenv

from database import db
from youtube_handler import search_youtube, download_audio
# Note: The complex audio engine is simplified for clarity.

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# --- THE CRITICAL FIX IS HERE ---
# Change 'threading' to 'eventlet' to unify the concurrency model
socketio = SocketIO(app, async_mode='eventlet')

# --- Authentication ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

async def create_initial_admin_user():
    """Checks for and creates the initial admin user from .env variables."""
    await db.connect() # Ensure DB is connected before query
    admin_user = os.getenv("DJ_USERNAME")
    admin_pass = os.getenv("DJ_PASSWORD")
    user = await db.get('users', {'username': admin_user})
    if not user:
        hashed_password = hash_password(admin_pass)
        await db.create('users', {'username': admin_user, 'password': hashed_password})
        print(f"Created initial admin user: {admin_user}")

def is_logged_in():
    return session.get('logged_in')

# --- Routes ---
@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = await db.get('users', {'username': username})
        if user and check_password(password, user['password']):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return "Invalid credentials", 401
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
    # This part remains a placeholder as the audio engine itself is a huge task
    return "Audio stream placeholder. Run the full audio engine.", 200

# --- API for Playlist (DJ Only) ---
@app.route('/api/playlist', methods=['GET', 'POST'])
async def handle_playlist():
    if not is_logged_in(): return "Unauthorized", 401
    if request.method == 'GET':
        playlist = await db.find('playlist', {})
        return jsonify(playlist)
    if request.method == 'POST':
        new_playlist = request.json
        if isinstance(new_playlist, list):
            await db.replace_collection('playlist', new_playlist)
            # Here you would signal the audio engine to reload the playlist
            return "Playlist updated", 200
        return "Invalid data format", 400

# --- APIs for Song Suggestions (Public) ---
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
        
        suggestion = {
            "title": data.get('title', 'Untitled'),
            "yt_id": yt_id,
            "votes": 0,
            "voter_ips": []
        }
        await db.create('suggestions', suggestion)
        return jsonify(suggestion), 201

@app.route('/api/suggestions/<suggestion_id>/vote', methods=['POST'])
async def vote_for_suggestion(suggestion_id):
    voter_ip = request.remote_addr
    
    suggestion = await db.get('suggestions', {'_id': suggestion_id})
    if not suggestion: return "Suggestion not found", 404
    
    if voter_ip in suggestion.get('voter_ips', []):
        return "You have already voted for this song", 403

    updated_suggestion = await db.update(
        'suggestions', 
        {'_id': suggestion_id},
        {'$inc': {'votes': 1}, '$addToSet': {'voter_ips': voter_ip}}
    )
    return jsonify(updated_suggestion)

# --- APIs for YouTube (DJ Only) ---
@app.route('/api/search')
async def search():
    if not is_logged_in(): return "Unauthorized", 401
    query = request.args.get('q')
    if not query: return "Query required", 400
    results = search_youtube(query)
    return jsonify(results)

@app.route('/api/promote_winner', methods=['POST'])
async def promote_winner():
    if not is_logged_in(): return "Unauthorized", 401
    
    top_songs = await db.find('suggestions', sort=[("votes", -1)], limit=1)
    if not top_songs: return "No suggestions to promote", 404
    
    winner = top_songs[0]
    
    filepath = download_audio(winner['yt_id'])
    if not filepath: return "Failed to download song audio", 500

    playlist_entry = {
        "title": winner['title'],
        "yt_id": winner['yt_id'],
        "filepath": filepath
    }
    await db.update('playlist', {'name': 'master'}, {'$push': {'songs': playlist_entry}}, upsert=True)
    
    await db.delete_many('suggestions', {})
    
    return f"'{winner['title']}' promoted to playlist!", 200


if __name__ == '__main__':
    # This block is now used for one-time setup and for local development.
    # The production server (Render) will use the Gunicorn command from the Procfile.
    
    print("Performing initial setup...")
    asyncio.run(create_initial_admin_user())
    print("Setup complete.")

    print("\n>>> Starting local development server <<<")
    print(">>> Production deployment on Render will use Gunicorn from the Procfile. <<<")
    # This command will be used when you run `python app.py` on your Windows machine.
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)