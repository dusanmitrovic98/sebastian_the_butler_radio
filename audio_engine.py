import threading
import time
import os
import asyncio
import logging
from pydub import AudioSegment

from async_database import DataAccessLayer # Import from the renamed async file

class AudioEngine(threading.Thread):
    def __init__(self, broadcaster, now_playing_queue):
        super().__init__()
        self.daemon = True
        self.broadcaster = broadcaster
        # Create a private instance of the Async DataAccessLayer for this thread
        self.db = DataAccessLayer()
        self.now_playing_queue = now_playing_queue
        
        # State
        self.playlist = []
        self.current_song_index = -1
        self.is_playing = True
        self.is_dj_live = False
        
        self._playlist_lock = threading.Lock()
        self._reload_event = threading.Event()
        self.logger = logging.getLogger("AudioEngine")

    def reload_playlist_from_db(self):
        """Signals the run loop to reload the playlist from the database."""
        self._reload_event.set()

    async def _load_playlist_async(self):
        """Asynchronously fetches and loads the playlist from MongoDB."""
        self.logger.info("Attempting to reload playlist from database...")
        try:
            # Sort by the 'order' field set by the DJ dashboard
            playlist_from_db = await self.db.find('playlist', {}, sort=[("order", 1)])
            with self._playlist_lock:
                self.playlist = playlist_from_db
                # If index is now invalid, reset to the beginning
                if self.current_song_index >= len(self.playlist):
                    self.current_song_index = 0 if self.playlist else -1
            self.logger.info(f"Playlist reloaded with {len(self.playlist)} songs.")
        except Exception as e:
            self.logger.error(f"Failed to load playlist from DB: {e}")
        finally:
            self._reload_event.clear()

    def run(self):
        """The main loop of the audio engine."""
        CHUNK_SIZE = 1024  # bytes
        
        # The engine's thread needs its own asyncio event loop to talk to the async DB driver
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initial playlist load
        loop.run_until_complete(self._load_playlist_async())
        self.current_song_index = 0 if self.playlist else -1

        while True:
            # Check if a reload has been requested
            if self._reload_event.is_set():
                loop.run_until_complete(self._load_playlist_async())

            with self._playlist_lock:
                if not self.is_playing or not self.playlist or self.current_song_index < 0:
                    self.now_playing_queue.put({"title": "Silence..."})
                    time.sleep(1)
                    continue
                
                song_info = self.playlist[self.current_song_index]
            
            self.now_playing_queue.put(song_info)
            song_path = song_info.get('filepath')

            if not song_path or not os.path.exists(song_path):
                self.logger.warning(f"Song file not found: {song_path}. Skipping.")
                self.next_song()
                continue
            
            try:
                self.logger.info(f"Now playing: {song_info.get('title')}")
                song = AudioSegment.from_file(song_path)
            except Exception as e:
                self.logger.error(f"Could not load song {song_path}: {e}")
                self.next_song()
                continue

            audio_stream = song.raw_data
            
            # This calculation ensures playback speed is roughly correct
            sleep_duration = float(CHUNK_SIZE) / (song.frame_rate * song.sample_width * song.channels)
            
            playback_interrupted = False
            for i in range(0, len(audio_stream), CHUNK_SIZE):
                # Check for state changes (e.g., skip, pause, reload) on every chunk
                if not self.is_playing or self._reload_event.is_set():
                    playback_interrupted = True
                    break
                
                chunk = audio_stream[i:i+CHUNK_SIZE]
                
                if self.is_dj_live:
                    # Audio ducking: convert chunk to segment, lower volume, get raw data back
                    audio_segment_chunk = AudioSegment(data=chunk, frame_rate=song.frame_rate, sample_width=song.sample_width, channels=song.channels)
                    ducked_chunk = audio_segment_chunk - 10 # Duck by 10 dB
                    chunk = ducked_chunk.raw_data

                self.broadcaster.push(chunk)
                time.sleep(sleep_duration)

            if not playback_interrupted:
                self.next_song()

    def next_song(self):
        with self._playlist_lock:
            if not self.playlist:
                self.current_song_index = -1
                return
            self.current_song_index = (self.current_song_index + 1) % len(self.playlist)
    
    def prev_song(self):
        with self._playlist_lock:
            if not self.playlist:
                self.current_song_index = -1
                return
            self.current_song_index = (self.current_song_index - 1 + len(self.playlist)) % len(self.playlist)
    
    def set_dj_live(self, is_live):
        self.logger.info(f"DJ Live status changed to: {is_live}")
        self.is_dj_live = is_live