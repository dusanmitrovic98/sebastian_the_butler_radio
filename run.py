# run.py

import os
import sys
import logging
import threading
import subprocess

from app import app, socketio, create_initial_admin_user, audio_engine, now_playing_emitter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

def main():
    """Sets up and runs the application server."""
    logging.info("Performing initial setup...")
    create_initial_admin_user()
    logging.info("Setup complete.")

    logging.info("Starting background threads...")
    # Start the audio engine in a daemon thread
    audio_thread = threading.Thread(target=audio_engine.run, name="AudioEngineThread", daemon=True)
    audio_thread.start()

    # Start the websocket emitter for 'now playing' updates
    socketio.start_background_task(target=now_playing_emitter)

    port = int(os.getenv("PORT", 5000))
    host = '0.0.0.0'

    # Check the operating system to choose the correct server
    if sys.platform == "win32":
        # Use Waitress for Windows
        logging.info(f"Detected Windows. Starting Waitress server on http://{host}:{port}")
        from waitress import serve
        serve(app, host=host, port=port)
    else:
        # Use Gunicorn for Linux/macOS
        logging.info(f"Detected Linux/macOS. Starting Gunicorn server on http://{host}:{port}")
        # Gunicorn command-line arguments
        # -w 1: Use a single worker process (important for stateful apps like this)
        # -k eventlet: Use the eventlet worker to handle websockets
        # --bind: The address to bind to
        # app:socketio: The Socket.IO app instance inside the 'app' module
        gunicorn_command = [
            'gunicorn',
            '-w', '1',
            '-k', 'eventlet',
            '--bind', f'{host}:{port}',
            'app:socketio'
        ]
        subprocess.run(gunicorn_command)

if __name__ == '__main__':
    main()