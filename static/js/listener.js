document.addEventListener('DOMContentLoaded', () => {
    const suggestionForm = document.getElementById('suggestion-form');
    const suggestionInput = document.getElementById('suggestion-input');
    const suggestionsList = document.getElementById('suggestions-list');

    async function fetchSuggestions() {
        const response = await fetch('/api/suggestions');
        const suggestions = await response.json();
        renderSuggestions(suggestions);
    }

    function renderSuggestions(suggestions) {
        suggestionsList.innerHTML = '';
        suggestions.forEach(song => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${song.title} (${song.votes} votes)</span>
                <button class="vote-btn" data-id="${song._id}">Vote</button>
            `;
            suggestionsList.appendChild(li);
        });
    }

    suggestionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        // A very basic regex to find a YouTube ID from a URL
        const ytIdMatch = suggestionInput.value.match(/(?:v=|\/)([0-9A-Za-z_-]{11}).*/);
        if (!ytIdMatch) {
            alert("Please provide a valid YouTube link for now.");
            return;
        }
        const yt_id = ytIdMatch[1];
        
        const response = await fetch('/api/suggestions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ yt_id: yt_id, title: `Song from ${yt_id}` }) // Title can be improved
        });

        if (response.ok) {
            suggestionInput.value = '';
            fetchSuggestions();
        } else {
            const error = await response.text();
            alert(`Error: ${error}`);
        }
    });

    suggestionsList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('vote-btn')) {
            const id = e.target.dataset.id;
            const response = await fetch(`/api/suggestions/${id}/vote`, { method: 'POST' });
            if (response.ok) {
                fetchSuggestions();
            } else {
                alert(await response.text());
            }
        }
    });

    // Initial load
    fetchSuggestions();
});