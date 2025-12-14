#IMPORTS
import os
import argparse
import numpy as np
import pydicom
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from tkinter import Tk, filedialog
Tk().withdraw()  # Prevent tkinter window from appearing

# Add at the top of the file
def parse_args():
    parser = argparse.ArgumentParser(description='Interactive DICOM viewer')
    parser.add_argument('--folder', type=str, help='Path to DICOM folder')
    parser.add_argument('--output', type=str, help='Output directory for images')
    return parser.parse_args()

def load_scan(path):
    """Load all DICOM files in the specified directory"""
    slices = []
    for s in os.listdir(path):
        try:
            file_path = os.path.join(path, s)
            if os.path.isfile(file_path) and not s.startswith('.'):
                ds = pydicom.dcmread(file_path)
                slices.append(ds)
        except:
            print(f"Error reading file: {s}")
    
    # Sort slices
    try:
        slices.sort(key=lambda x: float(x.ImagePositionPatient[2]))
    except:
        try:
            slices.sort(key=lambda x: float(x.SliceLocation))
        except:
            try:
                slices.sort(key=lambda x: int(x.InstanceNumber))
            except:
                print("Could not sort slices, using original order")
    
    return slices


def get_pixels_hu(slices):
    """Convert raw pixel values to Hounsfield units if possible"""
    image = np.stack([s.pixel_array for s in slices])
    
    # Convert to int16 to avoid overflow
    image = image.astype(np.int16)
    
    # Apply slope and intercept if available (conversion to Hounsfield units)
    try:
        intercept = slices[0].RescaleIntercept
        slope = slices[0].RescaleSlope
        
        if slope != 1:
            image = slope * image.astype(np.float64)
            image = image.astype(np.int16)
            
        image += np.int16(intercept)
    except:
        print("Could not apply rescale slope/intercept, using raw pixel values")
    
    return np.array(image, dtype=np.int16)


def apply_ct_window(img, window_center=-600, window_width=1500, alpha=1.0):
    """
    Apply a CT window to the image and create a transparent grayscale image
    
    Parameters:
    - img: Input image array
    - window_center: Center of windowing range in HU
    - window_width: Width of windowing range in HU
    - alpha: Transparency level (1.0 = fully opaque, 0.0 = fully transparent)
    
    Returns:
    - RGBA image with grayscale values and transparency
    """
    # Apply windowing function to get values between 0 and 1
    img_min = window_center - window_width // 2
    img_max = window_center + window_width // 2
    
    img_windowed = np.clip(img, img_min, img_max)
    img_normalized = (img_windowed - img_min) / (img_max - img_min)
    
    # Create an RGBA grayscale image with transparency
    rgba_img = np.zeros((*img.shape, 4))
    
    # Set RGB channels to the same value (grayscale)
    rgba_img[..., 0] = img_normalized  # R
    rgba_img[..., 1] = img_normalized  # G
    rgba_img[..., 2] = img_normalized  # B
    
    # Set alpha channel based on intensity and input alpha
    # Lower intensity pixels will be more transparent
    rgba_img[..., 3] = img_normalized * alpha
    
    return rgba_img


def interactive_slice_viewer(dicom_folder=None):
    """Interactive slice viewer with standard CT grayscale styling"""
    # If no folder provided, open dialog to select one
    if dicom_folder is None:
        print("Select your DICOM folder...")
        dicom_folder = filedialog.askdirectory(title="Select DICOM Folder")
        if not dicom_folder:
            print("No folder selected")
            return
    
    print(f"Loading DICOM data from: {dicom_folder}")
    
    # Load scan
    slices = load_scan(dicom_folder)
    if not slices:
        print("No valid DICOM files found")
        return
    
    print(f"Loaded {len(slices)} slices")
    
    # Convert to Hounsfield units
    pixel_data = get_pixels_hu(slices)
    
    # Get spacing information
    try:
        spacing = (
            float(slices[0].PixelSpacing[0]),
            float(slices[0].PixelSpacing[1]),
            float(slices[0].SliceThickness)
        )
    except:
        spacing = (1.0, 1.0, 1.0)
    
    print(f"Volume dimensions: {pixel_data.shape} with spacing: {spacing}")
    
    # Set up the figure and initial display
    fig, ax = plt.subplots(figsize=(10, 8))
    plt.subplots_adjust(bottom=0.25)  # Make room for slider
    
    # Set white background for traditional CT display
    fig.patch.set_facecolor('white')
    ax.set_facecolor('black')
    
    # Show initial slice (middle of the stack)
    z_index = len(slices) // 2
    img = pixel_data[z_index]
    
    # Apply CT windowing and transparency
    rgba_img = apply_ct_window(img)
    
    # Display the image
    img_display = ax.imshow(rgba_img, aspect='equal')
    
    # Remove axis ticks and labels for cleaner appearance
    ax.set_xticks([])
    ax.set_yticks([])
    
    # Add title
    ax.set_title('Interactive CT Visualization', color='black', fontsize=16)
    
    # Add slider for scrolling through slices
    ax_slider = plt.axes([0.25, 0.1, 0.65, 0.03], facecolor='lightgray')
    slice_slider = Slider(
        ax=ax_slider,
        label='Slice',
        valmin=0,
        valmax=len(slices)-1,
        valinit=z_index,
        valfmt='%d',
        color='gray'
    )
    
    # Add window sliders for CT adjustment
    ax_center = plt.axes([0.25, 0.06, 0.65, 0.03], facecolor='lightgray')
    center_slider = Slider(
        ax=ax_center,
        label='Level',
        valmin=-1000,
        valmax=3000,
        valinit=-600,
        valfmt='%d',
        color='gray'
    )
    
    ax_width = plt.axes([0.25, 0.02, 0.65, 0.03], facecolor='lightgray')
    width_slider = Slider(
        ax=ax_width,
        label='Window',
        valmin=1,
        valmax=4000,
        valinit=1500,
        valfmt='%d',
        color='gray'
    )
    
    # Add text showing slice number and total
    text = ax.text(0.02, 0.02, f'Slice: {z_index+1}/{len(slices)}', 
                   transform=ax.transAxes, color='white')
    
    # Function to update display when slider changes
    def update(val):
        z_idx = int(slice_slider.val)
        center = center_slider.val
        width = width_slider.val
        
        new_img = pixel_data[z_idx]
        img_display.set_array(apply_ct_window(new_img, window_center=center, window_width=width))
        text.set_text(f'Slice: {z_idx+1}/{len(slices)}')
        fig.canvas.draw_idle()
    
    slice_slider.on_changed(update)
    center_slider.on_changed(update)
    width_slider.on_changed(update)
    
    # Display
    plt.show()


def multi_view_display(dicom_folder=None):
    """Display three orthogonal views of the data with standard CT styling"""
    # If no folder provided, open dialog to select one
    if dicom_folder is None:
        print("Select your DICOM folder...")
        dicom_folder = filedialog.askdirectory(title="Select DICOM Folder")
        if not dicom_folder:
            print("No folder selected")
            return
    
    # Load scan
    slices = load_scan(dicom_folder)
    if not slices:
        print("No valid DICOM files found")
        return
    
    # Convert to Hounsfield units
    pixel_data = get_pixels_hu(slices)
    
    # Create figure with white background
    fig = plt.figure(figsize=(15, 8))
    fig.patch.set_facecolor('white')
    
    # Calculate middle indices
    z_mid = pixel_data.shape[0] // 2
    y_mid = pixel_data.shape[1] // 2
    x_mid = pixel_data.shape[2] // 2
    
    # Axial view (top left)
    ax1 = fig.add_subplot(1, 3, 1)
    ax1.set_facecolor('black')
    ax1.imshow(apply_ct_window(pixel_data[z_mid]))
    ax1.set_title('Axial', color='black', fontsize=14)
    ax1.set_xticks([])
    ax1.set_yticks([])
    
    # Coronal view (top middle)
    ax2 = fig.add_subplot(1, 3, 2)
    ax2.set_facecolor('black')
    ax2.imshow(apply_ct_window(pixel_data[:, y_mid, :]))
    ax2.set_title('Coronal', color='black', fontsize=14)
    ax2.set_xticks([])
    ax2.set_yticks([])
    
    # Sagittal view (top right)
    ax3 = fig.add_subplot(1, 3, 3)
    ax3.set_facecolor('black')
    ax3.imshow(apply_ct_window(pixel_data[:, :, x_mid]))
    ax3.set_title('Sagittal', color='black', fontsize=14)
    ax3.set_xticks([])
    ax3.set_yticks([])
    
    # Main title
    fig.suptitle('CT Visualization', color='black', fontsize=16)
    plt.tight_layout()
    
    plt.show()


def create_animated_rotation(dicom_folder=None):
    """Create a series of images that simulate rotation around the object"""
    # If no folder provided, open dialog to select one
    if dicom_folder is None:
        print("Select your DICOM folder...")
        dicom_folder = filedialog.askdirectory(title="Select DICOM Folder")
        if not dicom_folder:
            print("No folder selected")
            return
    
    # Load scan
    slices = load_scan(dicom_folder)
    if not slices:
        print("No valid DICOM files found")
        return
    
    # Convert to Hounsfield units
    pixel_data = get_pixels_hu(slices)
    
    # Create output directory for frames
    frames_dir = os.path.join(os.getcwd(), "ct_frames")
    if not os.path.exists(frames_dir):
        os.makedirs(frames_dir)
    
    # Number of frames to generate
    n_frames = 36  # 10 degrees per frame for full 360 rotation
    
    # Add rotation effect by cycling through slices and applying visual effects
    print("Generating rotation frames...")
    
    for i in range(n_frames):
        # Set up figure
        fig = plt.figure(figsize=(8, 8))
        fig.patch.set_facecolor('white')
        ax = plt.subplot(111)
        ax.set_facecolor('black')
        
        # Select slice (cycle through available slices)
        slice_idx = i % len(slices)
        img = pixel_data[slice_idx]
        
        # Apply CT windowing
        rgba_img = apply_ct_window(img)
        
        # Display with standard CT appearance
        ax.imshow(rgba_img)
        
        # Add subtle grid overlay
        # Create grid lines
        rows, cols = img.shape
        for r in range(0, rows, rows//10):
            x = np.linspace(0, cols-1, 100)
            y = np.ones(100) * r
            ax.plot(x, y, color='white', alpha=0.2, linewidth=0.5)
        
        for c in range(0, cols, cols//10):
            y = np.linspace(0, rows-1, 100)
            x = np.ones(100) * c
            ax.plot(x, y, color='white', alpha=0.2, linewidth=0.5)
        
        # Add angle indicator
        ax.text(0.02, 0.02, f'Angle: {i*10}°', transform=ax.transAxes, 
               color='white', fontsize=12)
        
        # Add frame number indicator
        ax.text(0.02, 0.06, f'Frame: {i+1}/{n_frames}', transform=ax.transAxes,
               color='white', fontsize=12)
        
        # Add slice indicator
        ax.text(0.02, 0.10, f'Slice: {slice_idx+1}/{len(slices)}', transform=ax.transAxes,
               color='white', fontsize=12)
        
        # Remove axis ticks
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Save the frame
        filename = os.path.join(frames_dir, f"frame_{i:03d}.png")
        plt.savefig(filename, facecolor='white', dpi=100)
        plt.close()
        
        # Show progress
        if (i+1) % 5 == 0 or i == 0 or i == n_frames-1:
            print(f"Generated frame {i+1}/{n_frames}")
    
    print(f"\nAnimation frames saved to: {frames_dir}")
    print("You can combine these frames into an animation using tools like:")
    print("- ImageJ (File > Import > Image Sequence)")
    print("- ffmpeg (ffmpeg -framerate 10 -i frame_%03d.png -c:v libx264 ct_animation.mp4)")
    print("- Any video editing software")


if __name__ == "__main__":
    args = parse_args()
    
    if args.folder and args.output:
        # Make sure output directory exists
        os.makedirs(args.output, exist_ok=True)
        
        # Run with the specified folder
        print(f"Processing DICOM files from: {args.folder}")
        
        # Call the interactive viewer with command line arguments
        interactive_slice_viewer(args.folder)
        
        # Save the result
        output_file = os.path.join(args.output, 'slice_view.png')
        plt.savefig(output_file)
        plt.close()
        print(f"Visualization saved to: {output_file}")
    else:
        # Simplified original behavior - only Interactive Slice Viewer
        print("DICOM Interactive Slice Viewer")
        interactive_slice_viewer()
