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
  const multivalueInput = document.getElementById("multivalueInput");
  const multivalueGroup = document.getElementById("multivalueGroup");

  let fileData = null;
  let parsedData = [];  // Will store the raw parsed data with arrays preserved
  let headers = [];

  // Listen for file selection changes
  fileInput.addEventListener("change", function(evt) {
    if (evt.target.files && evt.target.files[0]) {
      fileData = evt.target.files[0];
      // Show/hide delimiter input based on file type
      const isCSV = fileData.name.endsWith(".csv");
      delimiterGroup.style.display = isCSV ? "flex" : "none";
      
      const reader = new FileReader();
      reader.onload = function(e) {
        const text = e.target.result;
        try {
          if (isCSV) {
            const delimiter = delimiterInput.value || ",";
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

  // Add listener for multivalue separator changes
  if (multivalueInput) {
    multivalueInput.addEventListener("input", function() {
      if (parsedData.length > 0) {
        // Just update the preview with the new separator
        renderPreviewTable(headers, parsedData);
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

    // Parse headers using the CSV parser
    headers = parseCSVLine(lines[0], delimiter).map(h => h.trim());

    // Parse data rows and preserve raw quoted values
    parsedData = lines.slice(1).map(line => {
        const values = parseCSVLine(line, delimiter);
        
        // Store raw values, preserving quotes for potential arrays
        return values.map(val => {
            if (val && val.includes(",")) {
                return {
                    type: 'multivalue',
                    values: val.split(",").map(v => v.trim()).filter(v => v)
                };
            }
            return val ? val.trim() : null;
        });
    });

    renderPreviewTable(headers, parsedData);
  }

  // Helper function to properly parse CSV lines
  function parseCSVLine(line, delimiter) {
    const values = [];
    let currentValue = '';
    let insideQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"') {
            if (!insideQuotes) {
                insideQuotes = true;
            } else if (line[i + 1] === '"') {
                currentValue += '"';
                i++; // Skip next quote
            } else {
                insideQuotes = false;
            }
        } else if (char === delimiter && !insideQuotes) {
            values.push(currentValue.trim());
            currentValue = '';
        } else {
            currentValue += char;
        }
    }

    values.push(currentValue.trim());
    return values;
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
      parsedData = data.map(record => 
        headers.map(h => {
          const value = record[h];
          if (Array.isArray(value)) {
            return {
              type: 'multivalue',
              values: value
            };
          }
          return value;
        })
      );
    } else if (data.rows && Array.isArray(data.rows)) {
      if (data.rows.length === 0) {
        showStatus("JSON file contains no rows.", "error");
        return;
      }
      headers = Object.keys(data.rows[0]);
      parsedData = data.rows.map(record => 
        headers.map(h => {
          const value = record[h];
          if (Array.isArray(value)) {
            return {
              type: 'multivalue',
              values: value
            };
          }
          return value;
        })
      );
    } else {
      showStatus("Unrecognized JSON format.", "error");
    }
    
    renderPreviewTable(headers, parsedData);
  }

  // Render preview table with proper array formatting
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
      dataRows[r].forEach(value => {
        const td = document.createElement("td");
        if (value && value.type === 'multivalue') {
          td.textContent = value.values.join(", ");
          td.classList.add('multivalue-cell');
        } else {
          td.textContent = value || "";
        }
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
      <input type="text" placeholder="Value (use commas for multiple values)" class="fixed-field-value" />
      <button type="button" class="icon-btn delete-field" title="Remove Field">
        <i class="fas fa-times"></i>
      </button>
    `;

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

    // Get fixed fields
    const fixedFields = {};
    document.querySelectorAll('.fixed-field-row').forEach(row => {
      const name = row.querySelector('.fixed-field-name').value.trim();
      const value = row.querySelector('.fixed-field-value').value.trim();
      if (name && value) {
        // Handle multivalue fixed fields
        if (value.includes(',')) {
          fixedFields[name] = value.split(',').map(v => v.trim()).filter(v => v);
        } else {
          fixedFields[name] = value;
        }
      }
    });

    // Build FormData for POSTing.
    const formData = new FormData();
    formData.append("file", fileData);
    formData.append("delimiter", delimiterInput.value || ",");
    formData.append("column_mappings", JSON.stringify(columnMappings));
    formData.append("included_columns", JSON.stringify(includedColumns));
    formData.append("fixed_fields", JSON.stringify(fixedFields));

    // Show progress indication
    uploadProgress.style.display = "block";
    progressFill.style.width = "0%";
    progressText.textContent = "0%";
    showStatus("Uploading...", "info");

    // Create and configure XMLHttpRequest
    const xhr = new XMLHttpRequest();
    
    // Upload progress handler
    xhr.upload.onprogress = function(e) {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        progressFill.style.width = percentComplete + '%';
        progressText.textContent = Math.round(percentComplete) + '%';
      }
    };

    // Upload complete handler
    xhr.onload = function() {
      if (xhr.status === 200) {
        const result = JSON.parse(xhr.responseText);
        const message = `Upload completed:
          • ${result.inserted_count} new records added
          • ${result.updated_count} records updated`;
        showStatus(message, "success");
        progressFill.style.width = "100%";
        progressText.textContent = "100%";
        
        // Reset the form
        resetUploadForm();
        
        // Refresh the logs panel
        if (typeof refreshLogs === 'function') {
          refreshLogs();
        }
      } else {
        showStatus("Upload failed: " + xhr.statusText, "error");
      }
      
      // Hide progress bar after 2 seconds
      setTimeout(() => {
        uploadProgress.style.display = "none";
      }, 2000);
    };

    // Error handler
    xhr.onerror = function() {
      showStatus("Upload failed: Network error", "error");
      setTimeout(() => {
        uploadProgress.style.display = "none";
      }, 2000);
    };

    // Send the request
    xhr.open("POST", "/api/records/upload-file", true);
    xhr.send(formData);
  }

  function resetUploadForm() {
    // Reset file input
    fileInput.value = '';
    fileData = null;
    parsedData = [];
    headers = [];
    
    // Clear preview table
    previewHead.innerHTML = '';
    previewBody.innerHTML = '';
    
    // Reset fixed fields
    fixedFieldsContainer.innerHTML = '';
    
    // Reset delimiter input and hide it
    delimiterInput.value = ',';
    delimiterGroup.style.display = 'none';
  }

  // Utility function to display status messages.
  function showStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = "status-message " + type;
  }
}); 