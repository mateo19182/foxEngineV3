// scripts.js

function toggleLogs() {
  const panel = document.getElementById('logsPanel');
  const btn = panel.querySelector('.toggle-logs-btn i');
  panel.classList.toggle('collapsed');
  btn.classList.toggle('fa-chevron-up');
  btn.classList.toggle('fa-chevron-down');
}

document.addEventListener("DOMContentLoaded", () => {

  
    // Add Field Button (Home/Search Page)
    const addFieldBtn = document.getElementById("addFieldBtn");
    if (addFieldBtn) {
      addFieldBtn.addEventListener("click", () => {
        const container = document.getElementById("searchFields");
        const div = document.createElement("div");
        div.classList.add("search-row");
        div.innerHTML = `
          <input type="text" placeholder="Field" list="availableFields" class="field-name" />
          <input type="text" placeholder="Value" class="field-value" />
          <button class="icon-btn delete-field" onclick="deleteField(this)" title="Remove Field">
            <i class="fas fa-times"></i>
          </button>
        `;
        container.appendChild(div);
      });
    }
  
    // Upload Page Elements
    const inputCSV = document.getElementById("inputCSV");
    const delimiterInput = document.getElementById("delimiterInput");
    if (inputCSV && delimiterInput) {
      let currentFile = null;
  
      // Set default delimiter to ","
      delimiterInput.value = ",";
  
      inputCSV.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
          currentFile = e.target.files[0];
          previewCSV();
        }
      });
  
      delimiterInput.addEventListener("input", () => {
        if (currentFile) {
          previewCSV();
        }
      });
  
      async function previewCSV() {
        const delim = delimiterInput.value || ",";
        const file = currentFile;
        const text = await file.text();
        const lines = text.split(/\r?\n/).filter(l => l.trim() !== "");
  
        const parsed = lines.map(line => line.split(delim));
        if (!parsed.length) {
          alert("No data found in CSV.");
          return;
        }
  
        // First row as column names
        const columns = parsed[0].map(col => col.trim() || "Unnamed");
        const dataRows = parsed.slice(1);
  
        renderPreviewTable(columns, dataRows);
      }
  
      function renderPreviewTable(columns, dataRows) {
        const headEl = document.getElementById("previewHead");
        const bodyEl = document.getElementById("previewBody");
        headEl.innerHTML = "";
        bodyEl.innerHTML = "";
  
        if (!columns.length) {
          headEl.innerHTML = "<tr><th>No columns</th></tr>";
          return;
        }
  
        // Create headers with checkboxes for inclusion/exclusion
        let thRow = "<tr>";
        columns.forEach((col, idx) => {
          thRow += `
            <th>
              <div class="column-header">
                <input type="checkbox" 
                       class="column-toggle" 
                       data-idx="${idx}" 
                       checked />
                <input type="text" 
                       class="column-name" 
                       data-idx="${idx}" 
                       value="${col}" />
              </div>
            </th>
          `;
        });
        thRow += "</tr>";
        headEl.innerHTML = thRow;
  
        // Display data rows
        const maxPreview = 10;
        for (let r = 0; r < dataRows.length && r < maxPreview; r++) {
          const row = dataRows[r];
          let rowHTML = "<tr>";
          for (let c = 0; c < columns.length; c++) {
            rowHTML += `<td>${row[c] || ""}</td>`;
          }
          rowHTML += "</tr>";
          bodyEl.innerHTML += rowHTML;
        }
      }
  
      // Finalize Upload Button
      const finalizeUploadBtn = document.querySelector("button[onclick='finalizeUpload()']");
      if (finalizeUploadBtn) {
        finalizeUploadBtn.addEventListener("click", finalizeUpload);
      }
  
      async function finalizeUpload() {
        const headInputs = document.querySelectorAll("#previewHead input");
        const columns = [];
        headInputs.forEach(input => {
          const colName = input.value.trim() || "Unnamed";
          columns.push(colName);
        });
  
        const bodyRows = Array.from(document.querySelectorAll("#previewBody tr")).map(tr => {
          return Array.from(tr.querySelectorAll("td")).map(td => td.textContent);
        });
  
        if (!columns.length || !bodyRows.length) {
          alert("No data to upload.");
          return;
        }
  
        const payload = {
          rows: bodyRows,
          columns: columns
        };
  
        try {
          const res = await fetch("/upload-data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          alert(`Inserted ${data.inserted_count} records.`);
          window.location.href = "/";
        } catch (err) {
          console.error(err);
          alert("Upload failed.");
        }
      }
    }

  const body = document.body;


  // Fetch and display the total count
  fetchTotalCount();

  // Fetch and display logs
  async function fetchLogs() {
    try {
        const res = await fetch('/logs');
        const logs = await res.json();
        const logsList = document.getElementById("logsList");
        logsList.innerHTML = ""; // Clear existing logs

        logs.forEach(log => {
            const listItem = document.createElement("li");
            listItem.classList.add("log-entry");

            // Create a structured display for each log entry
            listItem.innerHTML = `
                <strong>Timestamp:</strong> ${new Date(log.timestamp).toLocaleString()}<br/>
                <strong>Endpoint:</strong> ${log.endpoint}<br/>
                <strong>User:</strong> ${log.user}<br/>
                <strong>Status Code:</strong> ${log.status_code}<br/>
                <strong>Error:</strong> ${log.error || 'None'}<br/>
                <strong>Additional Info:</strong> ${log.additional_info || 'None'}<br/>
                <hr/>
            `;
            logsList.appendChild(listItem);
        });
    } catch (err) {
        console.error('Error fetching logs:', err);
    }
  }

  // Call fetchLogs to populate the side panel
  fetchLogs();

  // File Upload Handling
  const inputFile = document.getElementById("inputFile");
  if (inputFile) {
    inputFile.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        const file = e.target.files[0];
        if (file.name.endsWith('.csv')) {
          previewFile(file);
        } else if (file.name.endsWith('.json')) {
          previewJSON(file);
        }
      }
    });
  }

});    
  
  // Search Page Functions (Home/Search)
  async function doSearch() {
    const params = collectSearchParams();
    try {
      // Construct the URL with the correct query parameter
      const url = `/search?query=${encodeURIComponent(params)}&skip=0&limit=50`;
      const res = await fetch(url);
      const data = await res.json();
      renderTable(data);
      const info = document.getElementById("info");
      if (info) info.textContent = `Filters: ${params || "none"}`;
    } catch (err) {
      console.error(err);
      alert("Search error.");
    }
  }
  
async function doDownload() {
    const params = collectSearchParams();
    try {
        const res = await fetch(`/count?params=${params}`);
        const data = await res.json();
        const recordCount = data.total_records;

        if (confirm(`You are about to download ${recordCount} records. Do you want to proceed?`)) {
            window.location.href = `/download-csv?params=${params}`;
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
    console.log(arr);
    return arr.join("&");
  }
  
  // Render Table (Home/Search)
  function renderTable(data) {
    const headEl = document.getElementById("resultsHead");
    const bodyEl = document.getElementById("resultsBody");
    if (!headEl || !bodyEl) return;
  
    headEl.innerHTML = "";
    bodyEl.innerHTML = "";
  
    if (!data || !data.length) {
      headEl.innerHTML = "<tr><th>No records</th></tr>";
      return;
    }
  
    const columns = Object.keys(data[0]);
    let theadHTML = "<tr>";
    columns.forEach(col => {
      theadHTML += `<th>${col}</th>`;
    });
    theadHTML += `<th>Actions</th></tr>`;
    headEl.innerHTML = theadHTML;
  
    data.forEach(row => {
      let rowHTML = "<tr>";
      columns.forEach(col => {
        rowHTML += `<td>${row[col] || ""}</td>`;
      });
      rowHTML += `
        <td>
          <button class="icon-btn" onclick='openEdit(${JSON.stringify(row)})' title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button class="icon-btn" onclick='deleteRecord("${row._id}")' title="Delete">
            <i class="fas fa-trash"></i>
          </button>
        </td>
      `;
      rowHTML += "</tr>";
      bodyEl.innerHTML += rowHTML;
    });
  }
  
  // Delete Record (Home/Search)
  async function deleteRecord(id) {
    if (!confirm("Are you sure you want to delete this record?")) return;
    try {
      const res = await fetch(`/record/${id}`, { method: "DELETE" });
      const result = await res.json();
      if (result.deleted) {
        alert("Record deleted.");
        doSearch();
      } else {
        alert("Delete failed.");
      }
    } catch (err) {
      console.error(err);
      alert("Delete error.");
    }
  }
  
  // Edit Modal Functions (Home/Search)
  function openEdit(row) {
    const overlay = document.getElementById("editOverlay");
    const editId = document.getElementById("editId");
    const editFields = document.getElementById("editFields");
    if (!overlay || !editId || !editFields) return;
  
    overlay.style.display = "flex";
    editId.value = row._id;
    editFields.innerHTML = "";
  
    Object.keys(row).forEach(k => {
      if (k === "_id") return;
      const val = row[k] || "";
      editFields.innerHTML += `
        <div style="margin-bottom:0.5rem;">
          <label>${k}</label><br/>
          <input type="text" name="${k}" value="${val}" style="width:100%;" />
        </div>
      `;
    });
  }
  
  function closeModal() {
    const overlay = document.getElementById("editOverlay");
    if (overlay) overlay.style.display = "none";
  }
  
  async function saveEdit() {
    const editId = document.getElementById("editId");
    const editFields = document.getElementById("editFields");
    if (!editId || !editFields) return;
  
    const id = editId.value;
    const inputs = editFields.querySelectorAll("input");
    const payload = {};
  
    inputs.forEach(input => {
      payload[input.name] = input.value;
    });
  
    try {
      const res = await fetch(`/record/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.updated) {
        alert("Record updated.");
        closeModal();
        doSearch();
      } else {
        alert("Update failed.");
      }
    } catch (err) {
      console.error(err);
      alert("Update error.");
    }
  }
  
  async function fetchTotalCount() {
    try {
      const res = await fetch('/count');
      const data = await res.json();
      const countElement = document.getElementById('totalCount');
      if (countElement) {
        countElement.textContent = `Total Records: ${data.total_records}`;
      }
    } catch (err) {
      console.error('Error fetching total count:', err);
    }
  }


// Add event listener for page load to clear any cached form data
document.addEventListener('DOMContentLoaded', function() {
  // Reset the file input
  const fileInput = document.getElementById("inputFile");
  if (fileInput) {
    fileInput.value = "";
  }
  
  // Clear any previous status messages
  const statusEl = document.getElementById("uploadStatus");
  if (statusEl) {
    statusEl.style.display = "none";
  }
});