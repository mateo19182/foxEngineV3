// Logs functionality
const logs = {
  async update() {
    try {
      const response = await fetch('/api/records/logs?limit=50');
      const logs = await response.json();
      const logsList = document.getElementById('logsList');
      
      if (logsList) {
        logsList.innerHTML = logs.map(log => {
          const timestamp = new Date(log.timestamp).toLocaleString();
          const statusClass = log.status_code >= 400 ? 'error' : 'success';
          const methodBadge = log.method ? `<span class="method-badge ${log.method.toLowerCase()}">${log.method}</span>` : '';
          
          return `
            <li class="log-entry ${statusClass}">
              <div class="log-header">
                ${methodBadge}
                <span class="endpoint">${log.endpoint}</span>
                <span class="timestamp">${timestamp}</span>
              </div>
              <div class="log-details">
                <span class="status">Status: ${log.status_code}</span>
                ${log.error ? `<span class="error-message">Error: ${log.error}</span>` : ''}
                ${log.additional_info ? `<span class="info">${log.additional_info}</span>` : ''}
              </div>
            </li>
          `;
        }).join('');
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  },

  toggle() {
    const panel = document.getElementById('logsPanel');
    const btn = panel.querySelector('.toggle-logs-btn i');
    panel.classList.toggle('collapsed');
    btn.classList.toggle('fa-chevron-up');
    btn.classList.toggle('fa-chevron-down');
  },

  init() {
    // Initial update
    this.update();
    
    // Set up periodic updates
    setInterval(() => this.update(), 30000);
    
    // Set up toggle functionality
    const panel = document.getElementById('logsPanel');
    if (panel) {
      panel.querySelector('.logs-panel-header').addEventListener('click', () => this.toggle());
    }
  }
};

// Initialize logs when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => logs.init()); 