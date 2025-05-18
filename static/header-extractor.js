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
        
        // Show loading state
        setLoading(true);
        
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // Send the file to the server
            const response = await fetch('/api/tools/extract-headers', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            displayResults(result);
        } catch (error) {
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
                    });
            };
            responseArea.appendChild(copyButton);
        }
        
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
