import os
import cv2
import json
import base64
import uuid
from flask import Flask, request, jsonify, send_file, abort, render_template
from flask_cors import CORS
import numpy as np
from werkzeug.utils import secure_filename
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from xml.etree import ElementTree as ET
from io import BytesIO
import sys
import tempfile

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Set the Tesseract path for Render
if 'RENDER' in os.environ:
    # On Render, Tesseract is installed at /usr/bin/tesseract
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    
    # Create a temporary directory for uploads on Render
    app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
else:
    # Local development configuration
    app.config['UPLOAD_FOLDER'] = 'uploads'

# REMOVE THIS DUPLICATE LINE:
# app.config['UPLOAD_FOLDER'] = 'uploads'  # <-- DELETE THIS LINE

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def preprocess_image(image_path):
    """Preprocess image to improve OCR accuracy"""
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply threshold to get image with only black and white
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Apply dilation to make text more visible
    kernel = np.ones((2, 2), np.uint8)
    processed = cv2.dilate(thresh, kernel, iterations=1)
    
    # Save processed image
    processed_path = os.path.join(app.config['UPLOAD_FOLDER'], f"processed_{os.path.basename(image_path)}")
    cv2.imwrite(processed_path, processed)
    
    return processed_path

def extract_text_with_tesseract(image_path):
    """Extract text from image using Tesseract OCR"""
    try:
        # Preprocess the image
        processed_path = preprocess_image(image_path)
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(processed_path, lang='eng')
        
        # Clean up processed image
        if os.path.exists(processed_path) and processed_path != image_path:
            os.remove(processed_path)
        
        return text.strip()
    except Exception as e:
        print(f"Tesseract Error: {e}")
        return "Error extracting text"

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({'success': True, 'filename': filename})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/capture', methods=['POST'])
def capture_image():
    """Handle image capture from camera"""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Extract base64 image data
        image_data = data['image'].split(',')[1]  # Remove data:image/jpeg;base64, prefix
        image_bytes = base64.b64decode(image_data)
        
        # Generate unique filename
        filename = f"capture_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save the image
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        return jsonify({'success': True, 'filename': filename})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image/<filename>')
def get_image(filename):
    """Serve uploaded images"""
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert', methods=['POST'])
def convert_image_to_text():
    """Convert image to text using OCR"""
    try:
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({'error': 'No filename provided'}), 400
        
        filename = data['filename']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Extract text using Tesseract
        text = extract_text_with_tesseract(filepath)
        
        return jsonify({'text': text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/pdf/<filename>')
def export_pdf(filename):
    """Export extracted text as PDF"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            abort(404)
        
        # Extract text
        text = extract_text_with_tesseract(filepath)
        
        # Create PDF
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setFont("Helvetica", 12)
        
        # Split text into lines that fit the page
        lines = []
        for paragraph in text.split('\n'):
            words = paragraph.split()
            line = ""
            for word in words:
                if pdf.stringWidth(line + word, "Helvetica", 12) < 450:  # Page width minus margins
                    line += word + " "
                else:
                    lines.append(line)
                    line = word + " "
            if line:
                lines.append(line)
        
        # Add text to PDF
        y = 750  # Start from top of page
        for line in lines:
            if y < 50:  # Add new page if needed
                pdf.showPage()
                pdf.setFont("Helvetica", 12)
                y = 750
            pdf.drawString(50, y, line)
            y -= 15
        
        pdf.save()
        buffer.seek(0)
        
        return send_file(buffer, as_attachment=True, download_name=f"{filename}.pdf", mimetype='application/pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/json/<filename>')
def export_json(filename):
    """Export extracted text as JSON"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            abort(404)
        
        # Extract text
        text = extract_text_with_tesseract(filepath)
        
        # Create JSON response
        data = {
            "filename": filename,
            "text": text,
            "character_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n'))
        }
        
        # Create JSON file
        buffer = BytesIO()
        buffer.write(json.dumps(data, indent=2).encode('utf-8'))
        buffer.seek(0)
        
        return send_file(buffer, as_attachment=True, download_name=f"{filename}.json", mimetype='application/json')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/xml/<filename>')
def export_xml(filename):
    """Export extracted text as XML"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            abort(404)
        
        # Extract text
        text = extract_text_with_tesseract(filepath)
        
        # Create XML structure
        root = ET.Element("extracted_text")
        ET.SubElement(root, "filename").text = filename
        ET.SubElement(root, "text").text = text
        ET.SubElement(root, "character_count").text = str(len(text))
        ET.SubElement(root, "word_count").text = str(len(text.split()))
        ET.SubElement(root, "line_count").text = str(len(text.split('\n')))
        
        # Create XML file
        tree = ET.ElementTree(root)
        buffer = BytesIO()
        tree.write(buffer, encoding='utf-8', xml_declaration=True)
        buffer.seek(0)
        
        return send_file(buffer, as_attachment=True, download_name=f"{filename}.xml", mimetype='application/xml')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Clean up uploaded files"""
    try:
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 