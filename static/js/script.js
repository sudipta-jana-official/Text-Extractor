document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const fileUpload = document.getElementById('file-upload');
    const cameraBtn = document.getElementById('camera-btn');
    const convertBtn = document.getElementById('convert-btn');
    const clearBtn = document.getElementById('clear-btn');
    const previewImage = document.getElementById('preview-image');
    const placeholderText = document.getElementById('placeholder-text');
    const imageContainer = document.getElementById('image-container');
    const outputText = document.getElementById('output-text');
    const exportPdf = document.getElementById('export-pdf');
    const exportJson = document.getElementById('export-json');
    const exportXml = document.getElementById('export-xml');
    const notification = document.getElementById('notification');
    const cameraModal = document.getElementById('camera-modal');
    const cameraPreview = document.getElementById('camera-preview');
    const captureBtn = document.getElementById('capture-btn');
    const closeCamera = document.getElementById('close-camera');
    
    let currentFilename = null;
    let extractedText = '';
    let stream = null;

    // Show notification
    function showNotification(message, type = 'success') {
        notification.textContent = message;
        notification.className = `notification ${type} show`;
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 4000);
    }

    function enableExportButtons() {
        exportPdf.disabled = false;
        exportJson.disabled = false;
        exportXml.disabled = false;
    }

    function disableExportButtons() {
        exportPdf.disabled = true;
        exportJson.disabled = true;
        exportXml.disabled = true;
    }

    // Event listeners
    fileUpload.addEventListener('change', handleFileUpload);
    cameraBtn.addEventListener('click', openCamera);
    convertBtn.addEventListener('click', convertText);
    clearBtn.addEventListener('click', clearAll);
    exportPdf.addEventListener('click', exportAsPdf);
    exportJson.addEventListener('click', exportAsJson);
    exportXml.addEventListener('click', exportAsXml);
    captureBtn.addEventListener('click', captureImage);
    closeCamera.addEventListener('click', closeCameraModal);

    // Drag and drop functionality
    imageContainer.addEventListener('dragover', function(e) {
        e.preventDefault();
        imageContainer.classList.add('drag-over');
    });
    
    imageContainer.addEventListener('dragleave', function() {
        imageContainer.classList.remove('drag-over');
    });
    
    imageContainer.addEventListener('drop', function(e) {
        e.preventDefault();
        imageContainer.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileUpload.files = files;
            handleFileUpload({ target: fileUpload });
        }
    });

    // Handle file upload
    function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            showNotification('Please select an image file', 'error');
            return;
        }
        
        // Create a temporary preview while uploading
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImage.src = e.target.result;
            previewImage.style.display = 'block';
            placeholderText.style.display = 'none';
        };
        reader.readAsDataURL(file);
        
        const formData = new FormData();
        formData.append('file', file);
        
        setButtonLoading(convertBtn, true);
        disableExportButtons();
        showNotification('Uploading image...', 'warning');
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showNotification('Error: ' + data.error, 'error');
                return;
            }
            
            currentFilename = data.filename;
            displayImage('/image/' + data.filename);
            setButtonLoading(convertBtn, false);
            showNotification('Image uploaded successfully!', 'success');
        })
        .catch(error => {
            showNotification('Error uploading file', 'error');
            setButtonLoading(convertBtn, false);
        });
    }

    // Camera functionality
    async function openCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            });
            cameraPreview.srcObject = stream;
            cameraPreview.style.display = 'block';
            cameraModal.style.display = 'block';
        } catch (error) {
            showNotification('Camera access denied: ' + error.message, 'error');
        }
    }

    function captureImage() {
        const canvas = document.createElement('canvas');
        canvas.width = cameraPreview.videoWidth;
        canvas.height = cameraPreview.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);
        
        // Convert to base64
        const imageData = canvas.toDataURL('image/jpeg');
        
        // Send to server
        setButtonLoading(captureBtn, true);
        showNotification('Processing captured image...', 'warning');
        
        fetch('/capture', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        })
        .then(response => response.json())
        .then(data => {
            setButtonLoading(captureBtn, false);
            if (data.success) {
                currentFilename = data.filename;
                displayImage('/image/' + data.filename);
                closeCameraModal();
                showNotification('Image captured successfully!', 'success');
            } else {
                showNotification('Error capturing image: ' + data.error, 'error');
            }
        })
        .catch(error => {
            setButtonLoading(captureBtn, false);
            showNotification('Error capturing image', 'error');
        });
    }

    function closeCameraModal() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
        cameraPreview.style.display = 'none';
        cameraModal.style.display = 'none';
    }

    // Convert image to text
    function convertText() {
        if (!currentFilename) {
            showNotification('Please upload or capture an image first', 'error');
            return;
        }
        
        setButtonLoading(convertBtn, true);
        outputText.value = 'Extracting text...';
        showNotification('Processing image with AI...', 'warning');
        
        fetch('/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: currentFilename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                outputText.value = 'Error: ' + data.error;
                showNotification('Extraction failed', 'error');
            } else {
                extractedText = data.text;
                outputText.value = extractedText;
                if (extractedText && extractedText.length > 0) {
                    showNotification('Text extracted successfully!', 'success');
                    enableExportButtons();
                } else {
                    showNotification('No text detected', 'warning');
                    disableExportButtons();
                }
            }
            setButtonLoading(convertBtn, false);
        })
        .catch(error => {
            outputText.value = 'Error extracting text';
            showNotification('Extraction error', 'error');
            setButtonLoading(convertBtn, false);
            disableExportButtons();
        });
    }

    // Clear all
    function clearAll() {
        currentFilename = null;
        extractedText = '';
        previewImage.style.display = 'none';
        placeholderText.style.display = 'block';
        outputText.value = '';
        fileUpload.value = '';
        disableExportButtons();
        
        // Clean up server files
        fetch('/cleanup', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Cleared all content', 'success');
            }
        })
        .catch(error => {
            showNotification('Cleared local content', 'success');
        });
    }

    // Export functions
    function exportAsPdf() {
        if (!currentFilename || !extractedText) {
            showNotification('Please extract text first', 'error');
            return;
        }
        window.open(`/export/pdf/${currentFilename}`, '_blank');
    }

    function exportAsJson() {
        if (!currentFilename || !extractedText) {
            showNotification('Please extract text first', 'error');
            return;
        }
        window.open(`/export/json/${currentFilename}`, '_blank');
    }

    function exportAsXml() {
        if (!currentFilename || !extractedText) {
            showNotification('Please extract text first', 'error');
            return;
        }
        window.open(`/export/xml/${currentFilename}`, '_blank');
    }

    // Display image
    function displayImage(src) {
        previewImage.src = src;
        previewImage.style.display = 'block';
        placeholderText.style.display = 'none';
        
        previewImage.onerror = function() {
            previewImage.style.display = 'none';
            placeholderText.style.display = 'block';
            showNotification('Error loading image', 'error');
        };
    }

    // Set button loading state
    function setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            const originalText = button.innerHTML;
            button.setAttribute('data-original-text', originalText);
            button.innerHTML = '<span class="loading"></span> Processing...';
        } else {
            button.disabled = false;
            const originalText = button.getAttribute('data-original-text');
            if (originalText) {
                button.innerHTML = originalText;
            }
        }
    }

    // Close modal if clicked outside
    window.addEventListener('click', function(event) {
        if (event.target === cameraModal) {
            closeCameraModal();
        }
    });

    // Handle page refresh/closing to clean up camera
    window.addEventListener('beforeunload', function() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        
        // Clean up server files
        fetch('/cleanup', {
            method: 'POST'
        });
    });
});