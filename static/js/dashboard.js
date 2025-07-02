document.addEventListener('DOMContentLoaded', () => {
    const playlistEl = document.getElementById('playlist');
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const searchResultsEl = document.getElementById('search-results');
    const suggestionsListDj = document.getElementById('suggestions-list-dj');
    const promoteBtn = document.getElementById('promote-winner-btn');

    let playlist = [];

    // Make playlist draggable
    new Sortable(playlistEl, {
        animation: 150,
        ghostClass: 'blue-background-class'
    });

    async function fetchPlaylist() {
        const response = await fetch('/api/playlist');
        playlist = await response.json();
        renderPlaylist();
    }
    
    function renderPlaylist() {
        playlistEl.innerHTML = '';
        playlist.forEach(song => {
            const li = document.createElement('li');
            li.textContent = song.title;
            li.dataset.id = song.yt_id;
            playlistEl.appendChild(li);
        });
    }

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = searchInput.value;
        const response = await fetch(`/api/search?q=${query}`);
        const results = await response.json();
        renderSearchResults(results);
    });
    
    function renderSearchResults(results) {
        searchResultsEl.innerHTML = '';
        results.forEach(video => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${video.title}</span>
                <button class="add-btn" data-id="${video.id}" data-title="${video.title}">Add</button>
            `;
            searchResultsEl.appendChild(li);
        });
    }
    
    // In a full app, you'd add listeners for 'add' and 'save' buttons
    // to call the respective API endpoints.
    
    async function fetchDjSuggestions() {
        const response = await fetch('/api/suggestions');
        const suggestions = await response.json();
        suggestionsListDj.innerHTML = '';
        suggestions.forEach(song => {
            const li = document.createElement('li');
            li.innerHTML = `<span>${song.title} (${song.votes} votes)</span>`;
            suggestionsListDj.appendChild(li);
        });
    }

    promoteBtn.addEventListener('click', async () => {
        if (confirm("Are you sure you want to promote the top song and clear all suggestions?")) {
            const response = await fetch('/api/promote_winner', { method: 'POST' });
            alert(await response.text());
            fetchDjSuggestions();
            fetchPlaylist(); // Refresh playlist to show new song
        }
    });

    fetchPlaylist();
    fetchDjSuggestions();
});