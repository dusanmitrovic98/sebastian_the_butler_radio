import threading
import time
import json
import os
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
import io

class AudioEngine(threading.Thread):
    def __init__(self, broadcaster):
        super().__init__()
        self.daemon = True
        self.broadcaster = broadcaster
        
        # State
        self.playlist = []
        self.current_song_index = 0
        self.is_playing = True
        self.is_dj_live = False
        
        self.load_playlist()

    def load_playlist(self):
        if os.path.exists("data/playlist.json"):
            with open("data/playlist.json", "r") as f:
                self.playlist = json.load(f)
        self.current_song_index = 0

    def save_playlist(self):
        if not os.path.exists("data"):
            os.makedirs("data")
        with open("data/playlist.json", "w") as f:
            json.dump(self.playlist, f, indent=4)

    def run(self):
        """The main loop of the audio engine."""
        CHUNK_SIZE = 1024 # bytes
        
        while True:
            if not self.is_playing or not self.playlist:
                time.sleep(1)
                continue

            song_info = self.playlist[self.current_song_index]
            song_path = song_info.get('filepath')

            if not song_path or not os.path.exists(song_path):
                print(f"Song not found: {song_path}. Skipping.")
                self.next_song()
                continue
            
            try:
                song = AudioSegment.from_file(song_path)
            except Exception as e:
                print(f"Could not load song {song_path}: {e}")
                self.next_song()
                continue

            # This is a generator that yields audio chunks
            audio_stream = song.raw_data
            
            for i in range(0, len(audio_stream), CHUNK_SIZE):
                # Check for state changes (e.g., skip song) on every chunk
                if not self.is_playing: 
                    break 
                
                chunk = audio_stream[i:i+CHUNK_SIZE]
                
                # --- Audio Ducking Logic ---
                if self.is_dj_live:
                    # Convert chunk to AudioSegment to lower volume
                    audio_segment_chunk = AudioSegment(
                        chunk, 
                        frame_rate=song.frame_rate, 
                        sample_width=song.sample_width, 
                        channels=song.channels
                    )
                    # Duck the music volume by 10 dB
                    ducked_chunk = audio_segment_chunk - 10
                    chunk = ducked_chunk.raw_data

                # We could add DJ mic mixing here in the future
                
                self.broadcaster.push(chunk)
                
                # Sleep to simulate real-time playback
                # This is a simplified timing mechanism. More advanced would be needed for perfect sync.
                time.sleep(float(CHUNK_SIZE) / (song.frame_rate * song.sample_width * song.channels))

            if self.is_playing: # If we finished the song naturally
                self.next_song()
            
    def next_song(self):
        if not self.playlist:
            return
        self.current_song_index = (self.current_song_index + 1) % len(self.playlist)
        print(f"Playing next song: {self.playlist[self.current_song_index]['title']}")

    def prev_song(self):
        if not self.playlist:
            return
        self.current_song_index = (self.current_song_index - 1 + len(self.playlist)) % len(self.playlist)
    
    # --- Control methods for Flask to call ---
    def set_dj_live(self, is_live):
        print(f"DJ Live status changed to: {is_live}")
        self.is_dj_live = is_live

    # Placeholder for TTS integration
    # def play_tts(self, tts_audio_data): ...