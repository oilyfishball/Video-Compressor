import os
import uuid
import subprocess
import logging
from flask import Flask, request, send_file, jsonify

# --- Configuration and Initialization ---

# Initialize Flask App
app = Flask(__name__)

# Configure logging for better debugging and error visibility
logging.basicConfig(level=logging.INFO)

# Directory for temporary file storage
TEMP_DIR = '/tmp'
os.makedirs(TEMP_DIR, exist_ok=True)

# SECURITY/RELIABILITY: Limit the maximum file size for uploads to 100MB 
# to prevent resource exhaustion (DoS attack)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 


@app.route('/compress', methods=['POST'])
def compress_audio():
    """
    Handles file upload, compresses audio using FFmpeg, and returns the compressed file.
    The primary goal is to reduce file size below 25MB for the Groq Whisper API.
    """
    
    # Initialize paths to None for safe cleanup in the finally block
    input_path = None
    output_path = None

    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400

        uploaded_file = request.files['file']
        if uploaded_file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # 1. Save the incoming file to a temporary location
        unique_id = uuid.uuid4()
        
        # SECURITY FIX: Do not use the user-provided filename extension.
        # Instead, force a generic, non-executable, temporary extension (.bin)
        # FFmpeg is robust enough to detect the actual format from the file contents.
        input_path = os.path.join(TEMP_DIR, f'input_{unique_id}.bin')
        output_path = os.path.join(TEMP_DIR, f'output_{unique_id}.mp3')

        # Save the file stream to disk
        uploaded_file.save(input_path)
        app.logger.info(f"Saved file to {input_path}")
        
        # 2. Execute FFmpeg Command for Audio Downscaling
        # Command: 
        # -i (input) 
        # -vn (no video) 
        # -c:a libmp3lame (codec for MP3) 
        # -b:a 64k (target bitrate: 64kbps, significantly reduces size)
        command = [
            'ffmpeg', 
            '-i', input_path, 
            '-vn', # Strip video track if present
            '-c:a', 'libmp3lame', 
            '-b:a', '64k', # Downscale to 64 kbps (standard for voice/podcasts)
            '-y', # Overwrite output file if it exists
            output_path
        ]
        
        # Run the FFmpeg process
        # RELIABILITY FIX: Added 'timeout=180' to prevent indefinite execution 
        # on corrupted or overly long files.
        process = subprocess.run(command, 
                                 capture_output=True, 
                                 text=True,
                                 check=False,
                                 timeout=180) 

        if process.returncode != 0:
            app.logger.error(f"FFmpeg Error: {process.stderr}")
            return jsonify({"error": "FFmpeg compression failed", "details": process.stderr}), 500

        # 3. Read the compressed file back into memory and serve it
        app.logger.info(f"FFmpeg compression successful. Output file: {output_path}")
        
        return send_file(output_path, 
                         mimetype='audio/mpeg', 
                         as_attachment=True,
                         download_name='compressed_audio.mp3')

    except TimeoutError:
        app.logger.error("FFmpeg process timed out after 180 seconds.")
        return jsonify({"error": "Processing took too long and was aborted."}), 504
    
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "Internal server error during processing"}), 500

    finally:
        # 4. Clean up temporary files
        # RELIABILITY FIX: Check if paths were successfully assigned before cleanup
        for path in [input_path, output_path]:
            if path and os.path.exists(path):
                os.remove(path)
                app.logger.info(f"Cleaned up {path}")

# Run Block for Local Development
if __name__ == '__main__':
    # Correctly reads the PORT environment variable set by hosting services (like Render)
    # or defaults to 5000 for local development.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)