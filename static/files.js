document.addEventListener('DOMContentLoaded', function() {
    fetchFiles();
});

async function fetchFiles() {
    try {
        console.log('Fetching files...');
        const response = await fetch('/api/files/list');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const files = await response.json();
        console.log('Received files:', files);
        if (!Array.isArray(files)) {
            throw new Error('Expected array of files from server');
        }
        renderFilesTable(files);
    } catch (error) {
        console.error('Error fetching files:', error);
        const tbody = document.getElementById('filesTableBody');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" class="error-message">Error loading files: ${error.message}</td></tr>`;
        }
    }
}

function renderFilesTable(files) {
    const tbody = document.getElementById('filesTableBody');
    tbody.innerHTML = '';

    files.forEach(file => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${file.original_filename}</td>
            <td>${new Date(file.uploaded_at).toLocaleString()}</td>
            <td>${formatFileSize(file.size)}</td>
            <td>${file.content_type}</td>
            <td>${file.uploaded_by}</td>
            <td>
                <button class="icon-btn" onclick='showFileDetails(${JSON.stringify(file)})' title="View Details">
                    <i class="fas fa-info-circle"></i>
                </button>
                <button class="icon-btn" onclick='downloadFile("${file._id}")' title="Download">
                    <i class="fas fa-download"></i>
                </button>
                <button class="icon-btn" onclick='deleteFile("${file._id}")' title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showFileDetails(file) {
    const modal = document.getElementById('fileDetailsModal');
    const content = document.getElementById('fileDetailsContent');
    
    content.innerHTML = `
        <div class="file-details">
            <p><strong>Original Filename:</strong> <span class="text-break">${file.original_filename}</span></p>
            <p><strong>Stored Filename:</strong> <span class="text-break">${file.stored_filename}</span></p>
            <p><strong>Upload Date:</strong> ${new Date(file.uploaded_at).toLocaleString()}</p>
            <p><strong>Size:</strong> ${formatFileSize(file.size)}</p>
            <p><strong>Type:</strong> ${file.content_type}</p>
            <p><strong>Uploaded By:</strong> ${file.uploaded_by}</p>
            <p><strong>File Hash:</strong> <span class="text-break">${file.file_hash}</span></p>
        </div>
    `;
    
    modal.style.display = 'flex';
    
    // Add click event listener to close modal when clicking outside
    modal.onclick = function(event) {
        if (event.target === modal) {
            closeFileDetailsModal();
        }
    };
}

async function downloadFile(fileId) {
    try {
        window.location.href = `/api/files/${fileId}/download`;
    } catch (error) {
        console.error('Error downloading file:', error);
    }
}

async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) return;
    
    try {
        const response = await fetch(`/api/files/${fileId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            fetchFiles();
        } else {
            alert('Error deleting file');
        }
    } catch (error) {
        console.error('Error deleting file:', error);
    }
}

window.closeFileDetailsModal = function() {
    const modal = document.getElementById('fileDetailsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal when clicking on overlay (outside of the modal content)
window.addEventListener('click', function(event) {
    const modalOverlay = document.getElementById('fileDetailsModal');
    // If the click target is the overlay, not the inner modal, hide the overlay.
    if (event.target === modalOverlay) {
        modalOverlay.style.display = 'none';
    }
}); 