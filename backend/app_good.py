from flask import Flask, request, jsonify, send_file, render_template, url_for
from flask_cors import CORS
import os
import subprocess
import tempfile
import shutil
import uuid

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Directory to store uploaded files
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'static/results'

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return "DICOM Viewer API is running"

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files part'}), 400
    
    files = request.files.getlist('files[]')
    
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    # Create a unique folder for this upload
    upload_id = str(uuid.uuid4())
    upload_folder = os.path.join(UPLOAD_FOLDER, upload_id)
    os.makedirs(upload_folder)
    
    # Save the uploaded files
    file_count = 0
    for file in files:
        if file.filename.lower().endswith(('.dcm', '.ima')):
            file.save(os.path.join(upload_folder, file.filename))
            file_count += 1
    
    if file_count == 0:
        shutil.rmtree(upload_folder)
        return jsonify({'error': 'No valid DICOM files found'}), 400
    
    return jsonify({
        'success': True,
        'upload_id': upload_id,
        'file_count': file_count
    })

@app.route('/process', methods=['POST'])
def process_dicom():
    data = request.json
    if 'upload_id' not in data:
        return jsonify({'error': 'No upload ID provided'}), 400
    
    upload_id = data['upload_id']
    view_type = data.get('view_type', '2d')  # Default to 2D
    
    upload_folder = os.path.join(UPLOAD_FOLDER, upload_id)
    
    if not os.path.exists(upload_folder):
        return jsonify({'error': 'Upload folder not found'}), 404
    
    try:
        # Create temporary directory for output
        output_dir = tempfile.mkdtemp()
        
        # Run the appropriate Python script based on view_type
        if view_type == '2d':
            # Run interactive2.py
            cmd = ['python', 'interactive2.py', '--folder', upload_folder, '--output', output_dir]
        else:
            # Run holofix.py
            cmd = ['python', 'holofix.py', '--folder', upload_folder, '--output', output_dir]
        
        # Execute the command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Process failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return jsonify({
                'error': 'Processing failed',
                'details': f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            }), 500
        
        # Check for output image
        output_files = os.listdir(output_dir)
        if not output_files:
            return jsonify({'error': 'No output generated'}), 500
        
        # Save output images to a permanent location
        saved_images = []
        for output_file in output_files:
            src_path = os.path.join(output_dir, output_file)
            dest_filename = f"{upload_id}_{output_file}"
            dest_path = os.path.join(RESULTS_FOLDER, dest_filename)
            
            # Copy the file
            shutil.copy2(src_path, dest_path)
            saved_images.append(f"/static/results/{dest_filename}")
        
        # Clean up temp directory
        shutil.rmtree(output_dir)
        
        return jsonify({
            'success': True,
            'images': saved_images
        })
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
