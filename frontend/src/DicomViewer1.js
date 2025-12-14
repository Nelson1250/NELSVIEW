import React, { useState, useEffect, useRef } from 'react';
import * as cornerstone from 'cornerstone-core';
import * as cornerstoneWADOImageLoader from 'cornerstone-wado-image-loader';
import * as dicomParser from 'dicom-parser';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

// Initialize cornerstone libraries
cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
cornerstoneWADOImageLoader.external.dicomParser = dicomParser;
cornerstoneWADOImageLoader.wadouri.fileManager.purge();

const DicomViewer = () => {
  const [files, setFiles] = useState([]);
  const [slices, setSlices] = useState([]);
  const [currentSliceIndex, setCurrentSliceIndex] = useState(0);
  const [windowCenter, setWindowCenter] = useState(-600);
  const [windowWidth, setWindowWidth] = useState(1500);
  const [viewMode, setViewMode] = useState('2d'); // '2d' or '3d'
  const [loading, setLoading] = useState(false);
  
  const viewerRef = useRef(null);
  const threeDRef = useRef(null);
  const threeScene = useRef(null);
  const threeRenderer = useRef(null);
  const threeCamera = useRef(null);
  const threeControls = useRef(null);

  const handleFileUpload = async (event) => {
    const uploadedFiles = Array.from(event.target.files);
    
    if (uploadedFiles.length === 0) return;
    
    setFiles(uploadedFiles);
    setLoading(true);
    
    try {
      // Sort files and load them
      const loadedSlices = await Promise.all(
        uploadedFiles.map(async (file, index) => {
          // Create a URL for the file
          const fileUrl = URL.createObjectURL(file);
          
          // Load the DICOM file using cornerstone
          const image = await cornerstone.loadImage('wadouri:' + fileUrl);
          
          return {
            index,
            image,
            url: fileUrl,
            // Try to get instance number for proper sorting
            instanceNumber: image.data && image.data.string('x00200013') ? 
              parseInt(image.data.string('x00200013')) : index
          };
        })
      );
      
      // Sort slices by instance number
      const sortedSlices = loadedSlices.sort((a, b) => a.instanceNumber - b.instanceNumber);
      setSlices(sortedSlices);
      setCurrentSliceIndex(Math.floor(sortedSlices.length / 2));
      setLoading(false);
    } catch (error) {
      console.error("Error loading DICOM files:", error);
      setLoading(false);
    }
  };

  // Initialize cornerstone element
  useEffect(() => {
    if (viewerRef.current) {
      cornerstone.enable(viewerRef.current);
    }
    
    return () => {
      if (viewerRef.current) {
        cornerstone.disable(viewerRef.current);
      }
    };
  }, []);

  // Display current slice
  useEffect(() => {
    if (slices.length > 0 && viewerRef.current && viewMode === '2d') {
      const currentSlice = slices[currentSliceIndex];
      if (currentSlice && currentSlice.image) {
        const viewport = cornerstone.getDefaultViewportForImage(viewerRef.current, currentSlice.image);
        viewport.voi.windowWidth = windowWidth;
        viewport.voi.windowCenter = windowCenter;
        cornerstone.displayImage(viewerRef.current, currentSlice.image, viewport);
      }
    }
  }, [slices, currentSliceIndex, windowCenter, windowWidth, viewMode]);

  // Initialize 3D rendering
  useEffect(() => {
    if (viewMode === '3d' && threeDRef.current && slices.length > 0) {
      if (!threeScene.current) {
        // Set up Three.js scene
        threeScene.current = new THREE.Scene();
        threeScene.current.background = new THREE.Color(0x000000);
        
        // Set up camera
        threeCamera.current = new THREE.PerspectiveCamera(
          75, threeDRef.current.clientWidth / threeDRef.current.clientHeight, 0.1, 1000
        );
        threeCamera.current.position.z = 200;
        
        // Set up renderer
        threeRenderer.current = new THREE.WebGLRenderer({ antialias: true });
        threeRenderer.current.setSize(threeDRef.current.clientWidth, threeDRef.current.clientHeight);
        threeDRef.current.appendChild(threeRenderer.current.domElement);
        
        // Add controls
        threeControls.current = new OrbitControls(threeCamera.current, threeRenderer.current.domElement);
        threeControls.current.enableDamping = true;
        threeControls.current.dampingFactor = 0.25;
        
        // Add ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        threeScene.current.add(ambientLight);
        
        // Add directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(0, 1, 1);
        threeScene.current.add(directionalLight);
        
        // Animation function
        const animate = () => {
          requestAnimationFrame(animate);
          
          if (threeControls.current) {
            threeControls.current.update();
          }
          
          if (threeRenderer.current && threeScene.current && threeCamera.current) {
            threeRenderer.current.render(threeScene.current, threeCamera.current);
          }
        };
        
        animate();
      }
      
      // Create 3D volume from slices
      createVolumeFromSlices();
    }
    
    return () => {
      if (viewMode === '2d' && threeRenderer.current && threeDRef.current) {
        threeDRef.current.removeChild(threeRenderer.current.domElement);
        threeScene.current = null;
        threeRenderer.current = null;
        threeCamera.current = null;
        threeControls.current = null;
      }
    };
  }, [viewMode, slices]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (threeCamera.current && threeRenderer.current && threeDRef.current) {
        threeCamera.current.aspect = threeDRef.current.clientWidth / threeDRef.current.clientHeight;
        threeCamera.current.updateProjectionMatrix();
        threeRenderer.current.setSize(threeDRef.current.clientWidth, threeDRef.current.clientHeight);
      }
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // Create 3D volume from slices
  const createVolumeFromSlices = async () => {
    if (!threeScene.current || slices.length === 0) return;
    
    // Clear previous volume
    while (threeScene.current.children.length > 2) { // Keep lights
      threeScene.current.remove(threeScene.current.children[2]);
    }
    
    // Create a geometry to hold points
    const geometry = new THREE.BufferGeometry();
    const vertices = [];
    const colors = [];
    
    const sliceHeight = 1;
    const totalHeight = slices.length * sliceHeight;
    
    // Process each slice
    for (let i = 0; i < slices.length; i++) {
      const slice = slices[i];
      
      // Get pixel data from cornerstone image
      const image = slice.image;
      const pixelData = image.getPixelData();
      const width = image.columns;
      const height = image.rows;
      
      // Get image center for positioning
      const centerX = width / 2;
      const centerY = height / 2;
      
      // Z position based on slice index
      const z = i * sliceHeight - totalHeight / 2;
      
      // Sample pixels (reduce for performance)
      const samplingFactor = 4; // Take every 4th pixel
      
      for (let y = 0; y < height; y += samplingFactor) {
        for (let x = 0; x < width; x += samplingFactor) {
          const pixelIndex = y * width + x;
          const pixelValue = pixelData[pixelIndex];
          
          // Skip pixels darker than threshold (air)
          if (pixelValue < -800) continue;
          
          // Map Hounsfield units to colors
          let color;
          if (pixelValue < -100) { // Air/lungs
            color = new THREE.Color(0x3498db); // Blue
            // Skip most air pixels for better visibility
            if (Math.random() > 0.1) continue;
          } else if (pixelValue < 200) { // Soft tissue
            color = new THREE.Color(0xe74c3c); // Red
            // Skip some soft tissue for better visibility
            if (Math.random() > 0.3) continue;
          } else { // Bone
            color = new THREE.Color(0xf1c40f); // Yellow
          }
          
          // Position relative to center
          vertices.push(x - centerX, -(y - centerY), z);
          colors.push(color.r, color.g, color.b);
        }
      }
    }
    
    // Create point cloud
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    
    const material = new THREE.PointsMaterial({
      size: 1.5,
      vertexColors: true,
      transparent: true,
      opacity: 0.7
    });
    
    const pointCloud = new THREE.Points(geometry, material);
    threeScene.current.add(pointCloud);
    
    // Adjust camera to fit volume
    const maxDimension = Math.max(slices[0].image.columns, slices[0].image.rows, totalHeight);
    threeCamera.current.position.z = maxDimension * 1.5;
    threeControls.current.update();
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
              onChange={handleFileUpload}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              View Mode
            </label>
            <div className="flex space-x-2">
              <button
                onClick={() => setViewMode('2d')}
                className={`px-4 py-2 rounded-lg ${
                  viewMode === '2d'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-800'
                }`}
              >
                2D Slices
              </button>
              <button
                onClick={() => setViewMode('3d')}
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
          
          {viewMode === '2d' && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Slice: {currentSliceIndex + 1}/{slices.length}
                </label>
                <input
                  type="range"
                  min="0"
                  max={slices.length - 1}
                  value={currentSliceIndex}
                  onChange={(e) => setCurrentSliceIndex(parseInt(e.target.value))}
                  className="w-full"
                  disabled={slices.length === 0}
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Window Center: {windowCenter}
                </label>
                <input
                  type="range"
                  min="-1000"
                  max="3000"
                  value={windowCenter}
                  onChange={(e) => setWindowCenter(parseInt(e.target.value))}
                  className="w-full"
                  disabled={slices.length === 0}
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Window Width: {windowWidth}
                </label>
                <input
                  type="range"
                  min="1"
                  max="4000"
                  value={windowWidth}
                  onChange={(e) => setWindowWidth(parseInt(e.target.value))}
                  className="w-full"
                  disabled={slices.length === 0}
                />
              </div>
            </>
          )}
          
          {viewMode === '3d' && (
            <div className="text-sm text-gray-700">
              <h3 className="font-medium mb-1">3D Controls:</h3>
              <ul className="list-disc list-inside">
                <li>Left click + drag to rotate</li>
                <li>Right click + drag to pan</li>
                <li>Scroll to zoom in/out</li>
              </ul>
              <p className="mt-2">
                Color legend:
              </p>
              <div className="flex items-center mt-1">
                <div className="w-4 h-4 bg-blue-500 mr-2"></div>
                <span>Air/Lungs</span>
              </div>
              <div className="flex items-center mt-1">
                <div className="w-4 h-4 bg-red-500 mr-2"></div>
                <span>Soft Tissue</span>
              </div>
              <div className="flex items-center mt-1">
                <div className="w-4 h-4 bg-yellow-500 mr-2"></div>
                <span>Bone</span>
              </div>
            </div>
          )}
        </div>
        
        <div className="w-full md:w-3/4 bg-white rounded-lg shadow p-4 flex flex-col">
          <h2 className="text-xl font-semibold mb-4">
            {viewMode === '2d' ? 'DICOM Slice Viewer' : '3D Hologram Viewer'}
          </h2>
          
          <div className="flex-1 relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-200 bg-opacity-75 z-10">
                <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500"></div>
              </div>
            )}
            
            {slices.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-100 border-2 border-dashed border-gray-300 rounded-lg">
                <div className="text-center">
                  <p className="text-gray-500">No DICOM files loaded</p>
                  <p className="text-gray-400 text-sm mt-2">Upload DICOM files to view</p>
                </div>
              </div>
            ) : (
              viewMode === '2d' ? (
                <div 
                  ref={viewerRef} 
                  className="w-full h-full"
                  style={{ minHeight: '400px' }}
                ></div>
              ) : (
                <div 
                  ref={threeDRef} 
                  className="w-full h-full"
                  style={{ minHeight: '400px' }}
                ></div>
              )
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
