# Sebastian's Radio - A Community-Driven YouTube Radio Station

This project is a web application that runs a live, 24/7 internet radio station powered by YouTube. It features a DJ dashboard for managing the playlist and a public listener page where users can listen to the live stream, suggest songs, and vote for their favorites. The application is built to run on both Windows and Linux.

## Features

-   **Live Audio Streaming**: Continuous audio stream accessible to all connected clients.
-   **Cross-Platform**: Runs on both Windows and Linux without modification.
-   **DJ Dashboard**: A password-protected area (`/dashboard`) for playlist and suggestion management.
-   **Listener Engagement**: Public page (`/`) for listening, suggesting, and voting on songs.
-   **Real-time Updates**: Uses WebSockets (`Flask-SocketIO`) for instant client updates.
-   **Persistent State**: Uses MongoDB to store user credentials, playlists, and suggestions.
-   **Audio Caching**: Caches audio from YouTube to ensure smooth playback.

## Prerequisites

-   Python 3.8+
-   `pip`
-   MongoDB Server (local or a cloud instance like MongoDB Atlas)
-   **`ffmpeg`**: This is a required external dependency for audio processing.

## Setup & Installation

1.  **Install `ffmpeg`:**
    *   **On Linux (Debian/Ubuntu):**
        ```bash
        sudo apt update && sudo apt install ffmpeg
        ```
    *   **On Windows:**
        1.  Download a release build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (the `ffmpeg-release-essentials.zip` is recommended).
        2.  Extract the zip file to a permanent location (e.g., `C:\ffmpeg`).
        3.  Add the `bin` directory inside that folder (e.g., `C:\ffmpeg\bin`) to your system's `PATH` environment variable.

2.  **Clone the repository.**

3.  **Create and activate a virtual environment:**
    ```bash
    # For Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

4.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables:**
    Create a file named `.env` in the root directory and add the following:
    ```env
    # Flask & Security
    SECRET_KEY=a_very_secret_and_random_string
    
    # MongoDB Connection
    MONGO_URI=mongodb://localhost:27017/
    MONGO_DB_NAME=radio_station

    # Initial Admin/DJ Credentials
    DJ_USERNAME=admin
    DJ_PASSWORD=your_secure_password
    ```

## How to Run

The application is now started with a single, universal command on any operating system.

```bash
python app.py