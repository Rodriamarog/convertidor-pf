document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const selectedFile = document.getElementById('selected-file');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const removeFileBtn = document.getElementById('remove-file');
    const convertBtn = document.getElementById('convert-btn');
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const resultSection = document.getElementById('result-section');
    const successResult = document.getElementById('success-result');
    const errorResult = document.getElementById('error-result');
    const errorMessage = document.getElementById('error-message');
    const downloadBtn = document.getElementById('download-btn');
    const convertAnotherBtn = document.getElementById('convert-another-btn');
    const tryAgainBtn = document.getElementById('try-again-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('status-text');
    const toggleLogBtn = document.getElementById('toggle-log');
    const logContainer = document.getElementById('log-container');
    
    // Variables
    let selectedPdfFile = null;
    let currentJobId = null;
    let statusCheckInterval = null;
    
    // Format file size
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' bytes';
        else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        else return (bytes / 1048576).toFixed(1) + ' MB';
    }
    
    // Handle file selection
    function handleFileSelect(file) {
        if (file && file.type === 'application/pdf') {
            selectedPdfFile = file;
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            selectedFile.classList.remove('hidden');
            convertBtn.disabled = false;
        } else {
            alert('Por favor selecciona un archivo PDF válido.');
        }
    }
    
    // Reset the form
    function resetForm() {
        selectedPdfFile = null;
        fileInput.value = '';
        selectedFile.classList.add('hidden');
        convertBtn.disabled = true;
        
        // Reset sections
        uploadSection.classList.remove('hidden');
        processingSection.classList.add('hidden');
        resultSection.classList.add('hidden');
        successResult.classList.add('hidden');
        errorResult.classList.add('hidden');
        
        // Reset progress
        progressBar.style.width = '0%';
        statusText.textContent = 'Inicializando...';
        logContainer.textContent = '';
        logContainer.classList.add('hidden');
        toggleLogBtn.textContent = 'Mostrar';
        
        // Clear any running intervals
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
    }
    
    // Start conversion process
    async function startConversion() {
        if (!selectedPdfFile) return;
        
        // Show processing section
        uploadSection.classList.add('hidden');
        processingSection.classList.remove('hidden');
        
        // Create form data
        const formData = new FormData();
        formData.append('file', selectedPdfFile);
        
        try {
            // Send the file to the server
            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`El servidor respondió con ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            currentJobId = data.job_id;
            
            // Start checking status
            checkStatus();
            statusCheckInterval = setInterval(checkStatus, 2000);
            
        } catch (error) {
            showError(error.message);
        }
    }
    
    // Check conversion status
    async function checkStatus() {
        if (!currentJobId) return;
        
        try {
            const response = await fetch(`/api/status/${currentJobId}`);
            
            if (!response.ok) {
                throw new Error(`El servidor respondió con ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update progress based on status
            updateProgress(data);
            
            // Check if processing is complete
            if (data.status === 'completed') {
                showSuccess(data.download_url);
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
            } else if (data.status === 'failed') {
                showError(data.error || 'La conversión falló');
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
            }
            
        } catch (error) {
            showError(error.message);
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
    }
    
    // Update progress UI
    function updateProgress(data) {
        // Update log if available
        if (data.log) {
            logContainer.textContent = data.log;
        }
        
        // Update status text and progress bar
        let progressPercent = 0;
        
        switch (data.status) {
            case 'queued':
                statusText.textContent = 'En cola de espera...';
                progressPercent = 10;
                break;
            case 'processing':
                // Try to estimate progress from the log
                if (data.log) {
                    if (data.log.includes('5. Optimizing with compression')) {
                        statusText.textContent = 'Optimizando con compresión...';
                        progressPercent = 80;
                    } else if (data.log.includes('4. Converting to grayscale')) {
                        statusText.textContent = 'Convirtiendo a escala de grises...';
                        progressPercent = 60;
                    } else if (data.log.includes('3. Removing blank pages')) {
                        statusText.textContent = 'Eliminando páginas en blanco...';
                        progressPercent = 40;
                    } else if (data.log.includes('2. Removing forms')) {
                        statusText.textContent = 'Eliminando formularios, JavaScript y adjuntos...';
                        progressPercent = 30;
                    } else if (data.log.includes('1. Flattening PDF')) {
                        statusText.textContent = 'Aplanando formularios PDF...';
                        progressPercent = 20;
                    } else {
                        statusText.textContent = 'Procesando...';
                        progressPercent = 15;
                    }
                } else {
                    statusText.textContent = 'Procesando...';
                    progressPercent = 15;
                }
                break;
            case 'completed':
                statusText.textContent = '¡Conversión completa!';
                progressPercent = 100;
                break;
            case 'failed':
                statusText.textContent = 'Conversión fallida';
                progressPercent = 100;
                break;
        }
        
        progressBar.style.width = `${progressPercent}%`;
    }
    
    // Show success result
    function showSuccess(downloadUrl) {
        processingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        successResult.classList.remove('hidden');
        
        // Set download link
        downloadBtn.href = downloadUrl;
    }
    
    // Show error result
    function showError(message) {
        processingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        errorResult.classList.remove('hidden');
        
        // Set error message
        errorMessage.textContent = message || 'Ocurrió un error durante la conversión.';
    }
    
    // Event Listeners
    
    // File input change
    fileInput.addEventListener('change', function(e) {
        if (this.files && this.files[0]) {
            handleFileSelect(this.files[0]);
        }
    });
    
    // Drop zone drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, function(e) {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, function() {
            this.classList.add('active');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, function() {
            this.classList.remove('active');
        }, false);
    });
    
    // Handle file drop
    dropZone.addEventListener('drop', function(e) {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    }, false);
    
    // Click on drop zone
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });
    
    // Remove file button
    removeFileBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        resetForm();
    });
    
    // Convert button
    convertBtn.addEventListener('click', startConversion);
    
    // Cancel button
    cancelBtn.addEventListener('click', function() {
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
        resetForm();
    });
    
    // Convert another button
    convertAnotherBtn.addEventListener('click', resetForm);
    
    // Try again button
    tryAgainBtn.addEventListener('click', resetForm);
    
    // Toggle log button
    toggleLogBtn.addEventListener('click', function() {
        if (logContainer.classList.contains('hidden')) {
            logContainer.classList.remove('hidden');
            this.textContent = 'Ocultar';
        } else {
            logContainer.classList.add('hidden');
            this.textContent = 'Mostrar';
        }
    });
}); 