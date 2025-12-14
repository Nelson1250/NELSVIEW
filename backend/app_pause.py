from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import os
import subprocess
import tempfile
import shutil
import uuid
import pydicom
import numpy as np

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
            # Run holofix.py (only for static image output)
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

@app.route('/process_3d', methods=['POST'])
def process_3d():
    data = request.json
    if 'upload_id' not in data:
        return jsonify({'error': 'No upload ID provided'}), 400
    
    upload_id = data['upload_id']
    upload_folder = os.path.join(UPLOAD_FOLDER, upload_id)
    
    if not os.path.exists(upload_folder):
        return jsonify({'error': 'Upload folder not found'}), 404
    
    try:
        # Process DICOM files to extract volume data
        dicom_files = [f for f in os.listdir(upload_folder) 
                      if f.lower().endswith('.dcm') or f.lower().endswith('.ima')]
        
        if not dicom_files:
            return jsonify({'error': 'No DICOM files found'}), 400
        
        # Read and store pixel data with slice order
        slices = []
        for fname in dicom_files:
            ds = pydicom.dcmread(os.path.join(upload_folder, fname))
            try:
                instance_number = int(ds.InstanceNumber)
            except:
                instance_number = 0
            slices.append((instance_number, ds.pixel_array))
        
        # Sort and stack the images in correct order
        slices.sort(key=lambda x: x[0])  # Sort by InstanceNumber
        volume = np.stack([s[1] for s in slices], axis=-1).astype(np.int16)
        
        # Normalize for display
        volume = (volume - np.min(volume)) / (np.max(volume) - np.min(volume))
        volume = (volume * 255).astype(np.uint8)
        
        # Sample the volume data (for performance in browser)
        sampling_factor = 4  # Take every 4th voxel in each dimension
        sampled_volume = volume[::sampling_factor, ::sampling_factor, ::sampling_factor]
        
        # Convert to point cloud data
        points = []
        colors = []
        
        # Loop through the volume and extract points
        for z in range(sampled_volume.shape[2]):
            for y in range(sampled_volume.shape[1]):
                for x in range(sampled_volume.shape[0]):
                    value = sampled_volume[x, y, z]
                    # Skip transparent/air values
                    if value > 50:  # Threshold to reduce number of points
                        # Skip randomly to further reduce points
                        if np.random.random() > 0.3:  # Keep ~30% of points above threshold
                            continue
                            
                        # Add point coordinates
                        points.append([x, y, z])
                        
                        # Add color based on value
                        if value < 100:
                            colors.append([0.2, 0.5, 0.8])  # Blue for low values
                        elif value < 200:
                            colors.append([0.9, 0.3, 0.3])  # Red for medium values
                        else:
                            colors.append([0.9, 0.9, 0.2])  # Yellow for high values
        
        # Return the points and colors
        return jsonify({
            'success': True,
            'volume_data': {
                'points': points,
                'colors': colors,
                'dimensions': [
                    int(sampled_volume.shape[0]),
                    int(sampled_volume.shape[1]),
                    int(sampled_volume.shape[2])
                ]
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/static/results/<path:filename>')
def serve_result(filename):
    return send_file(os.path.join(RESULTS_FOLDER, filename))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
