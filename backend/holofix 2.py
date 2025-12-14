# IMPORTS
import os
import argparse
import pydicom
import numpy as np
import pyvista as pv
import tkinter as tk
from tkinter import filedialog

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

    # Read and store pixel data with slice order
    slices = []
    for fname in dicom_files:
        ds = pydicom.dcmread(os.path.join(folder_path, fname))
        slices.append((ds.InstanceNumber, ds.pixel_array))

    # Sort and stack the images in correct order
    slices.sort(key=lambda x: x[0])  # Sort by InstanceNumber
    volume = np.stack([s[1] for s in slices], axis=-1).astype(np.int16)

    # Normalize for display
    volume = (volume - np.min(volume)) / (np.max(volume) - np.min(volume))
    volume = (volume * 255).astype(np.uint8)

    # === Step 2: Visualize 3D Volume with pyvista ===
    grid = pv.wrap(volume)

      # Check if running in command line mode with output path
    if args.folder and args.output:
        # Use off-screen rendering for saving to file
        plotter = pv.Plotter(off_screen=True)
        plotter.add_volume(
            grid,
            cmap="bone",
            opacity="linear",
            shade=True
        )
        plotter.add_axes()
        
        # Save screenshot to output directory
        output_file = os.path.join(args.output, '3d_hologram.png')
        plotter.screenshot(output_file)
        print(f"3D visualization saved to: {output_file}")
    else:
        # Interactive mode
        plotter = pv.Plotter()
        plotter.add_volume(
            grid,
            cmap="bone",
            opacity="linear",
            shade=True
        )
        plotter.add_axes()
        plotter.show(title="3D CT Volume Viewer (from DICOM)")
