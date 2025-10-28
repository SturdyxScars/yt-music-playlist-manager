document.addEventListener("DOMContentLoaded", () => {
  const browseBtn = document.getElementById("browseBtn");
  const fileInput = document.getElementById("fileInput");
  const uploadForm = document.getElementById("uploadForm");
  const progressContainer = document.getElementById("progressContainer");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  const statusMessage = document.getElementById("statusMessage");

  // Trigger file input on browse click
  browseBtn.addEventListener("click", () => fileInput.click());

  // Show selected file info
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
      document.getElementById("fileInfo").textContent = `Selected: ${file.name}`;
    }
  });

  // Handle form submit with AJAX (no reload)
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(uploadForm);
    const file = fileInput.files[0];
    const songListText = document.getElementById("songList").value.trim();
    const playlistId = document.getElementById("playlistSelectUpload").value;

    // Basic validation
    if (!file && !songListText) {
      statusMessage.innerHTML = "❌ Please upload a file or paste a song list.";
      return;
    }
    if (!playlistId) {
      statusMessage.innerHTML = "❌ Please select a playlist.";
      return;
    }

    // Reset and show progress bar
    progressContainer.style.display = "block";
    progressBar.style.width = "0%";
    progressText.textContent = "Processing: 0%";
    statusMessage.textContent = "";

    try {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/upload", true);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          progressBar.style.width = `${percent}%`;
          progressText.textContent = `Processing: ${percent}%`;
        }
      };

      xhr.onload = () => {
        if (xhr.status === 200) {
          progressBar.style.width = "100%";
          progressText.textContent = "✅ Done!";
          statusMessage.innerHTML = xhr.responseText;
        } else {
          statusMessage.innerHTML = `❌ Upload failed: ${xhr.statusText}`;
        }
      };

      xhr.onerror = () => {
        statusMessage.innerHTML = "❌ Network error while uploading.";
      };

      xhr.send(formData);
    } catch (err) {
      console.error(err);
      statusMessage.innerHTML = "❌ Error sending request.";
    }
  });
});
// Function to populate playlists dropdown
async function populatePlaylists() {
    try {
        const response = await fetch('/get_playlists');
        const data = await response.json();

        if (data.error) {
            console.error('Error fetching playlists:', data.error);
            return;
        }

        const dropdown = document.getElementById('playlistSelectUpload');
        // Clear existing options except the first one
        dropdown.innerHTML = '<option value="">-- Select a playlist --</option>';

        // Add playlist options
        data.playlists.forEach(playlist => {
            const option = document.createElement('option');
            option.value = playlist.id;
            option.textContent = playlist.title;
            dropdown.appendChild(option);
        });

        console.log('Playlists populated successfully');
    } catch (error) {
        console.error('Error populating playlists:', error);
    }
}

// Call this function after successful login
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in and populate playlists
    checkAuthStatus();
});

// Function to check auth status (you might already have this)
async function checkAuthStatus() {
    try {
        const response = await fetch('/get_playlists');
        if (response.ok) {
            populatePlaylists();
        }
    } catch (error) {
        console.log('User not logged in or error checking auth status');
    }
}

// Also call populatePlaylists after successful login
// Add this to your login success callback
function onLoginSuccess() {
    populatePlaylists();
}