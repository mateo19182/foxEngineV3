// scripts.js

// Register all Handlebars helpers first
Handlebars.registerHelper('formatValue', function(value) {
  if (Array.isArray(value)) {
    return value.join(', ');
  } else if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  return value;
});

Handlebars.registerHelper('isSystemField', function(fieldName) {
  const systemFields = ['createdAt', 'lastModified', 'created_by', 'file_source'];
  return systemFields.includes(fieldName);
});

Handlebars.registerHelper('eq', function(a, b) {
  return a === b;
});

Handlebars.registerHelper('json', function(context) {
  return JSON.stringify(context);
});

Handlebars.registerHelper('getPreviewFields', function(record) {
  const preview = {};
  const priorityFields = ['name', 'email', 'username', 'title', 'id', 'type', 'status'];
  
  // First try to get priority fields
  for (const field of priorityFields) {
    if (record[field]) {
      preview[field] = record[field];
      if (Object.keys(preview).length >= 4) break;
    }
  }
  
  // If we don't have enough fields, add other non-id fields
  if (Object.keys(preview).length < 4) {
    for (const [key, value] of Object.entries(record)) {
      if (key !== '_id' && !preview[key] && !key.startsWith('_')) {
        preview[key] = value;
        if (Object.keys(preview).length >= 4) break;
      }
    }
  }

  // Count remaining fields (excluding system and special fields)
  const totalFields = Object.keys(record).filter(key => 
    !key.startsWith('_') && 
    !['createdAt', 'lastModified', 'created_by', 'file_source'].includes(key)
  ).length;
  
  const remainingFields = totalFields - Object.keys(preview).length;
  if (remainingFields > 0) {
    preview._remainingCount = remainingFields;
  }
  
  return preview;
});

// Initialize templates object
let templates = {};

// Add these variables at the top of the file
let currentPage = 1;
let totalResults = 0;
const RESULTS_PER_PAGE = 50;

// Search Page Functions
async function doSearch(page = 1) {
  const recordsContainer = document.getElementById("recordsContainer");
  const resultsCount = document.getElementById("searchResultsCount");
  const prevButton = document.getElementById("prevPage");
  const nextButton = document.getElementById("nextPage");
  const pageInfo = document.getElementById("pageInfo");
  
  if (!recordsContainer) return; // Not on search page
  
  currentPage = page;
  const skip = (page - 1) * RESULTS_PER_PAGE;
  
  recordsContainer.innerHTML = templates.loading();
  resultsCount.textContent = "";

  const params = collectSearchParams();
  try {
    const url = `/api/records/search?query=${encodeURIComponent(params)}&skip=${skip}&limit=${RESULTS_PER_PAGE}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }
    const data = await res.json();
    totalResults = data.total;
    
    if (!data.records || data.records.length === 0) {
      recordsContainer.innerHTML = templates.empty();
      resultsCount.textContent = "(0 results)";
      prevButton.disabled = true;
      nextButton.disabled = true;
      pageInfo.textContent = "Page 1";
    } else {
      recordsContainer.innerHTML = templates.records({ records: data.records });
      const start = skip + 1;
      const end = Math.min(skip + data.records.length, totalResults);
      resultsCount.textContent = `(showing ${start}-${end} of ${totalResults} results)`;
      
      // Update pagination controls
      prevButton.disabled = page === 1;
      nextButton.disabled = end >= totalResults;
      pageInfo.textContent = `Page ${page}`;
    }
  } catch (err) {
    console.error('Search error:', err);
    recordsContainer.innerHTML = '<div class="error-state">Search failed. Please try again.</div>';
    resultsCount.textContent = "";
    prevButton.disabled = true;
    nextButton.disabled = true;
  }
}

async function doDownload() {
  const params = collectSearchParams();
  try {
    const url = `/api/records/search?query=${encodeURIComponent(params)}&skip=0&limit=0`;
    const res = await fetch(url);
    const data = await res.json();
    const recordCount = data.total;

    if (confirm(`You are about to download ${recordCount} records. Do you want to proceed?`)) {
      window.location.href = `/api/records/download-csv?query=${encodeURIComponent(params)}`;
    }
  } catch (err) {
    console.error('Error fetching record count:', err);
    alert('Failed to fetch record count.');
  }
}

function collectSearchParams() {
  const rows = document.querySelectorAll(".search-row");
  const arr = [];
  rows.forEach((row) => {
    const nameEl = row.querySelector(".field-name");
    const valEl = row.querySelector(".field-value");
    if (nameEl && valEl) {
      const fieldName = nameEl.value.trim();
      const fieldValue = valEl.value.trim();
      if (fieldName && fieldValue) {
        arr.push(`${encodeURIComponent(fieldName)}:${encodeURIComponent(fieldValue)}`);
      }
    }
  });
  return arr.join("&");
}

// Delete Record
async function deleteRecord(id) {
  if (!confirm("Are you sure you want to delete this record?")) return;
  try {
    const res = await fetch(`/api/records/record/${id}`, { method: "DELETE" });
    const result = await res.json();
    if (result.deleted) {
      alert("Record deleted.");
      doSearch();
    } else {
      alert("Delete failed.");
    }
  } catch (err) {
    console.error('Delete error:', err);
    alert("Delete error.");
  }
}

// Edit Modal Functions
function openEdit(button) {
  const record = JSON.parse(button.dataset.record);
  const overlay = document.getElementById("editOverlay");
  const modal = overlay.querySelector('.modal');
  
  if (!overlay || !modal) return;
  
  modal.innerHTML = templates.editModal(record);
  overlay.style.display = "flex";
}

function closeModal() {
  const overlay = document.getElementById("editOverlay");
  if (overlay) overlay.style.display = "none";
}

async function saveEdit() {
  try {
    const editId = document.getElementById("editId");
    const inputs = document.querySelectorAll('.record-fields input[type="text"]');
    if (!editId || !inputs.length) {
      console.error('Edit form elements not found');
      return;
    }

    const id = editId.value;
    const payload = {};

    inputs.forEach(input => {
      payload[input.name] = input.value;
    });

    const res = await fetch(`/api/records/record/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (data.updated) {
      alert("Record updated successfully.");
      closeModal();
      doSearch(); // Refresh the records
    } else {
      alert("Update failed.");
    }
  } catch (err) {
    console.error('Error saving edit:', err);
    alert("Update error.");
  }
}

async function fetchTotalCount() {
  try {
    const res = await fetch('/api/records/count');
    const data = await res.json();
    const countElement = document.getElementById('totalCount');
    if (countElement) {
      countElement.textContent = data.total_records;
    }
  } catch (err) {
    console.error('Error fetching total count:', err);
  }
}

// Main initialization
document.addEventListener("DOMContentLoaded", () => {
  try {
    // Check if we're on the search page
    const isSearchPage = window.location.pathname === '/search';
    
    if (isSearchPage) {
      // Compile all templates needed for search page
      templates.loading = Handlebars.compile(document.getElementById("loading-template").innerHTML);
      templates.empty = Handlebars.compile(document.getElementById("empty-template").innerHTML);
      templates.records = Handlebars.compile(document.getElementById("records-template").innerHTML);
      templates.recordModal = Handlebars.compile(document.getElementById("record-modal-template").innerHTML);

      // Add Field Button (Search Page)
      const addFieldBtn = document.getElementById("addFieldBtn");
      if (addFieldBtn) {
        addFieldBtn.addEventListener("click", () => {
          const container = document.getElementById("searchFields");
          const div = document.createElement("div");
          div.classList.add("search-row");
          div.innerHTML = `
            <input type="text" placeholder="Field" list="availableFields" class="field-name" />
            <input type="text" placeholder="Value" class="field-value" />
            <button class="icon-btn delete-field" onclick="this.parentElement.remove()" title="Remove Field">
              <i class="fas fa-times"></i>
            </button>
          `;
          container.appendChild(div);
        });
      }

      // Initial search
      doSearch();

      // Add pagination event listeners
      const prevButton = document.getElementById("prevPage");
      const nextButton = document.getElementById("nextPage");
      
      if (prevButton && nextButton) {
        prevButton.addEventListener("click", () => {
          if (currentPage > 1) {
            doSearch(currentPage - 1);
          }
        });
        
        nextButton.addEventListener("click", () => {
          const maxPages = Math.ceil(totalResults / RESULTS_PER_PAGE);
          if (currentPage < maxPages) {
            doSearch(currentPage + 1);
          }
        });
      }
    }

    // Fetch total count for pages that need it
    const needsCount = document.getElementById('totalCount');
    if (needsCount) {
      fetchTotalCount();
      setInterval(fetchTotalCount, 30000);
    }

  } catch (err) {
    console.error('Error initializing:', err);
  }
});

// Toggle record details
function toggleDetails(id) {
  const card = document.querySelector(`.record-card[data-id="${id}"]`);
  const details = card.querySelector('.record-details');
  const btn = card.querySelector('.view-details i');
  
  if (details.style.display === 'none') {
    details.style.display = 'block';
    btn.classList.remove('fa-chevron-down');
    btn.classList.add('fa-chevron-up');
  } else {
    details.style.display = 'none';
    btn.classList.remove('fa-chevron-up');
    btn.classList.add('fa-chevron-down');
  }
}

// Updated viewRecord function for edit mode
function viewRecord(button) {
  try {
    const record = JSON.parse(button.dataset.record);
    const overlay = document.getElementById("editOverlay");
    const modal = overlay.querySelector('.modal');
    
    if (!overlay || !modal) {
      console.error('Modal elements not found');
      return;
    }
    
    // Pass readOnly as false for editable mode
    modal.innerHTML = templates.recordModal(Object.assign({}, record, { readOnly: false }));
    overlay.style.display = "flex";
  } catch (err) {
    console.error('Error viewing record:', err);
  }
}

// New function for record card click in read-only mode
function recordCardClicked(recordJson) {
  try {
    const record = JSON.parse(recordJson);
    const overlay = document.getElementById("editOverlay");
    const modal = overlay.querySelector('.modal');
    
    if (!overlay || !modal) {
      console.error('Modal elements not found');
      return;
    }
    
    // Set readOnly flag to true
    record.readOnly = true;
    modal.innerHTML = templates.recordModal(record);
    overlay.style.display = "flex";
  } catch (err) {
    console.error('Error viewing record details:', err);
  }
}