import base64
import json
import re
import time
import os
from pathlib import Path
import streamlit as st
import tempfile
import shutil
import zipfile
import warnings

# External libraries for analysis
import google.generativeai as genai
from iptcinfo3 import IPTCInfo
from PIL import Image

# External libraries for metadata removal
try:
    import rawpy
    import numpy as np
    RAW_SUCCESS = True
except ImportError:
    RAW_SUCCESS = False

# Set page config first - must be the first Streamlit command
st.set_page_config(
    page_title="Image Metadata Utility",
    page_icon="solsticelogo.png",  # Keep favicon
    layout="wide"
)

# Custom CSS for button styling (removed logo-related CSS)
st.markdown("""
<style>
.stButton > button {
    background-color: #ff6633;
    color: white;
}

.stButton > button:hover {
    background-color: #e6734d;
}
</style>
""", unsafe_allow_html=True)

# Suppress iptcinfo3 charset warnings
warnings.filterwarnings("ignore", message="problems with charset recognition")

# System prompt for Gemini analysis
SYSTEM_PROMPT = """
You're the big dog of image metadata analysis, hitting it straight off the tee. 
When I feed you an image encoded in Base64, you need to look deep and yank out the IPTC metadata.

Output it as clean JSON, with these keys:

- "caption": A quick summary, like a birdie putt
- "keywords": A list of tags, like hazards to avoid
- "byline": Who took the picture, the caddie's info
- "credit": Where the props go, like the club house
- "source": Where it's from, like the tee box

Keep it all solid valid JSON, no chitchat, and avoid going into the rough (don't add any commentary or markdown).
Be sure to use golf colloquialisms whenever appropriate. And ALWAYS add a keyword describing the emotion of the humans in any image if they are present.
"""

# Create a temporary directory for processing files
if 'temp_dir' not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp()

# Initialize session state for processed files if not exists
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = []

# Initialize session state for clearing uploaded files
if 'clear_uploaded_tagging' not in st.session_state:
    st.session_state.clear_uploaded_tagging = False
if 'clear_uploaded_stripping' not in st.session_state:
    st.session_state.clear_uploaded_stripping = False

# Removed logo file debug, as it’s no longer used in the UI

# ---------------------------
# Functions for Image Analysis (Tagging)
# ---------------------------
def encode_image(image_file):
    """Encodes an image to Base64 from file-like object."""
    try:
        return base64.b64encode(image_file.getvalue()).decode("utf-8")
    except Exception:
        return None

def analyze_image(image_file, api_key, max_retries=5):
    """Analyzes the image with Gemini, using exponential backoff on failures."""
    base64_image = encode_image(image_file)
    if base64_image is None:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception:
        return None

    prompt_parts = [
        SYSTEM_PROMPT,
        {"mime_type": "image/jpeg", "data": base64_image}
    ]

    retries = 0
    while retries <= max_retries:
        try:
            response = model.generate_content(prompt_parts)
            if not response.text:
                return None

            json_string = response.text.strip()

            # Remove markdown code fences if present
            if json_string.startswith("```"):
                lines = json_string.splitlines()
                if lines and lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                json_string = "\n".join(lines).strip()

            # Remove Unicode control characters
            json_string = re.sub(r'[\x00-\x1F\x7F-\x9F\u2000-\u200D\uFEFF]', '', json_string)

            if not json_string:
                return None

            try:
                json_data = json.loads(json_string)
                return json_data
            except json.JSONDecodeError:
                return None

        except Exception:
            if retries < max_retries:
                time.sleep(2 ** retries)
                retries += 1
            else:
                return None

    return None

def write_image_metadata(image_file, output_path, metadata):
    """
    Writes metadata to the image.
    For JPEG files, it uses IPTCInfo to write IPTC metadata.
    For PNG files, it embeds the metadata as textual chunks using Pillow.
    """
    temp_file_path = os.path.join(st.session_state.temp_dir, image_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(image_file.getvalue())
    
    ext = os.path.splitext(image_file.name)[1].lower()
    
    try:
        if ext in [".jpg", ".jpeg"]:
            info = IPTCInfo(temp_file_path, force=True)
            if metadata.get("caption"):
                info['caption/abstract'] = metadata["caption"].encode('utf-8').decode('utf-8', errors='ignore')
            if metadata.get("keywords") and isinstance(metadata["keywords"], list):
                info['keywords'] = [k.encode('utf-8').decode('utf-8', errors='ignore') for k in metadata["keywords"]]
            if metadata.get("byline"):
                info['by-line'] = metadata["byline"].encode('utf-8').decode('utf-8', errors='ignore')
            if metadata.get("credit"):
                info['credit'] = metadata["credit"].encode('utf-8').decode('utf-8', errors='ignore')
            if metadata.get("source"):
                info['source'] = metadata["source"].encode('utf-8').decode('utf-8', errors='ignore')
            info.save_as(output_path)
            return True
        
        elif ext == ".png":
            from PIL import PngImagePlugin
            im = Image.open(temp_file_path)
            pnginfo = PngImagePlugin.PngInfo()
            if metadata.get("caption"):
                pnginfo.add_text("caption", metadata["caption"].encode('utf-8').decode('utf-8', errors='ignore'))
            if metadata.get("keywords"):
                if isinstance(metadata["keywords"], list):
                    pnginfo.add_text("keywords", ", ".join([k.encode('utf-8').decode('utf-8', errors='ignore') for k in metadata["keywords"]]))
                else:
                    pnginfo.add_text("keywords", metadata["keywords"].encode('utf-8').decode('utf-8', errors='ignore'))
            if metadata.get("byline"):
                pnginfo.add_text("byline", metadata["byline"].encode('utf-8').decode('utf-8', errors='ignore'))
            if metadata.get("credit"):
                pnginfo.add_text("credit", metadata["credit"].encode('utf-8').decode('utf-8', errors='ignore'))
            if metadata.get("source"):
                pnginfo.add_text("source", metadata["source"].encode('utf-8').decode('utf-8', errors='ignore'))
            im.save(output_path, pnginfo=pnginfo)
            return True
        else:
            return False
    except Exception as e:
        st.error(f"Error writing metadata for {image_file.name}: {e}")
        return False
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# ---------------------------
# Functions for Metadata Removal (Stripping)
# ---------------------------
def remove_metadata_image(image_file, output_path):
    """Removes metadata from an image by recreating it from pixel data."""
    temp_file_path = os.path.join(st.session_state.temp_dir, image_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(image_file.getvalue())
    
    try:
        with Image.open(temp_file_path) as img:
            new_img = Image.new(img.mode, img.size)
            new_img.paste(img)
            new_img.save(output_path)
        return True
    except Exception as e:
        st.error(f"Error removing metadata from {image_file.name}: {e}")
        return False
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def process_raw_cr2(image_file, output_path):
    """Converts a .cr2 RAW image to JPEG format without metadata."""
    if not RAW_SUCCESS:
        return False
    
    temp_file_path = os.path.join(st.session_state.temp_dir, image_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(image_file.getvalue())
    
    try:
        with rawpy.imread(temp_file_path) as raw:
            rgb_image = raw.postprocess()
        img = Image.fromarray(rgb_image)
        img.save(output_path, "JPEG", quality=95)
        return True
    except Exception as e:
        st.error(f"Error processing RAW file {image_file.name}: {e}")
        return False
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# ---------------------------
# Main Application
# ---------------------------
def main():
    # Simple title without logo
    st.title("Image Metadata Utility")
    
    # Caption with copyright (no logo)
    st.caption("© Solstice Solutions | all rights reserved")
    
    # Create tabs for the different functions
    tab1, tab2 = st.tabs(["Tagging (Analysis)", "Stripping (Metadata Removal)"])
    
    with tab1:
        st.header("Tagging (Analysis)")
        
        # API Key input
        api_key = st.text_input("API Key:", type="password")
        
        # File uploader for multiple images with dynamic key
        uploader_key = "tagging_files" if not st.session_state.clear_uploaded_tagging else "tagging_files_clear"
        uploaded_files = st.file_uploader(
            "Upload images for analysis", 
            type=["jpg", "jpeg", "png"], 
            accept_multiple_files=True,
            key=uploader_key
        )
        
        # Layout with main content and clear buttons on the right
        col1, col2 = st.columns([0.9, 0.1])  # 90% for content, 10% for buttons
        
        with col1:
            if uploaded_files:
                st.success(f"Selected {len(uploaded_files)} images for analysis")
                
                # Calculate number of columns based on number of files
                num_files = len(uploaded_files)
                num_columns = min(max(2, num_files // 4), 6)  # Limit to 2–6 columns
                
                # Distribute file names across columns
                cols = st.columns(num_columns)
                st.write("Uploaded files:")
                for i, file in enumerate(uploaded_files):
                    with cols[i % num_columns]:
                        st.write(f"- {file.name}")  # Use bullet points for a clean list
        
        with col2:
            # Clear uploaded images button
            if uploaded_files and st.button("Clear Uploaded Images", key="clear_uploaded_tagging_button"):
                st.session_state.clear_uploaded_tagging = not st.session_state.clear_uploaded_tagging
                st.experimental_rerun()  # Force a rerun to reset the uploader
        
        # Process button with spinner
        if st.button("Analyze Images", type="primary", disabled=not uploaded_files or not api_key, key="analyze_button"):
            if not api_key:
                st.error("Please enter a valid API key")
            elif not uploaded_files:
                st.error("Please upload at least one image for analysis")
            else:
                with st.spinner("Analyzing images..."):
                    process_tagging(uploaded_files, api_key)
        
        # Download options for processed files in columns
        if st.session_state.processed_files:
            num_processed_files = len(st.session_state.processed_files)
            num_download_columns = min(max(2, num_processed_files // 4), 6)  # Limit to 2–6 columns
            
            download_cols = st.columns(num_download_columns)
            # Place ZIP button at the top in the first column
            if len(st.session_state.processed_files) > 1:
                zip_path = os.path.join(st.session_state.temp_dir, "tagged_images.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in st.session_state.processed_files:
                        zipf.write(file, os.path.basename(file))
                
                with open(zip_path, "rb") as f:
                    with download_cols[0]:
                        st.download_button(
                            label="Download All as ZIP",
                            data=f,
                            file_name="tagged_images.zip",
                            mime="application/zip",
                            key="download_all_zip_tagging"
                        )
            
            # Distribute individual download buttons across columns
            for i, file_path in enumerate(st.session_state.processed_files):
                file_name = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    with download_cols[i % num_download_columns]:
                        st.download_button(
                            label=f"Download {file_name}",
                            data=f,
                            file_name=file_name,
                            mime=f"image/{os.path.splitext(file_name)[1][1:]}",
                            key=f"download_tagging_{file_name}_{i}"
                        )
        
        # Clear outputs button on the right
        col3, col4 = st.columns([0.9, 0.1])
        with col4:
            if st.session_state.processed_files and st.button("Clear Outputs", key="clear_outputs_tagging"):
                for file_path in st.session_state.processed_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                st.session_state.processed_files = []
                st.success("Output files cleared!")

    with tab2:
        st.header("Stripping (Metadata Removal)")
        
        # File uploader for multiple images with dynamic key
        uploader_key = "stripping_files" if not st.session_state.clear_uploaded_stripping else "stripping_files_clear"
        uploaded_files = st.file_uploader(
            "Upload images for metadata removal", 
            type=["jpg", "jpeg", "png", "bmp", "gif", "tiff"] + (["cr2"] if RAW_SUCCESS else []), 
            accept_multiple_files=True,
            key=uploader_key
        )
        
        # Layout with main content and clear buttons on the right
        col1, col2 = st.columns([0.9, 0.1])  # 90% for content, 10% for buttons
        
        with col1:
            if uploaded_files:
                st.success(f"Selected {len(uploaded_files)} images for removal")
                
                # Calculate number of columns based on number of files
                num_files = len(uploaded_files)
                num_columns = min(max(2, num_files // 4), 6)  # Limit to 2–6 columns
                
                # Distribute file names across columns
                cols = st.columns(num_columns)
                st.write("Uploaded files:")
                for i, file in enumerate(uploaded_files):
                    with cols[i % num_columns]:
                        st.write(f"- {file.name}")  # Use bullet points for a clean list
        
        with col2:
            # Clear uploaded images button
            if uploaded_files and st.button("Clear Uploaded Images", key="clear_uploaded_stripping_button"):
                st.session_state.clear_uploaded_stripping = not st.session_state.clear_uploaded_stripping
                st.experimental_rerun()  # Force a rerun to reset the uploader
        
        # Process button with spinner
        if st.button("Remove Metadata", type="primary", disabled=not uploaded_files, key="remove_button"):
            if not uploaded_files:
                st.error("Please upload at least one image for metadata removal")
            else:
                with st.spinner("Removing metadata..."):
                    process_stripping(uploaded_files)
        
        # Download options for processed files in columns
        if st.session_state.processed_files:
            num_processed_files = len(st.session_state.processed_files)
            num_download_columns = min(max(2, num_processed_files // 4), 6)  # Limit to 2–6 columns
            
            download_cols = st.columns(num_download_columns)
            # Place ZIP button at the top in the first column
            if len(st.session_state.processed_files) > 1:
                zip_path = os.path.join(st.session_state.temp_dir, "stripped_images.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in st.session_state.processed_files:
                        zipf.write(file, os.path.basename(file))
                
                with open(zip_path, "rb") as f:
                    with download_cols[0]:
                        st.download_button(
                            label="Download All as ZIP",
                            data=f,
                            file_name="stripped_images.zip",
                            mime="application/zip",
                            key="download_all_zip_stripping"
                        )
            
            # Distribute individual download buttons across columns
            for i, file_path in enumerate(st.session_state.processed_files):
                file_name = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    with download_cols[i % num_download_columns]:
                        st.download_button(
                            label=f"Download {file_name}",
                            data=f,
                            file_name=file_name,
                            mime=f"image/{os.path.splitext(file_name)[1][1:]}",
                            key=f"download_stripping_{file_name}_{i}"
                        )
        
        # Clear outputs button on the right
        col3, col4 = st.columns([0.9, 0.1])
        with col4:
            if st.session_state.processed_files and st.button("Clear Outputs", key="clear_outputs_stripping"):
                for file_path in st.session_state.processed_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                st.session_state.processed_files = []
                st.success("Output files cleared!")

def process_tagging(files, api_key):
    """Process uploaded files and analyze them for metadata tagging."""
    # Create a place to store processed files
    output_dir = os.path.join(st.session_state.temp_dir, "tagged_images")
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each file silently
    processed_files = []
    for file in files:
        output_path = os.path.join(output_dir, file.name)
        metadata = analyze_image(file, api_key)
        if metadata and write_image_metadata(file, output_path, metadata):
            processed_files.append(output_path)
    
    # Update session state with processed files
    st.session_state.processed_files = processed_files

def process_stripping(files):
    """Process uploaded files and strip their metadata."""
    # Create a place to store processed files
    output_dir = os.path.join(st.session_state.temp_dir, "stripped_images")
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each file silently
    processed_files = []
    for file in files:
        # Determine if this is a RAW file
        is_raw = file.name.lower().endswith('.cr2')
        
        # Create output filename
        if is_raw:
            output_path = os.path.join(output_dir, os.path.splitext(file.name)[0] + ".jpg")
            success = process_raw_cr2(file, output_path)
        else:
            output_path = os.path.join(output_dir, file.name)
            success = remove_metadata_image(file, output_path)
        
        if success:
            processed_files.append(output_path)
    
    # Update session state with processed files
    st.session_state.processed_files = processed_files

# Run the application
if __name__ == "__main__":
    main()
