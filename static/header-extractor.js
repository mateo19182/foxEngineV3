document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('csvFile');
    const extractButton = document.getElementById('extractButton');
    const responseArea = document.getElementById('responseArea');
    const fileNameDisplay = document.getElementById('fileName');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const fileInputContainer = document.getElementById('fileInputContainer');
    
    // Add click event to the container to trigger file input
    fileInputContainer.addEventListener('click', (e) => {
        // Prevent click event if the click was on the input itself
        if (e.target !== fileInput) {
            fileInput.click();
        }
    });
    
    // Handle file selection
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const fileName = e.target.files[0].name;
            fileNameDisplay.textContent = fileName;
            fileInputContainer.classList.add('has-file');
            extractButton.disabled = false;
        } else {
            fileNameDisplay.textContent = 'No file selected';
            fileInputContainer.classList.remove('has-file');
            extractButton.disabled = true;
        }
    });
    
    // Parse CSV data from a file
    function parseCSV(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (event) => {
                const csvData = event.target.result;
                const lines = csvData.split('\n');
                const result = [];
                
                for (let i = 0; i < Math.min(10, lines.length); i++) {
                    // Skip empty lines
                    if (lines[i].trim() === '') continue;
                    
                    // Parse CSV line (handling quoted values with commas)
                    const row = [];
                    let inQuotes = false;
                    let currentValue = '';
                    
                    for (let j = 0; j < lines[i].length; j++) {
                        const char = lines[i][j];
                        
                        if (char === '"') {
                            inQuotes = !inQuotes;
                        } else if (char === ',' && !inQuotes) {
                            row.push(currentValue);
                            currentValue = '';
                        } else {
                            currentValue += char;
                        }
                    }
                    
                    // Add the last value
                    row.push(currentValue);
                    result.push(row);
                }
                
                resolve(result);
            };
            
            reader.onerror = () => {
                reject(new Error('Failed to read the file'));
            };
            
            reader.readAsText(file);
        });
    }
    
    // Log to the console and the logs panel
    function logMessage(message, type = 'info') {
        console.log(message);
        // Add to logs panel if it exists
        if (typeof addLogEntry === 'function') {
            addLogEntry({
                timestamp: new Date().toISOString(),
                level: type,
                message: message
            });
        }
    }
    
    // Store original file for later use
    let originalFile = null;
    
    // Read just the sample data from the CSV file
    function readSampleCsv(file, sampleSize = 10) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (event) => {
                const csvData = event.target.result;
                const lines = csvData.split('\n');
                const result = [];
                
                // Only process up to sampleSize non-empty lines
                let processedLines = 0;
                for (let i = 0; i < lines.length && processedLines < sampleSize; i++) {
                    // Skip empty lines
                    if (lines[i].trim() === '') continue;
                    
                    // Parse CSV line (handling quoted values with commas)
                    const row = [];
                    let inQuotes = false;
                    let currentValue = '';
                    
                    for (let j = 0; j < lines[i].length; j++) {
                        const char = lines[i][j];
                        
                        if (char === '"') {
                            inQuotes = !inQuotes;
                        } else if (char === ',' && !inQuotes) {
                            row.push(currentValue);
                            currentValue = '';
                        } else {
                            currentValue += char;
                        }
                    }
                    
                    // Add the last value
                    row.push(currentValue);
                    result.push(row);
                    processedLines++;
                }
                
                resolve(result);
            };
            
            reader.onerror = () => {
                reject(new Error('Failed to read the file'));
            };
            
            // Only read the beginning of the file to get the sample
            const blob = file.slice(0, 50 * 1024); // Read first 50KB which should be enough for sample
            reader.readAsText(blob);
        });
    }
    
    // Read the entire CSV file and add headers
    function readAndDownloadWithHeaders(file, headers, newFilename) {
        logMessage('Reading full file for download...');
        
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (event) => {
                try {
                    const csvData = event.target.result;
                    const lines = csvData.split('\n');
                    
                    // Filter out empty lines
                    const nonEmptyLines = lines.filter(line => line.trim() !== '');
                    
                    // Create CSV content with headers
                    const csvContent = [
                        headers.join(','),
                        ...nonEmptyLines
                    ].join('\n');
                    
                    // Create a blob and download link
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const url = URL.createObjectURL(blob);
                    const downloadLink = document.createElement('a');
                    
                    // Set up download link
                    downloadLink.href = url;
                    downloadLink.setAttribute('download', newFilename);
                    downloadLink.style.display = 'none';
                    
                    // Add to document, trigger click, and clean up
                    document.body.appendChild(downloadLink);
                    downloadLink.click();
                    document.body.removeChild(downloadLink);
                    URL.revokeObjectURL(url);
                    
                    logMessage(`Downloaded file with headers: ${newFilename}`);
                    resolve();
                } catch (error) {
                    logMessage(`Error processing file: ${error.message}`, 'error');
                    reject(error);
                }
            };
            
            reader.onerror = (error) => {
                logMessage(`Error reading file: ${error}`, 'error');
                reject(new Error('Failed to read the file'));
            };
            
            reader.readAsText(file);
        });
    }
    
    // Handle extract button click
    extractButton.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a CSV file first');
            return;
        }
        
        if (!file.name.toLowerCase().endsWith('.csv')) {
            showError('Please select a valid CSV file');
            return;
        }
        
        // Store the original file for later use
        originalFile = file;
        
        // Show loading state
        setLoading(true);
        
        try {
            // Parse the CSV file locally to get sample data for header extraction
            logMessage('Parsing CSV file locally to extract sample data');
            const sampleData = await readSampleCsv(file);
            
            if (sampleData.length === 0) {
                throw new Error('The CSV file appears to be empty');
            }
            
            // Prepare the sample data to send as JSON
            logMessage(`Sending sample data to server (${sampleData.length} rows)`);
            
            // Send the sample data to the server as JSON
            const response = await fetch('/api/tools/extract-headers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    csv_data: sampleData
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server responded with ${response.status}: ${errorText}`);
            }
            
            const result = await response.json();
            logMessage(`Headers extracted successfully: ${JSON.stringify(result.headers)}`);
            displayResults(result);
        } catch (error) {
            logMessage(`Error: ${error.message}`, 'error');
            showError(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    });
    
    function displayResults(result) {
        responseArea.innerHTML = '';
        
        // Create header section
        const headerSection = document.createElement('div');
        headerSection.className = 'result-section';
        
        // We're now assuming all CSV files don't have headers
        
        const headerTitle = document.createElement('h3');
        headerTitle.textContent = 'Extracted Headers';
        headerSection.appendChild(headerTitle);
        
        // Create headers list
        const headersList = document.createElement('ul');
        headersList.className = 'headers-list';
        
        if (result.headers && result.headers.length > 0) {
            result.headers.forEach((header, index) => {
                const headerItem = document.createElement('li');
                headerItem.className = 'header-item';
                headerItem.innerHTML = `<span class="header-index">${index + 1}</span><span class="header-name">${header}</span>`;
                headersList.appendChild(headerItem);
            });
        } else {
            const noHeaders = document.createElement('p');
            noHeaders.textContent = 'No headers could be extracted';
            headersList.appendChild(noHeaders);
        }
        
        headerSection.appendChild(headersList);
        responseArea.appendChild(headerSection);
        
        // Add sample data section
        if (result.sample_data && result.sample_data.length > 0) {
            const sampleSection = document.createElement('div');
            sampleSection.className = 'result-section';
            
            const sampleTitle = document.createElement('h3');
            sampleTitle.textContent = 'Sample Data';
            sampleSection.appendChild(sampleTitle);
            
            const sampleTable = document.createElement('table');
            sampleTable.className = 'sample-table';
            
            // Add header row
            const headerRow = document.createElement('tr');
            result.headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            sampleTable.appendChild(headerRow);
            
            // Add data rows
            result.sample_data.forEach(row => {
                const tr = document.createElement('tr');
                row.forEach(cell => {
                    const td = document.createElement('td');
                    td.textContent = cell;
                    tr.appendChild(td);
                });
                sampleTable.appendChild(tr);
            });
            
            sampleSection.appendChild(sampleTable);
            responseArea.appendChild(sampleSection);
        }
        
        // Add action buttons
        const actionSection = document.createElement('div');
        actionSection.className = 'action-section';
        
        // Add copy button
        if (result.headers && result.headers.length > 0) {
            const copyButton = document.createElement('button');
            copyButton.className = 'btn copy-btn';
            copyButton.innerHTML = '<i class="fas fa-copy"></i> Copy Headers';
            copyButton.onclick = () => {
                navigator.clipboard.writeText(result.headers.join(','))
                    .then(() => {
                        copyButton.innerHTML = '<i class="fas fa-check"></i> Copied!';
                        setTimeout(() => {
                            copyButton.innerHTML = '<i class="fas fa-copy"></i> Copy Headers';
                        }, 2000);
                    })
                    .catch(err => {
                        console.error('Failed to copy: ', err);
                        logMessage('Failed to copy headers: ' + err.message, 'error');
                    });
            };
            actionSection.appendChild(copyButton);
            
            // Add download button if we have the original file
            if (originalFile) {
                const downloadButton = document.createElement('button');
                downloadButton.className = 'btn download-btn';
                downloadButton.innerHTML = '<i class="fas fa-download"></i> Download CSV with Headers';
                downloadButton.onclick = async () => {
                    try {
                        // Disable the button during processing
                        downloadButton.disabled = true;
                        downloadButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                        
                        // Generate a filename with '-with-headers' suffix
                        const originalName = originalFile.name;
                        const nameParts = originalName.split('.');
                        const extension = nameParts.pop();
                        const baseName = nameParts.join('.');
                        const newFilename = `${baseName}-with-headers.${extension}`;
                        
                        // Read the full file and download it with headers
                        await readAndDownloadWithHeaders(originalFile, result.headers, newFilename);
                        
                        // Update button state
                        downloadButton.disabled = false;
                        downloadButton.innerHTML = '<i class="fas fa-check"></i> Downloaded!';
                        setTimeout(() => {
                            downloadButton.innerHTML = '<i class="fas fa-download"></i> Download CSV with Headers';
                        }, 2000);
                    } catch (error) {
                        // Handle errors
                        showError(`Error downloading file: ${error.message}`);
                        downloadButton.disabled = false;
                        downloadButton.innerHTML = '<i class="fas fa-download"></i> Download CSV with Headers';
                    }
                };
                actionSection.appendChild(downloadButton);
            }
        }
        
        responseArea.appendChild(actionSection);
        
        // Show the response area
        responseArea.classList.remove('hidden');
    }
    
    function showError(message) {
        responseArea.innerHTML = `<div class="error-message"><i class="fas fa-exclamation-circle"></i> ${message}</div>`;
        responseArea.classList.remove('hidden');
    }
    
    function setLoading(isLoading) {
        if (isLoading) {
            loadingIndicator.classList.remove('hidden');
            extractButton.disabled = true;
        } else {
            loadingIndicator.classList.add('hidden');
            extractButton.disabled = false;
        }
    }
});
