document.addEventListener("DOMContentLoaded", function() {
  const fileInput = document.getElementById("fileInput");
  const previewHead = document.getElementById("previewHead");
  const previewBody = document.getElementById("previewBody");
  const uploadStatus = document.getElementById("uploadStatus");
  const uploadProgress = document.getElementById("uploadProgress");
  const progressFill = uploadProgress.querySelector(".progress-fill");
  const progressText = uploadProgress.querySelector(".progress-text");
  const uploadBtn = document.getElementById("uploadBtn");
  const addFixedFieldBtn = document.getElementById("addFixedFieldBtn");
  const fixedFieldsContainer = document.getElementById("fixedFields");
  const delimiterInput = document.getElementById("delimiterInput");
  const delimiterGroup = document.getElementById("delimiterGroup");

  let fileData = null;
  let parsedData = [];
  let headers = [];

  // Listen for file selection changes
  fileInput.addEventListener("change", function(evt) {
    const delimiterGroup = document.getElementById("delimiterGroup");
    
    if (evt.target.files && evt.target.files[0]) {
      fileData = evt.target.files[0];
      // Show/hide delimiter input based on file type
      delimiterGroup.style.display = fileData.name.endsWith(".csv") ? "flex" : "none";
      
      const reader = new FileReader();
      reader.onload = function(e) {
        const text = e.target.result;
        try {
          if (fileData.name.endsWith(".csv")) {
            const delimiter = document.getElementById("delimiterInput").value || ",";
            parseCSV(text, delimiter);
          } else if (fileData.name.endsWith(".json")) {
            parseJSON(text);
          } else {
            showStatus("Unsupported file type", "error");
          }
        } catch (err) {
          showStatus("Error parsing file: " + err.message, "error");
        }
      };
      reader.readAsText(fileData);
    } else {
      delimiterGroup.style.display = "none";
    }
  });

  // Add this after the file input handler
  if (delimiterInput) {
    delimiterInput.addEventListener("input", function() {
      if (fileData && fileData.name.endsWith(".csv")) {
        const reader = new FileReader();
        reader.onload = function(e) {
          parseCSV(e.target.result, delimiterInput.value || ",");
        };
        reader.readAsText(fileData);
      }
    });
  }

  // Parse CSV file – first row as header and following rows as data
  function parseCSV(text, delimiter) {
    const lines = text.split(/\r?\n/).filter(line => line.trim() !== "");
    if (lines.length < 2) {
        showStatus("CSV file must have a header and at least one data row.", "error");
        return;
    }

    // Parse headers using the specified delimiter
    headers = lines[0].split(delimiter).map(s => s.trim());

    // Parse data rows with special handling for array fields
    parsedData = lines.slice(1).map(line => {
        const values = [];
        let currentValue = '';
        let insideQuotes = false;

        // Parse each character to handle quoted values properly
        for (let char of line) {
            if (char === '"') {
                insideQuotes = !insideQuotes;
            } else if (char === delimiter && !insideQuotes) {
                values.push(currentValue.trim());
                currentValue = '';
            } else {
                currentValue += char;
            }
        }
        values.push(currentValue.trim());
        return values;
    });

    renderPreviewTable(headers, parsedData);
  }

  // Parse JSON file – support both direct list of records or an object with "rows"
  function parseJSON(text) {
    const data = JSON.parse(text);
    if (Array.isArray(data)) {
      if (data.length === 0) {
        showStatus("JSON file is empty.", "error");
        return;
      }
      headers = Object.keys(data[0]);
      parsedData = data.map(record => headers.map(h => record[h] || ""));
      renderPreviewTable(headers, parsedData);
    } else if (data.rows && Array.isArray(data.rows)) {
      if (data.rows.length === 0) {
        showStatus("JSON file contains no rows.", "error");
        return;
      }
      headers = Object.keys(data.rows[0]);
      parsedData = data.rows.map(record => headers.map(h => record[h] || ""));
      renderPreviewTable(headers, parsedData);
    } else {
      showStatus("Unrecognized JSON format.", "error");
    }
  }

  // Render preview table: headers with input for renaming and rows for preview
  function renderPreviewTable(headers, dataRows) {
    previewHead.innerHTML = "";
    const thRow = document.createElement("tr");
    
    headers.forEach((header, index) => {
      const th = document.createElement("th");
      th.innerHTML = `
        <div class="column-header">
          <div class="checkbox-wrapper">
            <input type="checkbox" id="col-${index}" checked data-index="${index}">
            <label for="col-${index}">Include</label>
          </div>
          <input type="text" class="column-name" value="${header}" data-index="${index}">
        </div>
      `;

      // Add change listener to checkbox to toggle column visibility
      const checkbox = th.querySelector('input[type="checkbox"]');
      checkbox.addEventListener('change', function() {
        const columnCells = document.querySelectorAll(`td:nth-child(${index + 1}), th:nth-child(${index + 1})`);
        columnCells.forEach(cell => {
          if (this.checked) {
            cell.classList.remove('dropped-column');
          } else {
            cell.classList.add('dropped-column');
          }
        });
      });

      thRow.appendChild(th);
    });
    
    previewHead.appendChild(thRow);

    // Render preview rows (limit to first 10)
    previewBody.innerHTML = "";
    const rowsToShow = Math.min(dataRows.length, 10);
    for (let r = 0; r < rowsToShow; r++) {
      const tr = document.createElement("tr");
      dataRows[r].forEach(cellValue => {
        const td = document.createElement("td");
        td.textContent = cellValue;
        tr.appendChild(td);
      });
      previewBody.appendChild(tr);
    }
  }

  // Add a fixed field row when the corresponding button is clicked
  addFixedFieldBtn.addEventListener("click", addFixedField);

  function addFixedField() {
    const container = document.getElementById("fixedFields");
    const fieldDiv = document.createElement("div");
    fieldDiv.classList.add("fixed-field-row");
    fieldDiv.innerHTML = `
      <input type="text" placeholder="Field Name" class="fixed-field-name" />
      <input type="text" placeholder="Value" class="fixed-field-value" />
      <button type="button" class="icon-btn delete-field" title="Remove Field">
        <i class="fas fa-times"></i>
      </button>
    `;

    // Add click handler directly to the delete button
    const deleteBtn = fieldDiv.querySelector('.delete-field');
    deleteBtn.addEventListener('click', () => fieldDiv.remove());

    container.appendChild(fieldDiv);
  }

  // When the Upload button is clicked, gather all data and send to the backend.
  uploadBtn.addEventListener("click", uploadFile);

  function uploadFile() {
    if (!fileData) {
      showStatus("Please select a file first.", "error");
      return;
    }

    // Get column mappings from checkboxes and input fields
    const columnMappings = {};
    const includedColumns = [];
    const checkboxes = previewHead.querySelectorAll('input[type="checkbox"]');
    const nameInputs = previewHead.querySelectorAll('.column-name');

    checkboxes.forEach((checkbox, idx) => {
      if (checkbox.checked) {
        includedColumns.push(idx);
        const newColumnName = nameInputs[idx].value.trim();
        if (newColumnName) {
          columnMappings[idx] = newColumnName;
        }
      }
    });

    console.log('Column Mappings:', columnMappings);
    console.log('Included Columns:', includedColumns);

    // Get fixed fields
    const fixedFields = {};
    document.querySelectorAll('.fixed-field-row').forEach(row => {
      const name = row.querySelector('.fixed-field-name').value.trim();
      const value = row.querySelector('.fixed-field-value').value.trim();
      if (name && value) {
        fixedFields[name] = value;
      }
    });

    // Build FormData for POSTing.
    const formData = new FormData();
    formData.append("file", fileData);
    formData.append("delimiter", document.getElementById("delimiterInput").value || ",");
    formData.append("column_mappings", JSON.stringify(columnMappings));
    formData.append("included_columns", JSON.stringify(includedColumns));
    formData.append("fixed_fields", JSON.stringify(fixedFields));

    // Show a simple progress indication.
    uploadProgress.style.display = "block";
    progressFill.style.width = "0%";
    progressText.textContent = "0%";
    showStatus("Uploading...", "info");

    fetch("/api/records/upload-file", {
      method: "POST",
      body: formData
    })
    .then(response => response.json())
    .then(result => {
      // Show success message with details
      const message = `Upload completed:
        • ${result.inserted_count} records inserted
        ${result.duplicate_count ? `• ${result.duplicate_count} duplicates skipped` : ''}`;
      showStatus(message, "success");
      
      // Fetch and display recent logs
      return fetch("/api/records/logs?limit=5");
    })
    .then(response => response.json())
    .then(logs => {
      // Create and show logs section if it doesn't exist
      let logsSection = document.querySelector('.logs-section');
      if (!logsSection) {
        logsSection = document.createElement('section');
        logsSection.className = 'section logs-section';
        document.querySelector('.container').appendChild(logsSection);
      }
      
      // Display logs
      logsSection.innerHTML = `
        <h3>Recent Activity</h3>
        <div class="logs-container">
          ${logs.map(log => `
            <div class="log-entry ${log.status_code >= 400 ? 'error' : 'success'}">
              <span class="timestamp">${new Date(log.timestamp).toLocaleString()}</span>
              <span class="endpoint">${log.endpoint}</span>
              <span class="status">Status: ${log.status_code}</span>
              ${log.error ? `<span class="error-message">Error: ${log.error}</span>` : ''}
              ${log.additional_info ? `<span class="info">${log.additional_info}</span>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    })
    .catch(error => {
      showStatus("Upload failed: " + error.message, "error");
      
      // Still try to show logs even if upload failed
      fetch("/api/records/logs?limit=5")
        .then(response => response.json())
        .then(logs => {
          let logsSection = document.querySelector('.logs-section');
          if (!logsSection) {
            logsSection = document.createElement('section');
            logsSection.className = 'section logs-section';
            document.querySelector('.container').appendChild(logsSection);
          }
          
          logsSection.innerHTML = `
            <h3>Recent Activity</h3>
            <div class="logs-container">
              ${logs.map(log => `
                <div class="log-entry ${log.status_code >= 400 ? 'error' : 'success'}">
                  <span class="timestamp">${new Date(log.timestamp).toLocaleString()}</span>
                  <span class="endpoint">${log.endpoint}</span>
                  <span class="status">Status: ${log.status_code}</span>
                  ${log.error ? `<span class="error-message">Error: ${log.error}</span>` : ''}
                  ${log.additional_info ? `<span class="info">${log.additional_info}</span>` : ''}
                </div>
              `).join('')}
            </div>
          `;
        });
    })
    .finally(() => {
      setTimeout(() => {
        uploadProgress.style.display = "none";
      }, 2000);
    });
  }

  // Utility function to display status messages.
  function showStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = "status-message " + type;
  }
}); 