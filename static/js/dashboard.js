document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Element References
    const playlistEl = document.getElementById('playlist');
    const savePlaylistBtn = document.getElementById('save-playlist');
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const searchResultsEl = document.getElementById('search-results');
    const suggestionsListDj = document.getElementById('suggestions-list-dj');
    const promoteBtn = document.getElementById('promote-winner-btn');

    let playlist = [];
    let sortable = new Sortable(playlistEl, {
        animation: 150,
        ghostClass: 'blue-background-class',
    });

    // --- Data Fetching and Rendering ---
    const fetchPlaylist = async () => {
        const response = await fetch('/api/playlist');
        playlist = await response.json();
        renderPlaylist();
    };
    
    const fetchDjSuggestions = async () => {
        const response = await fetch('/api/suggestions');
        const suggestions = await response.json();
        renderDjSuggestions(suggestions);
    };

    const renderPlaylist = () => {
        playlistEl.innerHTML = '';
        playlist.forEach(song => {
            const li = document.createElement('li');
            li.textContent = song.title;
            li.dataset.id = song.yt_id; // For SortableJS
            playlistEl.appendChild(li);
        });
    };

    const renderDjSuggestions = (suggestions) => {
        suggestionsListDj.innerHTML = '';
        suggestions.forEach(song => {
            const li = document.createElement('li');
            li.innerHTML = `<span>${song.title} (${song.votes} votes)</span>`;
            suggestionsListDj.appendChild(li);
        });
        promoteBtn.disabled = suggestions.length === 0;
    };

    const renderSearchResults = (results) => {
        searchResultsEl.innerHTML = '';
        results.forEach(video => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${video.title}</span>
                <button class="add-btn" data-yt-id="${video.id}" data-title="${video.title}">Add to Playlist</button>
            `;
            searchResultsEl.appendChild(li);
        });
    };

    // --- Event Listeners ---
    savePlaylistBtn.addEventListener('click', async () => {
        const orderedIds = sortable.toArray();
        const newPlaylist = orderedIds.map(id => playlist.find(song => song.yt_id === id)).filter(Boolean);

        const response = await fetch('/api/playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newPlaylist)
        });

        if (response.ok) {
            alert('Playlist order saved!');
            playlist = newPlaylist; // Update local state
        } else {
            alert(`Error: ${await response.text()}`);
        }
    });

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = searchInput.value;
        if (!query) return;
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const results = await response.json();
        renderSearchResults(results);
    });

    searchResultsEl.addEventListener('click', async (e) => {
        if (e.target.classList.contains('add-btn')) {
            const button = e.target;
            const newSong = { yt_id: button.dataset.ytId, title: button.dataset.title };
            // For simplicity, we just promote it as a suggestion first
            const response = await fetch('/api/suggestions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(newSong)
            });
            if (response.ok || response.status === 409) { // 409 = already suggested
                 alert(`'${newSong.title}' has been added to suggestions.`);
            } else {
                alert(`Error: ${await response.text()}`);
            }
        }
    });

    promoteBtn.addEventListener('click', async () => {
        if (confirm("Promote the top song and clear all suggestions?")) {
            const response = await fetch('/api/promote_winner', { method: 'POST' });
            alert(await response.text());
        }
    });

    // --- Socket.IO Listeners ---
    socket.on('playlist_updated', (newPlaylist) => {
        console.log('Playlist updated via WebSocket.');
        playlist = newPlaylist;
        renderPlaylist();
    });

    socket.on('suggestions_updated', (suggestions) => {
        console.log('Suggestions updated via WebSocket.');
        renderDjSuggestions(suggestions);
    });

    // --- Initial Load ---
    fetchPlaylist();
    fetchDjSuggestions();
});