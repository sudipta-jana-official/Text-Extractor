import os
import uuid
import base64
import json
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import shutil
from PIL import Image

# Try to import ReportLab for PDF generation (optional)
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename for uploaded files using OS-safe characters"""
    # Extract file extension
    name, ext = os.path.splitext(original_filename)
    
    # Remove any special characters from filename (OS-safe)
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    if not safe_name:
        safe_name = "image"
    
    # Generate unique ID and timestamp
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Combine all parts
    return f"{safe_name}_{timestamp}_{unique_id}{ext}"

def save_uploaded_file(file, upload_folder: str) -> str:
    """Save an uploaded file to the server using OS module operations"""
    # Create upload directory if it doesn't exist
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        print(f"Created upload directory: {upload_folder}")
    
    # Generate a safe filename
    filename = generate_unique_filename(file.filename)
    filepath = os.path.join(upload_folder, filename)
    
    try:
        # Save the file using OS operations
        file.save(filepath)
        print(f"File saved successfully: {filepath}")
        
        # Verify file was saved
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filename
        else:
            raise Exception("File save operation failed")
            
    except Exception as e:
        # Clean up if something went wrong
        if os.path.exists(filepath):
            os.remove(filepath)
        raise Exception(f"Error saving file: {str(e)}")

def save_base64_image(image_data: str, upload_folder: str) -> str:
    """Save a base64 encoded image to the server using OS module"""
    # Create upload directory if it doesn't exist
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
    
    # Remove data URL prefix if present
    if ',' in image_data:
        image_data = image_data.split(',', 1)[1]
    
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        # Generate filename and save
        filename = generate_unique_filename("captured_image.jpg")
        filepath = os.path.join(upload_folder, filename)
        
        # Write file using OS operations
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        # Verify file was saved
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"Base64 image saved successfully: {filepath}")
            return filename
        else:
            raise Exception("Base64 image save operation failed")
            
    except Exception as e:
        # Clean up if something went wrong
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        raise Exception(f"Error saving base64 image: {str(e)}")

def get_file_info(filepath: str) -> Dict[str, Any]:
    """Get information about a file using OS module"""
    if not os.path.exists(filepath):
        return {"error": "File does not exist"}
    
    try:
        file_stats = os.stat(filepath)
        file_size = file_stats.st_size
        created_time = datetime.fromtimestamp(file_stats.st_ctime)
        modified_time = datetime.fromtimestamp(file_stats.st_mtime)
        
        # Get image dimensions if it's an image
        dimensions = None
        try:
            with Image.open(filepath) as img:
                dimensions = f"{img.width}x{img.height}"
        except:
            pass
        
        return {
            "filename": os.path.basename(filepath),
            "filepath": filepath,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "created": created_time.isoformat(),
            "modified": modified_time.isoformat(),
            "dimensions": dimensions,
            "file_type": os.path.splitext(filepath)[1].lower()
        }
    except Exception as e:
        return {"error": f"Could not get file info: {str(e)}"}

def list_uploaded_files(upload_folder: str) -> list:
    """List all files in the upload directory using OS module"""
    if not os.path.exists(upload_folder):
        return []
    
    try:
        files = []
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                file_info = get_file_info(filepath)
                files.append(file_info)
        return files
    except Exception as e:
        print(f"Error listing files: {str(e)}")
        return []

def validate_image_file(filepath: str, allowed_extensions: set) -> Tuple[bool, str]:
    """Validate if a file is a proper image using OS and PIL"""
    # Check if file exists
    if not os.path.exists(filepath):
        return False, "File does not exist"
    
    # Check file extension
    file_ext = os.path.splitext(filepath)[1].lower().lstrip('.')
    if file_ext not in allowed_extensions:
        return False, f"File type {file_ext} not allowed"
    
    # Check if file is actually an image
    try:
        with Image.open(filepath) as img:
            img.verify()  # Verify it's a valid image
        return True, "Valid image file"
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

def resize_image(filepath: str, max_width: int = 1200, max_height: int = 1200) -> bool:
    """Resize an image while maintaining aspect ratio using OS and PIL operations"""
    try:
        with Image.open(filepath) as img:
            # Calculate new dimensions while maintaining aspect ratio
            width, height = img.size
            if width <= max_width and height <= max_height:
                return True  # No resizing needed
            
            ratio = min(max_width/width, max_height/height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save the resized image (overwrite original)
            resized_img.save(filepath, optimize=True, quality=85)
            
            print(f"Image resized from {width}x{height} to {new_width}x{new_height}")
            return True
            
    except Exception as e:
        print(f"Error resizing image: {str(e)}")
        return False

def extract_text_from_image(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract text from an image using OCR
    Returns: (extracted_text, error_message)
    """
    try:
        # First validate the image
        is_valid, message = validate_image_file(image_path, {'png', 'jpg', 'jpeg', 'bmp', 'gif'})
        if not is_valid:
            return None, f"Invalid image: {message}"
        
        # Resize if needed for better OCR performance
        resize_image(image_path)
        
        # This is a placeholder for OCR implementation
        # You'll need to integrate with an OCR library like Tesseract, Google Vision, etc.
        
        # For now, return a mock response
        # Replace this with actual OCR implementation
        mock_text = f"This is a placeholder for extracted text from {os.path.basename(image_path)}.\nReplace with actual OCR implementation.\nFile was processed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
        
        return mock_text, None
        
    except Exception as e:
        return None, f"OCR processing error: {str(e)}"

def convert_to_pdf(text: str, filename: str) -> BytesIO:
    """Convert text to PDF format"""
    if not REPORTLAB_AVAILABLE:
        raise Exception("PDF export requires ReportLab library. Install with: pip install reportlab")
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Set up PDF content
    c.setFont("Helvetica", 12)
    text_lines = text.split('\n')
    y_position = 750  # Start from top of page
    
    # Add filename and timestamp
    c.drawString(50, 800, f"File: {filename}")
    c.drawString(50, 780, f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.line(50, 775, 562, 775)
    y_position = 760
    
    for line in text_lines:
        if y_position < 50:  # Add new page if needed
            c.showPage()
            c.setFont("Helvetica", 12)
            y_position = 750
        
        c.drawString(50, y_position, line)
        y_position -= 15
    
    c.save()
    buffer.seek(0)
    return buffer

def convert_to_json(text: str, filename: str) -> Dict[str, Any]:
    """Convert text to JSON format"""
    return {
        "filename": filename,
        "extracted_text": text,
        "processed_at": datetime.now().isoformat(),
        "character_count": len(text),
        "line_count": len(text.split('\n')),
        "file_info": get_file_info(os.path.join('static/uploads', filename))
    }

def convert_to_xml(text: str, filename: str) -> str:
    """Convert text to XML format"""
    root = ET.Element("extracted_text")
    
    ET.SubElement(root, "filename").text = filename
    ET.SubElement(root, "processed_at").text = datetime.now().isoformat()
    ET.SubElement(root, "character_count").text = str(len(text))
    ET.SubElement(root, "line_count").text = str(len(text.split('\n')))
    
    content = ET.SubElement(root, "content")
    content.text = text
    
    # Create XML string
    rough_string = ET.tostring(root, 'utf-8')
    
    # Pretty print (requires additional processing)
    from xml.dom import minidom
    parsed = minidom.parseString(rough_string)
    return parsed.toprettyxml(indent="  ")

def cleanup_files(upload_folder: str, max_age_minutes: int = 60) -> Dict[str, Any]:
    """Clean up old files in the upload folder using OS module operations"""
    if not os.path.exists(upload_folder):
        return {"deleted_count": 0, "error": "Upload folder does not exist"}
    
    current_time = datetime.now()
    deleted_count = 0
    deleted_files = []
    
    try:
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                file_age = current_time - file_time
                
                if file_age > timedelta(minutes=max_age_minutes):
                    os.remove(filepath)
                    deleted_count += 1
                    deleted_files.append(filename)
                    print(f"Deleted old file: {filename}")
        
        return {
            "deleted_count": deleted_count,
            "deleted_files": deleted_files,
            "message": f"Cleaned up {deleted_count} files older than {max_age_minutes} minutes"
        }
        
    except Exception as e:
        return {
            "deleted_count": deleted_count,
            "error": f"Error during cleanup: {str(e)}"
        }

def get_storage_usage(upload_folder: str) -> Dict[str, Any]:
    """Get storage usage statistics for the upload folder using OS module"""
    if not os.path.exists(upload_folder):
        return {"total_size": 0, "file_count": 0, "error": "Upload folder does not exist"}
    
    total_size = 0
    file_count = 0
    
    try:
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
                file_count += 1
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "folder_path": upload_folder
        }
        
    except Exception as e:
        return {
            "error": f"Error calculating storage usage: {str(e)}",
            "total_size": 0,
            "file_count": 0
        }