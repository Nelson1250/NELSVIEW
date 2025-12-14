import React, { useState } from 'react';

const DicomViewer = () => {
  const [files, setFiles] = useState([]);
  const [uploadId, setUploadId] = useState(null);
  const [fileCount, setFileCount] = useState(0);
  const [viewMode, setViewMode] = useState('2d');
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [resultImage, setResultImage] = useState(null);
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
    
    try {
      const response = await fetch(`${API_URL}/process`, {
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
      
      if (data.success && data.images && data.images.length > 0) {
        // Use the full URL to the image
        setResultImage(`${API_URL}${data.images[0]}`);
      } else {
        throw new Error('No images were generated');
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
        <h1 className="text-2xl font-bold">NELSVIEW: Views Dicom Images</h1>
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
            
            {!resultImage && !loading && !processing && !error && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-100 border-2 border-dashed border-gray-300 rounded-lg">
                <div className="text-center">
                  <p className="text-gray-500">No DICOM files processed</p>
                  <p className="text-gray-400 text-sm mt-2">Upload files and click "Process DICOM Files"</p>
                </div>
              </div>
            )}
            
            {resultImage && (
              <img 
                src={resultImage} 
                alt="DICOM visualization" 
                className="max-w-full max-h-full object-contain mx-auto"
                style={{ minHeight: '400px' }}
              />
            )}
          </div>
        </div>
      </div>
      
      <div className="bg-gray-800 text-white p-2 text-center text-sm">
         NELSVIEW - © 2025
      </div>
    </div>
  );
};

export default DicomViewer;
