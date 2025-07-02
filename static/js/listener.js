document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Element References
    const suggestionForm = document.getElementById('suggestion-form');
    const suggestionInput = document.getElementById('suggestion-input');
    const suggestionsList = document.getElementById('suggestions-list');
    const nowPlayingSpan = document.querySelector('#now-playing span');

    // --- Data Fetching and Rendering ---
    const fetchSuggestions = async () => {
        try {
            const response = await fetch('/api/suggestions');
            const suggestions = await response.json();
            renderSuggestions(suggestions);
        } catch (error) {
            console.error('Failed to fetch suggestions:', error);
        }
    };

    const renderSuggestions = (suggestions) => {
        suggestionsList.innerHTML = '';
        suggestions.forEach(song => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${song.title} (${song.votes} votes)</span>
                <button class="vote-btn" data-id="${song._id}">Vote</button>
            `;
            suggestionsList.appendChild(li);
        });
    };

    // --- Event Listeners ---
    suggestionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        // Regex to find a YouTube ID in a URL or as a standalone string
        const ytIdMatch = suggestionInput.value.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|^(?!www\.)[a-zA-Z0-9_-]{11}$)([a-zA-Z0-9_-]{11})/);
        
        if (!ytIdMatch || !ytIdMatch[1]) {
            alert("Please provide a valid YouTube link or video ID.");
            return;
        }
        const yt_id = ytIdMatch[1];
        
        const response = await fetch('/api/suggestions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ yt_id: yt_id })
        });

        if (response.ok) {
            suggestionInput.value = '';
            // The socket event will handle the re-render
        } else {
            alert(`Error: ${await response.text()}`);
        }
    });

    suggestionsList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('vote-btn')) {
            const id = e.target.dataset.id;
            e.target.disabled = true; // Prevent double-clicking
            const response = await fetch(`/api/suggestions/${id}/vote`, { method: 'POST' });
            if (!response.ok) {
                alert(await response.text());
                e.target.disabled = false;
            }
             // The socket event will handle the re-render
        }
    });

    // --- Socket.IO Listeners ---
    socket.on('now_playing', (songInfo) => {
        nowPlayingSpan.textContent = songInfo.title;
        document.title = `${songInfo.title} - Sebastian's Radio`;
    });

    socket.on('suggestions_updated', (suggestions) => {
        console.log('Suggestions updated via WebSocket.');
        renderSuggestions(suggestions);
    });

    // --- Initial Load ---
    fetchSuggestions();
});