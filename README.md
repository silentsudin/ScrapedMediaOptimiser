# ScrapedMediaOptimiser

ScrapedMediaOptimiser is a Python utility that optimizes media files scraped from retro gaming resources by tools like Skraper. It reduces file sizes while preserving quality to save storage space on devices with limited capacity, such as retro gaming handhelds and emulation systems. 

This is designed to be used with ES-DE Android and will move gamelist files to the location ES-DE Android expects

I wrote this script so I could optimise the space on my SD card for my Retroid Flip 2. I plan to add an AV1 encoding flag for devices using newer processors such as the SNapdragon 8 Gen 2 (For devices like the Ayn Thor and Ayn Odin 2)

## Features

- **Video Optimization**: Converts MP4 videos to MKV format using x265 encoding for significant space savings
- **Image Optimization**: Converts PNG and JPG/JPEG images to optimized WebP format while keeping original extensions
- **PDF Optimization**: Compresses PDF files using JPEG2000 and JBIG2 compression techniques
- **Smart Size Checking**: Only keeps optimized files if they're smaller than the originals
- **Preserves Directory Structure**: Maintains your organized media folders
- **Gamelist Handling**: Properly moves gamelist.xml files to expected locations
- **Progress Reporting**: Shows conversion progress with ETA for long operations

## Prerequisites

- Python 3.7+
- FFmpeg (system installation)
- Required Python packages:
  - ffmpeg-python
  - pymediainfo
  - webptools
  - PyMuPDF (fitz)
  - Pillow
  - pikepdf
  - numpy
- For best PDF optimization:
  - ocrmypdf (optional, provides JBIG2 compression support)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/SuperScraper.git
   cd SuperScraper
   ```

2. Install required Python packages:
   ```
   pip install ffmpeg-python pymediainfo webptools PyMuPDF Pillow pikepdf numpy
   ```

3. Install system dependencies:

   ### Windows

   **FFmpeg:**
   - Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) or install via [Chocolatey](https://chocolatey.org/):
     ```
     choco install ffmpeg
     ```
   - Add FFmpeg to your PATH environment variable

   **libwebp (for cwebp):**
   - Download the WebP utilities from [Google's WebP site](https://developers.google.com/speed/webp/download)
   - Extract and add the bin folder to your PATH environment variable

   **ocrmypdf (optional, for advanced PDF optimization):**
   - Install WSL (Windows Subsystem for Linux) and Ubuntu
   - Within WSL, install ocrmypdf:
     ```
     sudo apt-get install ocrmypdf
     ```

   **MediaInfo:**
   - Download MediaInfo from [mediaarea.net](https://mediaarea.net/en/MediaInfo/Download/Windows)
   - Or install via Chocolatey:
     ```
     choco install mediainfo
     ```

   ### macOS

   Using [Homebrew](https://brew.sh/):
   ```
   brew install ffmpeg libwebp mediainfo
   brew install ocrmypdf  # Optional, for advanced PDF optimization
   ```

   ### Linux

   Required packages:
   - `ffmpeg`: For video transcoding
   - `libwebp-tools` or similar: For the cwebp binary
   - `mediainfo`: For video file analysis
   - `ocrmypdf`: Optional, for advanced PDF optimization

   For Debian/Ubuntu:
   ```
   sudo apt-get install ffmpeg libwebp-tools mediainfo
   sudo apt-get install ocrmypdf  # Optional
   ```

   For other distributions, use the appropriate package manager and package names.

## Usage

The script can be configured using command-line arguments:

```
python MediaOptimiser.py [-h] [-i INPUT_DIR] [-o OUTPUT_DIR] [--skip_gamelists] [--skip_media] [--skip_video_optimization] [--skip_pdf_optimization]
```

### Arguments

- `-i, --input_dir`: Input directory containing scraped media (default: defined in script)
- `-o, --output_dir`: Output directory for optimized files (default: defined in script)
- `--skip_gamelists`: Skip processing gamelist.xml files
- `--skip_media`: Skip processing media folders
- `--skip_video_optimization`: Skip optimizing MP4 videos to MKV
- `--skip_pdf_optimization`: Skip optimizing PDF files

### Examples

Basic usage with default paths:
```
python MediaOptimiser.py
```

Specify custom input and output directories:
```
python MediaOptimiser.py -i /path/to/roms -o /path/to/output
```

Skip video optimization (faster, but less space savings):
```
python MediaOptimiser.py --skip_video_optimization
```

Only process gamelist files:
```
python MediaOptimiser.py --skip_media
```

## Output Structure

The script produces the following structure in your output directory:

```
output_dir/
├── gamelists/
│   ├── system1/
│   │   └── gamelist.xml
│   ├── system2/
│   │   └── gamelist.xml
│   └── ...
└── downloaded_media/
    ├── system1/
    │   ├── media_type1/
    │   ├── media_type2/
    │   └── ...
    ├── system2/
    │   └── ...
    └── ...
```

## Notes

- The script is designed to work with the directory structure created by tools like Skraper
- Video optimization can be time-consuming but provides significant space savings
- The script always preserves original files in their original locations
- Images maintain their original file extensions despite WebP conversion

## Troubleshooting

- If video conversion fails, ensure FFmpeg is properly installed and in your PATH
- For WebP conversion issues, verify that cwebp is installed
- For PDF optimization, install ocrmypdf for best results
