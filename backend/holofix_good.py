# IMPORTS
import os
import argparse
import pydicom
import numpy as np
import pyvista as pv
import tkinter as tk
from tkinter import filedialog
import vtk
from vtk.util.numpy_support import numpy_to_vtk
import time

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description='3D DICOM hologram viewer')
    parser.add_argument('--folder', type=str, help='Path to DICOM folder')
    parser.add_argument('--output', type=str, help='Output directory for images')
    return parser.parse_args()

# === Step 1: Ask user to select the DICOM folder ===
def select_folder():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    folder_path = filedialog.askdirectory(title="Select folder containing DICOM files")
    root.destroy()
    return folder_path

# Prompt user to select folder or use command line arguments
if __name__ == "__main__":
    args = parse_args()
    
    if args.folder and args.output:
        # Make sure output directory exists
        os.makedirs(args.output, exist_ok=True)
        
        # Skip tkinter folder selection
        folder_path = args.folder
        
        print(f"Selected folder: {folder_path}")
    else:
        # Original behavior
        print("Please select the folder containing DICOM files...")
        folder_path = select_folder()
        
        if not folder_path:
            print("No folder selected. Exiting...")
            exit()

        print(f"Selected folder: {folder_path}")

    # Check for DICOM files (with .dcm or .IMA extension, case insensitive)
    dicom_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.dcm') or f.lower().endswith('.ima')]

    if not dicom_files:
        raise ValueError("No DICOM files found in the selected folder. Looking for .dcm or .IMA files.")

    # Read DICOM metadata from first file to get dimensions
    first_dicom = pydicom.dcmread(os.path.join(folder_path, dicom_files[0]))
    rows = first_dicom.Rows
    cols = first_dicom.Columns
    
    try:
        # Try to get pixel spacing information
        pixel_spacing = first_dicom.PixelSpacing
        slice_thickness = first_dicom.SliceThickness
    except:
        # Use default values if not available
        pixel_spacing = [1.0, 1.0]
        slice_thickness = 1.0
    
    # Read and store pixel data with slice order
    slices = []
    for fname in dicom_files:
        try:
            ds = pydicom.dcmread(os.path.join(folder_path, fname))
            # Handle DICOM files with different slice number attributes
            if hasattr(ds, 'InstanceNumber'):
                slice_num = ds.InstanceNumber
            elif hasattr(ds, 'SliceLocation'):
                slice_num = ds.SliceLocation
            else:
                # Use file order if slice number not available
                slice_num = dicom_files.index(fname)
            
            slices.append((slice_num, ds.pixel_array))
        except Exception as e:
            print(f"Error reading {fname}: {e}")
            continue

    if not slices:
        raise ValueError("Could not read any valid DICOM slices")

    # Sort and stack the images in correct order
    slices.sort(key=lambda x: x[0])  # Sort by slice number
    try:
        volume = np.stack([s[1] for s in slices], axis=0).astype(np.float32)
    except ValueError as e:
        print(f"Error stacking slices: {e}")
        # Try to handle slices with different dimensions
        # Resize all slices to match the first one
        from skimage.transform import resize
        ref_shape = slices[0][1].shape
        resized_slices = []
        for s in slices:
            if s[1].shape != ref_shape:
                resized_slices.append(resize(s[1], ref_shape, preserve_range=True).astype(np.float32))
            else:
                resized_slices.append(s[1].astype(np.float32))
        volume = np.stack(resized_slices, axis=0)

    # Normalize volume data to 0-255 range
    if np.max(volume) != np.min(volume):
        volume = (volume - np.min(volume)) / (np.max(volume) - np.min(volume))
        volume = (volume * 255).astype(np.uint8)
    else:
        # Handle the case where all voxels have the same value
        volume = np.zeros_like(volume, dtype=np.uint8)

    # Create a 3D mesh for better visualization
    # First, create a voxel-based representation
    try:
        # Create structured grid
        grid = pv.UniformGrid()
        grid.dimensions = volume.shape
        grid.spacing = (pixel_spacing[0], pixel_spacing[1], slice_thickness)
        grid.point_data["values"] = volume.flatten(order='F')
        
        # Create isosurface for 3D rendering
        threshold_value = np.percentile(volume, 75)  # Adjust this threshold as needed
        contours = grid.contour([threshold_value])
    
        # Check if running in command line mode with output path
        if args.folder and args.output:
            # Generate multiple views for better user experience
            output_views = []
            
            # Create a plotter with nice settings for 3D rendering
            plotter = pv.Plotter(off_screen=True, window_size=[800, 800])
            
            # Add the mesh with nice rendering settings
            plotter.add_mesh(
                contours,
                color='white',
                specular=1.0,
                specular_power=15,
                smooth_shading=True,
                ambient=0.3
            )
            
            # Add a bounding box for context
            plotter.add_bounding_box(color='gray', opacity=0.3)
            
            # Default front view
            plotter.camera_position = 'xz'
            plotter.camera.zoom(1.2)
            output_file = os.path.join(args.output, '3d_hologram_front.png')
            plotter.screenshot(output_file, transparent_background=True)
            output_views.append('/static/results/' + os.path.basename(output_file))
            
            # Spin view 45 degrees
            plotter.camera.azimuth(45)
            plotter.camera.elevation(20)
            output_file = os.path.join(args.output, '3d_hologram_angle1.png')
            plotter.screenshot(output_file, transparent_background=True)
            output_views.append('/static/results/' + os.path.basename(output_file))
            
            # Spin view another 45 degrees
            plotter.camera.azimuth(45)
            output_file = os.path.join(args.output, '3d_hologram_angle2.png')
            plotter.screenshot(output_file, transparent_background=True)
            output_views.append('/static/results/' + os.path.basename(output_file))
            
            # Top view
            plotter.camera_position = 'xy'
            output_file = os.path.join(args.output, '3d_hologram_top.png')
            plotter.screenshot(output_file, transparent_background=True)
            output_views.append('/static/results/' + os.path.basename(output_file))
            
            # Create an animated GIF to show rotation
            try:
                import imageio
                plotter.open_gif(os.path.join(args.output, '3d_hologram.gif'))
                for i in range(36):  # 36 frames for 360 degrees
                    plotter.camera.azimuth(10)  # Rotate 10 degrees per frame
                    plotter.write_frame()
                plotter.close()
                output_views.append('/static/results/3d_hologram.gif')
            except ImportError:
                print("imageio not installed, skipping GIF creation")
            
            # Export main image
            output_file = os.path.join(args.output, '3d_hologram.png')
            plotter.screenshot(output_file, transparent_background=True)
            output_views.append('/static/results/' + os.path.basename(output_file))
            
            print(f"3D visualization saved to: {output_file}")
            print(f"Additional views: {output_views}")
            
            # Create a simple HTML viewer for the app to display
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ background-color: #000; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                    .container {{ position: relative; max-width: 100%; max-height: 100%; }}
                    .hologram {{ max-width: 100%; max-height: 100vh; display: block; margin: auto; }}
                    .buttons {{ position: absolute; bottom: 20px; width: 100%; display: flex; justify-content: center; gap: 10px; }}
                    .btn {{ background-color: rgba(0,0,0,0.7); color: white; border: 1px solid #555; padding: 5px 10px; cursor: pointer; }}
                </style>
                <script>
                    let currentView = 0;
                    const views = {output_views};
                    
                    function changeView(idx) {{
                        currentView = idx;
                        document.getElementById('hologram').src = views[idx];
                    }}
                    
                    function rotateView() {{
                        currentView = (currentView + 1) % views.length;
                        document.getElementById('hologram').src = views[currentView];
                        setTimeout(rotateView, 2000);
                    }}
                    
                    window.onload = function() {{
                        // Start with the GIF if available
                        const gifIndex = views.findIndex(v => v.endsWith('.gif'));
                        if (gifIndex >= 0) {{
                            changeView(gifIndex);
                        }}
                        
                        // Auto-rotate views
                        setTimeout(rotateView, 3000);
                    }};
                </script>
            </head>
            <body>
                <div class="container">
                    <img id="hologram" src="{output_views[-1]}" class="hologram" />
                </div>
            </body>
            </html>
            """
            
            with open(os.path.join(args.output, 'viewer.html'), 'w') as f:
                f.write(html_content)
            
        else:
            # Interactive mode
            plotter = pv.Plotter()
            plotter.add_mesh(
                contours,
                color='white',
                specular=1.0,
                smooth_shading=True
            )
            plotter.add_bounding_box()
            plotter.show(title="3D DICOM Hologram Viewer")
    
    except Exception as e:
        import traceback
        print(f"Error creating 3D visualization: {e}")
        print(traceback.format_exc())
        
        # Fallback to volume rendering if mesh creation fails
        try:
            # Use off-screen rendering for saving to file
            plotter = pv.Plotter(off_screen=True)
            plotter.add_volume(
                volume,
                cmap="bone",
                opacity="linear",
                shade=True
            )
            plotter.add_axes()
            
            # Save screenshot to output directory
            output_file = os.path.join(args.output, '3d_hologram.png')
            plotter.screenshot(output_file)
            print(f"Fallback 3D visualization saved to: {output_file}")
        except Exception as e2:
            print(f"Fallback rendering also failed: {e2}")
            # Create a very simple error image
            import matplotlib.pyplot as plt
            plt.figure(figsize=(8, 6))
            plt.text(0.5, 0.5, "3D rendering failed", ha='center', va='center', fontsize=20)
            plt.axis('off')
            plt.savefig(os.path.join(args.output, '3d_hologram.png'))
            plt.close()
