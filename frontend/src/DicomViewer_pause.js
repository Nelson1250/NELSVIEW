import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

// ThreeDViewer component for interactive 3D visualization
const ThreeDViewer = ({ volumeData }) => {
  const containerRef = useRef(null);
  const [renderer, setRenderer] = useState(null);
  const [scene, setScene] = useState(null);
  const [camera, setCamera] = useState(null);
  const [controls, setControls] = useState(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current || !volumeData) return;

    // Setup scene
    const newScene = new THREE.Scene();
    newScene.background = new THREE.Color(0x000000);
    
    // Setup camera
    const aspectRatio = containerRef.current.clientWidth / containerRef.current.clientHeight;
    const newCamera = new THREE.PerspectiveCamera(75, aspectRatio, 0.1, 1000);
    newCamera.position.z = 200;
    
    // Setup renderer
    const newRenderer = new THREE.WebGLRenderer({ antialias: true });
    newRenderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    containerRef.current.appendChild(newRenderer.domElement);
    
    // Setup controls
    const newControls = new OrbitControls(newCamera, newRenderer.domElement);
    newControls.enableDamping = true;
    newControls.dampingFactor = 0.25;
    
    // Add lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    newScene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(0, 1, 1);
    newScene.add(directionalLight);
    
    // Store references
    setScene(newScene);
    setCamera(newCamera);
    setRenderer(newRenderer);
    setControls(newControls);
    
    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);
      
      if (newControls) {
        newControls.update();
      }
      
      if (newRenderer && newScene && newCamera) {
        newRenderer.render(newScene, newCamera);
      }
    };
    
    animate();
    
    // Cleanup on unmount
    return () => {
      if (containerRef.current && newRenderer) {
        containerRef.current.removeChild(newRenderer.domElement);
      }
    };
  }, [volumeData]);
  
  // Update scene when volume data changes
  useEffect(() => {
    if (!scene || !volumeData || !volumeData.points || volumeData.points.length === 0) return;
    
    // Clear previous points
    scene.children = scene.children.filter(child => 
      child instanceof THREE.AmbientLight || child instanceof THREE.DirectionalLight);
    
    // Add points to scene
    const geometry = new THREE.BufferGeometry();
    
    // Prepare vertices and colors
    const vertices = [];
    const colors = [];
    
    volumeData.points.forEach((point, index) => {
      // Add vertex coordinates
      vertices.push(point[0], point[1], point[2]);
      
      // Add vertex color
      const color = volumeData.colors[index];
      colors.push(color[0], color[1], color[2]);
    });
    
    // Set geometry attributes
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    
    // Create point cloud material
    const material = new THREE.PointsMaterial({
      size: 2,
      vertexColors: true,
      transparent: true,
      opacity: 0.8
    });
    
    // Create point cloud and add to scene
    const pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);
    
    // Center the point cloud
    const box = new THREE.Box3().setFromObject(pointCloud);
    const center = box.getCenter(new THREE.Vector3());
    pointCloud.position.sub(center);
    
    // Adjust camera position
    const maxDimension = Math.max(
      volumeData.dimensions[0], 
      volumeData.dimensions[1], 
      volumeData.dimensions[2]
    );
    camera.position.z = maxDimension * 1.5;
    
    if (controls) {
      controls.update();
    }
  }, [scene, camera, controls, volumeData]);
  
  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (!containerRef.current || !camera || !renderer) return;
      
      camera.aspect = containerRef.current.clientWidth / containerRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [camera, renderer]);
  
  return (
    <div 
      ref={containerRef} 
      style={{ width: '100%', height: '400px', minHeight: '400px' }}
    ></div>
  );
};

// Main DicomViewer component
const DicomViewer = () => {
  const [files, setFiles] = useState([]);
  const [uploadId, setUploadId] = useState(null);
  const [fileCount, setFileCount] = useState(0);
  const [viewMode, setViewMode] = useState('2d');
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [resultImage, setResultImage] = useState(null);
  const [volumeData, setVolumeData] = useState(null);
  const [error, setError] = useState(null);
  
  // Base URL for API calls
  const API_URL = 'http://localhost:5001';
  
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files));
      setFileCount(e.target.files.length);
      // Reset previous results when new files are selected
      setUploadId(null);
      setResultImage(null);
      setVolumeData(null);
      setError(null);
    }
  };
  
  const uploadFiles = async () => {
    if (files.length === 0) {
      setError('Please select files to upload');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files[]', file);
    });
    
    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Upload failed');
      }
      
      setUploadId(data.upload_id);
      setFileCount(data.file_count);
    } catch (error) {
      console.error("Upload error:", error);
      setError(`Error uploading files: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  const processFiles = async () => {
    if (!uploadId) {
      setError('Please upload files first');
      return;
    }
    
    setProcessing(true);
    setError(null);
    
    // Reset previous results
    setResultImage(null);
    setVolumeData(null);
    
    try {
      // Different endpoints for 2D and 3D
      const endpoint = viewMode === '2d' ? '/process' : '/process_3d';
      
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          upload_id: uploadId,
          view_type: viewMode
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || data.details || 'Processing failed');
      }
      
      if (viewMode === '2d') {
        // Handle 2D processing result
        if (data.success && data.images && data.images.length > 0) {
          setResultImage(`${API_URL}${data.images[0]}`);
        } else {
          throw new Error('No images were generated');
        }
      } else {
        // Handle 3D processing result
        if (data.success && data.volume_data) {
          setVolumeData(data.volume_data);
        } else {
          throw new Error('No 3D data was generated');
        }
      }
    } catch (error) {
      console.error("Processing error:", error);
      setError(`Error processing files: ${error.message}`);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <div className="bg-gray-800 text-white p-4">
        <h1 className="text-2xl font-bold">DICOM Hologram Viewer</h1>
      </div>
      
      <div className="flex-1 flex flex-col md:flex-row p-4 space-y-4 md:space-y-0 md:space-x-4">
        <div className="w-full md:w-1/4 bg-white rounded-lg shadow p-4">
          <h2 className="text-xl font-semibold mb-4">Controls</h2>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Upload DICOM Files
            </label>
            <input
              type="file"
              multiple
              accept=".dcm,.ima"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
            {files.length > 0 && (
              <p className="text-xs text-gray-700 mt-1">
                {files.length} file(s) selected
              </p>
            )}
            
            <button
              onClick={uploadFiles}
              disabled={loading || files.length === 0}
              className="mt-3 w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-blue-300"
            >
              {loading ? 'Uploading...' : 'Upload Files'}
            </button>
          </div>
          
          {uploadId && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  View Mode
                </label>
                <div className="flex space-x-2">
                  <button
                    onClick={() => {
                      setViewMode('2d');
                      setVolumeData(null);
                      setResultImage(null);
                    }}
                    className={`px-4 py-2 rounded-lg ${
                      viewMode === '2d'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    2D Slices
                  </button>
                  <button
                    onClick={() => {
                      setViewMode('3d');
                      setVolumeData(null);
                      setResultImage(null);
                    }}
                    className={`px-4 py-2 rounded-lg ${
                      viewMode === '3d'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    3D Hologram
                  </button>
                </div>
              </div>
              
              <button
                onClick={processFiles}
                disabled={processing}
                className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-blue-300"
              >
                {processing ? 'Processing...' : 'Process DICOM Files'}
              </button>
              
              <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Uploaded:</strong> {fileCount} DICOM files
                </p>
              </div>
              
              {viewMode === '3d' && volumeData && (
                <div className="mt-4 p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-800 font-medium">3D Controls:</p>
                  <ul className="text-xs text-green-700 mt-1 list-disc list-inside">
                    <li>Left click + drag to rotate</li>
                    <li>Right click + drag to pan</li>
                    <li>Scroll to zoom in/out</li>
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
        
        <div className="w-full md:w-3/4 bg-white rounded-lg shadow p-4 flex flex-col">
          <h2 className="text-xl font-semibold mb-4">
            {viewMode === '2d' ? 'DICOM Slice Viewer' : '3D Hologram Viewer'}
          </h2>
          
          <div className="flex-1 relative">
            {(loading || processing) && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-200 bg-opacity-75 z-10">
                <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500"></div>
                <p className="ml-3 font-medium text-gray-700">
                  {loading ? 'Uploading...' : 'Processing...'}
                </p>
              </div>
            )}
            
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}
            
            {!resultImage && !volumeData && !loading && !processing && !error && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-100 border-2 border-dashed border-gray-300 rounded-lg">
                <div className="text-center">
                  <p className="text-gray-500">No DICOM files processed</p>
                  <p className="text-gray-400 text-sm mt-2">Upload files and click "Process DICOM Files"</p>
                </div>
              </div>
            )}
            
            {viewMode === '2d' && resultImage && (
              <img 
                src={resultImage} 
                alt="DICOM slice visualization" 
                className="max-w-full max-h-full object-contain mx-auto"
                style={{ minHeight: '400px' }}
              />
            )}
            
            {viewMode === '3d' && volumeData && (
              <ThreeDViewer volumeData={volumeData} />
            )}
          </div>
        </div>
      </div>
      
      <div className="bg-gray-800 text-white p-2 text-center text-sm">
        DICOM Hologram Viewer - © 2025
      </div>
    </div>
  );
};

export default DicomViewer;
