# Real-Time TTS Audio Streamer

This project is a web application that generates Text-to-Speech (TTS) audio in real-time and streams it to any connected web browser.

You can type text into the console where the server is running, and the server will speak it. All connected clients will hear the audio simultaneously.

## Features

-   **Real-time Streaming**: Uses Microsoft's `edge-tts` for high-quality neural voices.
-   **Live Broadcasting**: Multiple clients can connect and listen to the same audio stream.
-   **Catch-up Buffer**: New clients who join mid-stream will immediately hear the last few seconds of audio, ensuring a seamless experience.
-   **Thread-Safe Architecture**: Uses separate threads for input, TTS generation, and web serving.

## Prerequisites

-   Python 3.8+
-   `pip`
-   An internet connection for the TTS service.

## Setup & Installation

1.  **Clone the repository or download the files.**

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

1.  **Start the server:**
    ```bash
    python app.py
    ```
    You will see log messages indicating that the server and its worker threads have started.

2.  **Open a web browser** and navigate to:
    [http://127.0.0.1:5000](http://127.0.0.1:5000)

    The audio player should appear and start playing silence (or any queued audio).

3.  **Generate Speech:**
    Go back to the terminal where you ran `python app.py`. Type any text and press **Enter**. The server will generate the audio and stream it to your browser.