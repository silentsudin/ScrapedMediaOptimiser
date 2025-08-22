import os
import shutil
import argparse
import subprocess
from ffmpeg import FFmpeg
from pymediainfo import MediaInfo
import time  # Add this import at the top of the file
from webptools import dwebp, cwebp  # Import webptools for WebP conversion
import fitz  # PyMuPDF for PDF processing
import io
from PIL import Image
import pikepdf
import numpy as np

# Manually define input and output directories
INPUT_DIR = "/Volumes/data/retroid_sd/roms"
OUTPUT_DIR = "/Volumes/data/esde_media"


def optimize_video(source_file, dest_file):
    """
    Convert MP4 video to MKV using x265 encoding with optimized parameters.

    Args:
        source_file: Path to the source MP4 file
        dest_file: Path to the destination MKV file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if destination file already exists - skip if it does
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
            print(f"Skipping existing file: {dest_file}")
            return True

        # Validate input file first
        if not os.path.exists(source_file) or os.path.getsize(source_file) == 0:
            print(f"Invalid input file (missing or empty): {source_file}")
            return False

        # Skip hidden files (starting with ._)
        if os.path.basename(source_file).startswith("._"):
            print(f"Skipping hidden file: {source_file}")
            return False

        # Get media information using pymediainfo
        media_info = MediaInfo.parse(source_file)

        # Get total duration in seconds for progress calculation
        duration_seconds = 0
        for track in media_info.tracks:
            if track.track_type == "Video":
                if hasattr(track, "duration") and track.duration:
                    duration_seconds = (
                        float(track.duration) / 1000.0
                    )  # Convert ms to seconds
                break

        # Verify the file actually contains video streams
        has_video = False
        for track in media_info.tracks:
            if track.track_type == "Video":
                has_video = True
                break

        if not has_video:
            print(f"No video stream found in file: {source_file}")
            return False

        # Find the audio track and get its codec
        audio_codec = ""
        for track in media_info.tracks:
            if track.track_type == "Audio":
                audio_codec = track.codec.lower() if track.codec else ""
                break

        # Determine audio encoding options
        audio_options = {}
        if audio_codec == "aac":
            audio_options = {"c:a": "copy"}  # Copy audio if already AAC
        else:
            audio_options = {"c:a": "aac", "b:a": "160k"}  # Convert to AAC 160kbps

        # Configure FFmpeg for video conversion - corrected initialization
        ffmpeg = FFmpeg()

        # Add input file
        ffmpeg.option("i", source_file)

        # Add video encoding options
        ffmpeg.option("c:v", "libx265")
        ffmpeg.option("preset", "slow")
        ffmpeg.option("crf", "23")
        ffmpeg.option("x265-params", "profile=main10")
        ffmpeg.option("pix_fmt", "yuv420p10le")

        # Add audio encoding options
        for key, value in audio_options.items():
            ffmpeg.option(key, value)

        # Set output file
        ffmpeg.output(dest_file)

        # Store the start time for ETA calculation
        start_time = time.time()

        # Add progress handler to show encoding progress
        @ffmpeg.on("progress")
        def on_progress(progress):
            try:
                # Calculate percentage based on current time and total duration
                current_time_str = None
                current_time_seconds = 0

                # Extract current time from progress object
                if hasattr(progress, "time"):
                    # Handle timedelta objects directly
                    if hasattr(progress.time, "total_seconds"):
                        current_time_seconds = progress.time.total_seconds()
                    else:
                        current_time_str = str(progress.time)
                elif isinstance(progress, dict) and "time" in progress:
                    # Handle timedelta objects directly
                    if hasattr(progress["time"], "total_seconds"):
                        current_time_seconds = progress["time"].total_seconds()
                    else:
                        current_time_str = str(progress["time"])

                # If we have a string, parse it as time
                if current_time_str and current_time_seconds == 0:
                    try:
                        time_parts = current_time_str.split(":")
                        if len(time_parts) >= 3:
                            hours = int(time_parts[0])
                            minutes = int(time_parts[1])
                            seconds = float(time_parts[2])
                            current_time_seconds = hours * 3600 + minutes * 60 + seconds
                    except (ValueError, IndexError, AttributeError):
                        pass

                # Calculate percentage
                percentage = 0
                eta_str = "unknown"

                if duration_seconds > 0 and current_time_seconds > 0:
                    percentage = min(
                        100, (current_time_seconds / duration_seconds) * 100
                    )

                    # Calculate ETA (estimated time remaining)
                    if percentage > 0:
                        elapsed_time = time.time() - start_time
                        total_estimated_time = elapsed_time * 100 / percentage
                        time_remaining = total_estimated_time - elapsed_time

                        # Format the time remaining
                        if time_remaining < 60:
                            eta_str = f"{time_remaining:.0f} seconds"
                        elif time_remaining < 3600:
                            eta_str = f"{time_remaining/60:.1f} minutes"
                        else:
                            eta_str = f"{time_remaining/3600:.1f} hours"

                # Display progress with ETA
                print(
                    f"Encoding: {os.path.basename(source_file)} - {percentage:.1f}% - ETA: {eta_str}",
                    end="\r",
                )
            except Exception as progress_error:
                # Don't let progress display issues interrupt the encoding
                print(f"\nProgress display error: {progress_error}")
                print(f"Progress object type: {type(progress)}")
                if hasattr(progress, "time"):
                    print(f"Time object type: {type(progress.time)}")

        # Execute the FFmpeg command
        ffmpeg.execute()

        # Check if the destination file was created successfully
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
            # Compare file sizes and use the smaller one
            input_size = os.path.getsize(source_file)
            output_size = os.path.getsize(dest_file)

            if input_size < output_size:
                # If original file is smaller, delete the transcoded file
                os.remove(dest_file)

                # Remux the original file into MKV container without transcoding
                print(
                    f"Original file is smaller, remuxing to MKV without transcoding..."
                )

                # Create a new FFmpeg instance for remuxing
                remux_ffmpeg = FFmpeg()
                remux_ffmpeg.option("i", source_file)
                remux_ffmpeg.option("c", "copy")  # Copy all streams without transcoding
                remux_ffmpeg.output(dest_file)

                try:
                    # Execute the remux command
                    remux_ffmpeg.execute()

                    if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
                        remux_size = os.path.getsize(dest_file)
                        print(
                            f"Remuxed: {source_file} ({input_size/1024/1024:.2f}MB) -> {dest_file} ({remux_size/1024/1024:.2f}MB)"
                        )
                    else:
                        print(f"Remuxing failed, falling back to direct copy")
                        shutil.copy2(source_file, dest_file)
                        print(
                            f"Copied: {source_file} ({input_size/1024/1024:.2f}MB) -> {dest_file}"
                        )
                except Exception as remux_error:
                    print(
                        f"Error during remuxing: {remux_error}, falling back to direct copy"
                    )
                    shutil.copy2(source_file, dest_file)
                    print(
                        f"Copied: {source_file} ({input_size/1024/1024:.2f}MB) -> {dest_file}"
                    )
            else:
                # Transcoded file is smaller or equal size, keep it
                print(
                    f"Optimized: {source_file} ({input_size/1024/1024:.2f}MB) -> {dest_file} ({output_size/1024/1024:.2f}MB)"
                )

            return True
        else:
            print(
                f"Optimization seemed to complete but output file is missing or empty: {dest_file}"
            )
            return False
    except Exception as e:
        print(f"Error optimizing {source_file}: {str(e)}")
        # If a partial output file was created, remove it
        if os.path.exists(dest_file):
            try:
                os.remove(dest_file)
                print(f"Removed partial output file: {dest_file}")
            except Exception as cleanup_error:
                print(f"Failed to remove partial output file: {cleanup_error}")
        return False


def optimize_image(source_file, dest_file):
    """
    Convert PNG or JPG/JPEG to WebP format while keeping original extension.

    Args:
        source_file: Path to the source image file
        dest_file: Path to the destination file (should have original extension)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if destination file already exists - skip if it does
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
            print(f"Skipping existing file: {dest_file}")
            return True

        # Validate input file first
        if not os.path.exists(source_file) or os.path.getsize(source_file) == 0:
            print(f"Invalid input file (missing or empty): {source_file}")
            return False

        # Skip hidden files
        if os.path.basename(source_file).startswith("._"):
            print(f"Skipping hidden file: {source_file}")
            return False

        # Get file extension
        _, ext = os.path.splitext(source_file)
        ext = ext.lower()

        # Convert to WebP
        if ext in [".png", ".jpg", ".jpeg"]:
            # Check if the filename has spaces or special characters
            has_special_chars = (
                " " in source_file or "(" in source_file or ")" in source_file
            )

            # Create a temporary directory for processing
            temp_dir = os.path.join(os.path.dirname(dest_file), ".tmp_webp_conversion")
            os.makedirs(temp_dir, exist_ok=True)

            # Create temporary filenames without spaces - using a different naming strategy for special chars
            if has_special_chars:
                print(
                    f"File has spaces or special characters, using special handling: {source_file}"
                )
                # Create sanitized temp filenames that avoid special characters
                temp_input = os.path.join(
                    temp_dir, f"input_{int(time.time())}_{os.urandom(4).hex()}{ext}"
                )
                temp_output = os.path.join(
                    temp_dir, f"output_{int(time.time())}_{os.urandom(4).hex()}.webp"
                )
                temp_final = os.path.join(
                    temp_dir, f"final_{int(time.time())}_{os.urandom(4).hex()}{ext}"
                )
            else:
                # Standard temp filenames for regular files
                temp_input = os.path.join(
                    temp_dir, f"input_{int(time.time())}_{os.urandom(4).hex()}{ext}"
                )
                temp_output = os.path.join(
                    temp_dir, f"output_{int(time.time())}_{os.urandom(4).hex()}.webp"
                )
                temp_final = None  # Not needed for regular files

            try:
                # Copy the source file to our temp location
                shutil.copy2(source_file, temp_input)
                print(f"Converting {source_file} to WebP...")

                conversion_success = False

                # Different conversion approaches based on whether we have special characters
                if has_special_chars:
                    try:
                        # Try using direct subprocess for files with special characters
                        print("Using subprocess for file with special characters...")

                        # First check if cwebp is available
                        which_result = subprocess.run(
                            ["which", "cwebp"], capture_output=True, text=True
                        )

                        if which_result.returncode == 0:
                            cwebp_path = which_result.stdout.strip()
                            print(f"Found cwebp at: {cwebp_path}")

                            # Use subprocess with properly quoted filenames
                            subprocess_result = subprocess.run(
                                [cwebp_path, "-q", "80", temp_input, "-o", temp_output],
                                capture_output=True,
                                text=True,
                            )

                            if subprocess_result.returncode == 0:
                                print("Direct subprocess conversion successful")
                                conversion_success = True
                            else:
                                print(
                                    f"Direct subprocess conversion failed: {subprocess_result.stderr}"
                                )
                        else:
                            print(
                                "cwebp not found in PATH, falling back to pillow conversion"
                            )

                            # If cwebp is not available, try using Pillow for conversion
                            try:
                                from PIL import Image

                                img = Image.open(temp_input)
                                img.save(temp_output, "WEBP", quality=80)
                                conversion_success = True
                                print("Pillow conversion successful")
                            except ImportError:
                                print("Pillow not available")
                            except Exception as pillow_error:
                                print(f"Pillow conversion error: {str(pillow_error)}")
                    except Exception as special_error:
                        print(
                            f"Special handling conversion error: {str(special_error)}"
                        )
                else:
                    # Standard conversion using webptools
                    try:
                        # Use quality 80 - good balance between size and quality
                        exit_code = cwebp(
                            input_image=temp_input,
                            output_image=temp_output,
                            option="-q 80",
                        )

                        if isinstance(exit_code, dict) and "exit_code" in exit_code:
                            exit_code = exit_code["exit_code"]

                        # Print more detailed debug info
                        print(f"WebP conversion exit code: {exit_code}")

                        if exit_code == 0:
                            conversion_success = True
                        else:
                            print(
                                f"WebP conversion failed for {source_file}, exit code: {exit_code}"
                            )

                            # Try direct conversion with subprocess as fallback
                            try:
                                print("Trying fallback conversion with subprocess...")
                                # Check if cwebp command exists
                                which_result = subprocess.run(
                                    ["which", "cwebp"], capture_output=True, text=True
                                )
                                if which_result.returncode == 0:
                                    cwebp_path = which_result.stdout.strip()
                                    print(f"Found cwebp at: {cwebp_path}")

                                    # Use subprocess directly
                                    subprocess_result = subprocess.run(
                                        [
                                            cwebp_path,
                                            "-q",
                                            "80",
                                            temp_input,
                                            "-o",
                                            temp_output,
                                        ],
                                        capture_output=True,
                                        text=True,
                                    )

                                    if subprocess_result.returncode == 0:
                                        print("Fallback conversion successful!")
                                        conversion_success = True
                                    else:
                                        print(
                                            f"Fallback conversion failed: {subprocess_result.stderr}"
                                        )
                                else:
                                    print("cwebp command not found in PATH")
                            except Exception as fallback_error:
                                print(
                                    f"Fallback conversion error: {str(fallback_error)}"
                                )
                    except Exception as webp_error:
                        print(f"WebP conversion error: {str(webp_error)}")

                # If conversion was successful, check the output
                if (
                    conversion_success
                    and os.path.exists(temp_output)
                    and os.path.getsize(temp_output) > 0
                ):
                    # Compare file sizes
                    input_size = os.path.getsize(source_file)
                    webp_size = os.path.getsize(temp_output)

                    if input_size < webp_size:
                        # Original is smaller, use it
                        shutil.copy2(source_file, dest_file)
                        print(
                            f"Original file is smaller, copied: {source_file} ({input_size/1024:.2f}KB) -> {dest_file}"
                        )
                    else:
                        # WebP is smaller, copy it to the destination
                        shutil.copy2(temp_output, dest_file)
                        print(
                            f"Optimized: {source_file} ({input_size/1024:.2f}KB) -> {dest_file} ({webp_size/1024:.2f}KB)"
                        )
                    return True
                else:
                    # If conversion failed, fall back to direct copy
                    print(
                        f"Conversion failed, falling back to direct copy for: {source_file}"
                    )
                    shutil.copy2(source_file, dest_file)
                    print(f"Copied: {source_file} -> {dest_file}")
                    return True
            finally:
                # Clean up temporary files
                if os.path.exists(temp_input):
                    os.remove(temp_input)
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                if temp_final and os.path.exists(temp_final):
                    os.remove(temp_final)
                try:
                    os.rmdir(temp_dir)  # Remove temp dir if empty
                except:
                    pass  # It's ok if we can't remove it
        else:
            # For unsupported formats, just copy
            shutil.copy2(source_file, dest_file)
            print(f"Copied (unsupported format): {source_file} -> {dest_file}")
            return True

    except Exception as e:
        print(f"Error optimizing image {source_file}: {str(e)}")
        # If a partial output file was created, remove it
        if os.path.exists(dest_file):
            try:
                os.remove(dest_file)
            except:
                pass
        return False


def optimize_pdf(source_file, dest_file):
    """
    Optimize PDF file by converting:
    - Color images to JPEG2000 format
    - Monochrome images to JBIG2 format

    Args:
        source_file: Path to the source PDF file
        dest_file: Path to the destination PDF file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if destination file already exists - skip if it does
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
            print(f"Skipping existing PDF file: {dest_file}")
            return True

        # Validate input file first
        if not os.path.exists(source_file) or os.path.getsize(source_file) == 0:
            print(f"Invalid PDF file (missing or empty): {source_file}")
            return False

        # Skip hidden files
        if os.path.basename(source_file).startswith("._"):
            print(f"Skipping hidden PDF file: {source_file}")
            return False

        # Get input file size immediately and display it
        input_size = os.path.getsize(source_file)
        print(
            f"Processing PDF: {source_file} (Size: {input_size/1024:.2f}KB / {input_size/1024/1024:.2f}MB)"
        )

        # Create temporary directory for processing
        temp_dir = os.path.join(
            os.path.dirname(dest_file), f".tmp_pdf_conversion_{int(time.time())}"
        )
        os.makedirs(temp_dir, exist_ok=True)

        # Temporary optimization file
        temp_pdf = os.path.join(temp_dir, "optimized.pdf")

        try:
            # Check if ocrmypdf is installed (needed for JBIG2)
            has_ocrmypdf = False
            try:
                subprocess.run(
                    ["ocrmypdf", "--version"], capture_output=True, check=False
                )
                has_ocrmypdf = True
            except (FileNotFoundError, subprocess.SubprocessError):
                print("ocrmypdf not found, JBIG2 compression may not be available")

            print(f"Optimizing PDF: {source_file}")

            # Method 1: Use ocrmypdf if available (it has JBIG2 and image optimization)
            if has_ocrmypdf:
                print("Using ocrmypdf for optimization with JBIG2/JPEG2000 support")
                # --redo-ocr: Re-run OCR on any text (ensures we can reprocess PDFs)
                # --optimize 3: Maximum optimization level
                # --jbig2-lossy: Enable lossy JBIG2 for monochrome images
                # --jpeg-quality 75: Good balance for JPEG quality
                result = subprocess.run(
                    [
                        "ocrmypdf",
                        "--optimize",
                        "3",
                        "--skip-text",  # Skip OCR if already has text
                        "--jbig2-lossy",
                        "--jpeg-quality",
                        "75",
                        "--output-type",
                        "pdf",
                        "--quiet",
                        source_file,
                        temp_pdf,
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    # Handle case where optimization failed but PDF might be image-only
                    print(f"Standard optimization failed: {result.stderr}")
                    print("Trying with force-ocr option...")

                    result = subprocess.run(
                        [
                            "ocrmypdf",
                            "--optimize",
                            "3",
                            "--force-ocr",
                            "--jbig2-lossy",
                            "--jpeg-quality",
                            "75",
                            "--output-type",
                            "pdf",
                            "--quiet",
                            source_file,
                            temp_pdf,
                        ],
                        capture_output=True,
                        text=True,
                    )

                optimization_success = result.returncode == 0

            # Method 2: Fallback to pikepdf and manual processing
            else:
                # Open the PDF with PyMuPDF (fitz) for analyzing images
                pdf_doc = fitz.open(source_file)
                needs_optimization = False

                # Scan PDF to see if it has images that need optimization
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc[page_num]
                    image_list = page.get_images(full=True)

                    for img_index, img_info in enumerate(image_list):
                        xref = img_info[0]
                        base_image = pdf_doc.extract_image(xref)
                        image_bytes = base_image["image"]

                        # Check image compression type
                        img_type = base_image["colorspace"]
                        compression = base_image.get("cs-name", "")

                        # If not already JPEG2000 or JBIG2, mark for optimization
                        if "JP2" not in compression and "JBIG2" not in compression:
                            needs_optimization = True
                            break

                    if needs_optimization:
                        break

                if not needs_optimization:
                    print(f"PDF already uses optimal compression: {source_file}")
                    shutil.copy2(source_file, dest_file)
                    return True

                # Use pikepdf for optimization
                with pikepdf.open(source_file) as pdf:
                    # Save with optimization settings
                    pdf.save(
                        temp_pdf,
                        compress_streams=True,
                        object_streams="generate",
                        linearize=False,
                    )

                optimization_success = (
                    os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0
                )

            # Compare file sizes and determine which to keep
            if optimization_success:
                output_size = os.path.getsize(temp_pdf)
                size_diff = input_size - output_size
                reduction_percent = (
                    (size_diff / input_size) * 100 if input_size > 0 else 0
                )

                print(
                    f"Input size: {input_size/1024:.2f}KB / {input_size/1024/1024:.2f}MB"
                )
                print(
                    f"Output size: {output_size/1024:.2f}KB / {output_size/1024/1024:.2f}MB"
                )

                if size_diff > 0:
                    print(
                        f"Size reduction: {size_diff/1024:.2f}KB ({reduction_percent:.1f}%)"
                    )
                else:
                    print(
                        f"Size increase: {-size_diff/1024:.2f}KB ({-reduction_percent:.1f}%)"
                    )

                if input_size < output_size:
                    # Original is smaller, use it
                    print(f"Original PDF is smaller, copying original")
                    shutil.copy2(source_file, dest_file)
                else:
                    # Optimized is smaller, use it
                    print(f"Using optimized PDF (smaller than original)")
                    shutil.copy2(temp_pdf, dest_file)

                return True
            else:
                print(
                    f"PDF optimization failed, falling back to direct copy: {source_file}"
                )
                shutil.copy2(source_file, dest_file)
                # Display size information even for direct copies
                output_size = os.path.getsize(dest_file)
                print(
                    f"Copied without optimization: {input_size/1024:.2f}KB -> {output_size/1024:.2f}KB"
                )
                return True

        finally:
            # Clean up temporary files with timeouts and better error handling
            try:
                # First try to remove the temporary PDF file if it exists
                if os.path.exists(temp_pdf):
                    try:
                        os.remove(temp_pdf)
                        print(f"Removed temporary PDF: {temp_pdf}")
                    except (PermissionError, OSError) as cleanup_error:
                        print(
                            f"Failed to remove temporary PDF {temp_pdf}: {cleanup_error}"
                        )
                        # Try to make the file writable in case it's read-only
                        try:
                            os.chmod(temp_pdf, 0o666)
                            os.remove(temp_pdf)
                            print(f"Removed temporary PDF after chmod: {temp_pdf}")
                        except Exception as e:
                            print(f"Still failed to remove temporary PDF: {e}")

                # Then try to remove the temporary directory
                if os.path.exists(temp_dir):
                    try:
                        # First check if directory is empty
                        files_in_dir = os.listdir(temp_dir)
                        if not files_in_dir:
                            os.rmdir(temp_dir)
                            print(f"Removed temporary directory: {temp_dir}")
                        else:
                            # If directory is not empty, try to remove all files first
                            print(
                                f"Temporary directory not empty, trying to clean up: {temp_dir}"
                            )
                            for filename in files_in_dir:
                                file_path = os.path.join(temp_dir, filename)
                                try:
                                    if os.path.isfile(file_path) or os.path.islink(
                                        file_path
                                    ):
                                        os.unlink(file_path)
                                    elif os.path.isdir(file_path):
                                        shutil.rmtree(file_path)
                                except Exception as e:
                                    print(f"Failed to delete {file_path}: {e}")

                            # Try again to remove the directory
                            if not os.listdir(temp_dir):
                                os.rmdir(temp_dir)
                                print(
                                    f"Removed temporary directory after cleanup: {temp_dir}"
                                )
                            else:
                                print(
                                    f"Could not fully clean temporary directory: {temp_dir}"
                                )
                    except Exception as dir_error:
                        print(f"Failed to remove temporary directory: {dir_error}")
                        # Don't let this stop the process
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
                # Continue with execution regardless of cleanup errors

    except Exception as e:
        print(f"Error optimizing PDF {source_file}: {str(e)}")
        traceback.print_exc()  # Add this to get full error trace
        # If a partial output file was created, remove it
        if os.path.exists(dest_file):
            try:
                os.remove(dest_file)
                print(f"Removed partial output file: {dest_file}")
            except Exception as cleanup_error:
                print(f"Failed to remove partial output file: {cleanup_error}")
        return False


def move_gamelists(input_dir, output_dir):
    """
    Recursively scan through input_dir for gamelist.xml files and move them to
    output_dir/gamelists/ while maintaining the original folder structure.
    """
    # Create the gamelists directory in the output folder if it doesn't exist
    gamelists_dir = os.path.join(output_dir, "gamelists")
    if not os.path.exists(gamelists_dir):
        os.makedirs(gamelists_dir)

    # Count for reporting
    files_moved = 0
    files_skipped = 0

    # Walk through the directory tree
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file == "gamelist.xml":
                # Get the source file path
                source_file = os.path.join(root, file)

                # Calculate the relative path from input_dir
                rel_path = os.path.relpath(root, input_dir)

                # Create the destination directory
                dest_dir = os.path.join(gamelists_dir, rel_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)

                # Set the destination file path
                dest_file = os.path.join(dest_dir, file)

                # Check if the file already exists in destination
                if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
                    print(f"Skipping existing gamelist: {dest_file}")
                    files_skipped += 1
                    continue

                # Move the file
                shutil.copy2(source_file, dest_file)
                print(f"Moved: {source_file} -> {dest_file}")
                files_moved += 1

    print(f"Total gamelist.xml files moved: {files_moved}")
    print(f"Total gamelist.xml files skipped: {files_skipped}")


def copy_media_folders(input_dir, output_dir, optimize_videos=True):
    """
    Recursively scan through input_dir for 'media' folders and copy their contents to
    output_dir/downloaded_media/{parent_folder_name}/ structure.
    Optimize MP4 videos by converting to MKV with x265 encoding if optimize_videos is True.
    Optimize PNG and JPG images by converting to WebP format.
    """
    # Create the downloaded_media directory in the output folder if it doesn't exist
    downloaded_media_dir = os.path.join(output_dir, "downloaded_media")
    if not os.path.exists(downloaded_media_dir):
        os.makedirs(downloaded_media_dir)

    # Count for reporting
    media_folders_processed = 0
    files_copied = 0
    files_skipped = 0
    videos_optimized = 0
    images_optimized = 0

    # Walk through the directory tree
    for root, dirs, _ in os.walk(input_dir):
        for dir_name in dirs:
            if dir_name == "media":
                # Get full path to the media directory
                media_dir_path = os.path.join(root, dir_name)

                # Get the parent folder name (e.g., "megadrive")
                parent_folder = os.path.basename(root)

                # Create destination directory for this system
                dest_system_dir = os.path.join(downloaded_media_dir, parent_folder)
                if not os.path.exists(dest_system_dir):
                    os.makedirs(dest_system_dir)

                # For each subfolder in the media directory, process it
                for item in os.listdir(media_dir_path):
                    item_path = os.path.join(media_dir_path, item)

                    # Only process directories (we want to copy each folder in media/)
                    if os.path.isdir(item_path):
                        dest_item_path = os.path.join(dest_system_dir, item)

                        # Create the base destination directory if it doesn't exist
                        if not os.path.exists(dest_item_path):
                            os.makedirs(dest_item_path)

                        # Walk through all files in the directory
                        for file_root, _, files in os.walk(item_path):
                            # Get the relative path from item_path
                            rel_path = os.path.relpath(file_root, item_path)
                            dest_file_dir = os.path.join(dest_item_path, rel_path)

                            # Create destination directory if it doesn't exist
                            if rel_path != "." and not os.path.exists(dest_file_dir):
                                os.makedirs(dest_file_dir)

                            # Process each file
                            for file in files:
                                # Skip macOS hidden files at the outset
                                if file.startswith("._"):
                                    print(
                                        f"Skipping macOS hidden file: {file} (completely bypassing all processing)"
                                    )
                                    files_skipped += 1
                                    continue  # This should skip to the next file without further processing

                                # Get full path to source file
                                src_file_path = os.path.join(file_root, file)

                                # Double-check that we're not processing a hidden file (defensive check)
                                if os.path.basename(src_file_path).startswith("._"):
                                    print(
                                        f"Secondary hidden file check caught: {src_file_path}"
                                    )
                                    files_skipped += 1
                                    continue

                                file_lower = file.lower()

                                # Check if it's a video file to optimize
                                if optimize_videos and file_lower.endswith(".mp4"):
                                    # Change extension to .mkv for optimized files
                                    dest_file_name = os.path.splitext(file)[0] + ".mkv"
                                    dest_file_path = os.path.join(
                                        dest_file_dir, dest_file_name
                                    )

                                    # Check if destination already exists
                                    if (
                                        os.path.exists(dest_file_path)
                                        and os.path.getsize(dest_file_path) > 0
                                    ):
                                        print(
                                            f"Skipping existing video: {dest_file_path}"
                                        )
                                        files_skipped += 1
                                        continue

                                    # Optimize and convert the video
                                    if optimize_video(src_file_path, dest_file_path):
                                        videos_optimized += 1
                                        files_copied += 1
                                # Check if it's a PDF file to optimize
                                elif file_lower.endswith(".pdf"):
                                    dest_file_path = os.path.join(dest_file_dir, file)

                                    # Check if destination already exists
                                    if (
                                        os.path.exists(dest_file_path)
                                        and os.path.getsize(dest_file_path) > 0
                                    ):
                                        print(
                                            f"Skipping existing PDF: {dest_file_path}"
                                        )
                                        files_skipped += 1
                                        continue

                                    # Optimize PDF file
                                    if optimize_pdf(src_file_path, dest_file_path):
                                        files_copied += 1
                                        print(
                                            f"PDF processed: {src_file_path} -> {dest_file_path}"
                                        )
                                # Check if it's an image file to optimize
                                elif file_lower.endswith((".png", ".jpg", ".jpeg")):
                                    dest_file_path = os.path.join(dest_file_dir, file)

                                    # Check if destination already exists
                                    if (
                                        os.path.exists(dest_file_path)
                                        and os.path.getsize(dest_file_path) > 0
                                    ):
                                        print(
                                            f"Skipping existing image: {dest_file_path}"
                                        )
                                        files_skipped += 1
                                        continue

                                    # Optimize and convert the image
                                    if optimize_image(src_file_path, dest_file_path):
                                        images_optimized += 1
                                        files_copied += 1
                                else:
                                    # Regular file copy
                                    dest_file_path = os.path.join(dest_file_dir, file)

                                    # Check if destination already exists
                                    if (
                                        os.path.exists(dest_file_path)
                                        and os.path.getsize(dest_file_path) > 0
                                    ):
                                        print(
                                            f"Skipping existing file: {dest_file_path}"
                                        )
                                        files_skipped += 1
                                        continue

                                    shutil.copy2(src_file_path, dest_file_path)
                                    files_copied += 1
                                    print(
                                        f"Copied: {src_file_path} -> {dest_file_path}"
                                    )

                media_folders_processed += 1

    print(f"Total media folders processed: {media_folders_processed}")
    print(f"Total files copied: {files_copied}")
    print(f"Total files skipped (already exist): {files_skipped}")
    if optimize_videos:
        print(f"Total videos optimized: {videos_optimized}")
    print(f"Total images optimized: {images_optimized}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process gamelist.xml files and media folders"
    )
    parser.add_argument(
        "-i",
        "--input_dir",
        default=INPUT_DIR,
        help="Input directory to scan recursively",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        default=OUTPUT_DIR,
        help="Output directory where processed files will be stored",
    )
    parser.add_argument(
        "--skip_gamelists",
        action="store_true",
        help="Skip processing gamelist.xml files",
    )
    parser.add_argument(
        "--skip_media",
        action="store_true",
        help="Skip processing media folders",
    )
    parser.add_argument(
        "--skip_video_optimization",
        action="store_true",
        help="Skip optimizing MP4 videos to MKV with x265 encoding",
    )
    parser.add_argument(
        "--skip_pdf_optimization",
        action="store_true",
        help="Skip optimizing PDF files with JPEG2000/JBIG2 compression",
    )

    args = parser.parse_args()

    # Validate directories
    if not os.path.isdir(args.input_dir):
        print(
            f"Error: Input directory '{args.input_dir}' does not exist or is not a directory"
        )
        exit(1)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if not args.skip_gamelists:
        move_gamelists(args.input_dir, args.output_dir)

    if not args.skip_media:
        copy_media_folders(
            args.input_dir, args.output_dir, not args.skip_video_optimization
        )
