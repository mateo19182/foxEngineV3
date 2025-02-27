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
      // Show/hide delimiter and multivalue inputs based on file type
      const isCSV = fileData.name.endsWith(".csv");
      delimiterGroup.style.display = isCSV ? "flex" : "none";
      multivalueGroup.style.display = isCSV ? "flex" : "none";
      
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
      multivalueGroup.style.display = "none";
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
            if (val && val.startsWith('"') && val.endsWith('"')) {
                // Store the raw quoted value for later interpretation
                return {
                    type: 'quoted',
                    raw: val.slice(1, -1)  // Remove outer quotes but preserve everything else
                };
            }
            return val;
        });
    });

    renderPreviewTable(headers, parsedData);
  }

  // Helper function to properly parse CSV lines
  function parseCSVLine(line, delimiter) {
    const values = [];
    let currentValue = '';
    let insideQuotes = false;
    let previousChar = '';
    let i = 0;

    while (i < line.length) {
        const char = line[i];

        if (char === '"') {
            if (!insideQuotes) {
                // Starting a quoted field
                insideQuotes = true;
                currentValue += char;  // Keep the quotes in the value
            } else if (line[i + 1] === '"') {
                // Escaped quote inside quoted field
                currentValue += '""';  // Keep escaped quotes as-is
                i++; // Skip next quote
            } else {
                // Ending a quoted field
                insideQuotes = false;
                currentValue += char;  // Keep the quotes in the value
            }
        } else if (char === delimiter && !insideQuotes) {
            // End of field
            values.push(currentValue);
            currentValue = '';
        } else {
            currentValue += char;
        }

        previousChar = char;
        i++;
    }

    // Don't forget the last field
    values.push(currentValue);

    return values;
  }

  // Helper function to unescape CSV quoted values
  function unescapeCSV(str) {
    return str.replace(/""/g, '"');
  }

  // Helper function to split string by separator while preserving quoted substrings
  function splitPreservingQuotes(str, separator) {
    const parts = [];
    let currentPart = '';
    let insideQuotes = false;
    
    for (let i = 0; i < str.length; i++) {
        const char = str[i];
        
        if (char === '"') {
            insideQuotes = !insideQuotes;
            currentPart += char;
        } else if (char === separator && !insideQuotes) {
            parts.push(currentPart);
            currentPart = '';
        } else {
            currentPart += char;
        }
    }
    
    // Add the last part
    if (currentPart) {
        parts.push(currentPart);
    }
    
    return parts;
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
      parsedData = data.map(record => headers.map(h => record[h]));
      renderPreviewTable(headers, parsedData);
    } else if (data.rows && Array.isArray(data.rows)) {
      if (data.rows.length === 0) {
        showStatus("JSON file contains no rows.", "error");
        return;
      }
      headers = Object.keys(data.rows[0]);
      parsedData = data.rows.map(record => headers.map(h => record[h]));
      renderPreviewTable(headers, parsedData);
    } else {
      showStatus("Unrecognized JSON format.", "error");
    }
  }

  // Helper function to interpret a potentially quoted value based on current separator
  function interpretValue(value) {
    if (value && typeof value === 'object' && value.type === 'quoted') {
        const multiSep = multivalueInput.value || ",";
        // Check if this is actually a multivalue field
        const parts = splitPreservingQuotes(value.raw, multiSep);
        if (parts.length > 1) {
            return parts.map(p => {
                // Remove any remaining quotes and unescape
                p = p.trim();
                if (p.startsWith('"') && p.endsWith('"')) {
                    p = p.slice(1, -1);
                }
                return unescapeCSV(p);
            });
        }
        // Single value, just unescape it
        return unescapeCSV(value.raw);
    }
    return value;
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
        // Interpret the value based on current separator settings
        const interpretedValue = interpretValue(value);
        if (Array.isArray(interpretedValue)) {
          td.textContent = interpretedValue.join(multivalueInput.value || ",");
        } else {
          td.textContent = interpretedValue || "";
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
    formData.append("delimiter", delimiterInput.value || ",");
    formData.append("multivalue_separator", multivalueInput.value || ",");
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
      
      // Reset the form
      resetUploadForm();
      
      // Refresh the logs panel
      if (typeof refreshLogs === 'function') {
        refreshLogs();
      }
    })
    .catch(error => {
      showStatus("Upload failed: " + error.message, "error");
      
      // Refresh logs even if upload failed
      if (typeof refreshLogs === 'function') {
        refreshLogs();
      }
    })
    .finally(() => {
      setTimeout(() => {
        uploadProgress.style.display = "none";
      }, 2000);
    });
  }

  // Add this new function to reset the form
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
    
    // Reset delimiter and multivalue inputs and hide them
    delimiterInput.value = ',';
    multivalueInput.value = ',';
    delimiterGroup.style.display = 'none';
    multivalueGroup.style.display = 'none';
  }

  // Utility function to display status messages.
  function showStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = "status-message " + type;
  }
}); 