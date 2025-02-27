# Image Metadata Utility

A Streamlit web application for managing image metadata with two primary features:

1. **Tagging (Analysis)**: Add AI-generated metadata to images using Google's Gemini API
2. **Stripping (Metadata Removal)**: Remove all metadata from images for privacy

## Features

### Tagging (Analysis)
- Analyzes images using Google's Gemini API
- Extracts and adds metadata including captions, keywords, byline, credit, and source
- Supports JPEG and PNG formats
- Downloads processed images individually or as a zip file

### Stripping (Metadata Removal)
- Removes all metadata from images by recreating them
- Supports multiple formats: JPEG, PNG, BMP, GIF, TIFF
- Optional support for Canon RAW (CR2) files
- Downloads clean images individually or as a zip file

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/image-metadata-utility.git
cd image-metadata-utility
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. For RAW file support (optional), uncomment and install these dependencies in requirements.txt:
```
rawpy>=0.18.0
numpy>=1.24.0
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

3. For the Tagging feature, you'll need a Google Gemini API key:
   - Get your API key from [Google AI Studio](https://aistudio.google.com/)
   - Enter the key in the app when prompted

## Deployment

You can deploy this application on Streamlit Cloud:

1. Push this code to a GitHub repository
2. Connect your GitHub account to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy the app by selecting your repository

## Environment Variables

For added security when deployed, you can use environment variables:
- Create a `.env` file for local development
- Add your API key to Streamlit Cloud's secrets management when deployed

## Credits

© Solstice Solutions | all rights reserved

This is a Streamlit web version of the original tkinter-based desktop application.
