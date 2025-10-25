import os
import uuid
import subprocess
from flask import Flask, request, send_file
from io import BytesIO

# Initialize Flask App
app = Flask(__name__)

# Directory for temporary file storage
TEMP_DIR = '/tmp'
os.makedirs(TEMP_DIR, exist_ok=True)

@app.route('/compress', methods=['POST'])
def compress_audio():
    """
    Handles file upload, compresses audio using FFmpeg, and returns the compressed file.
    The primary goal is to reduce file size below 25MB for the Groq Whisper API.
    """
    if 'file' not in request.files:
        return {"error": "No file part in the request"}, 400

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return {"error": "No selected file"}, 400

    # 1. Save the incoming file to a temporary location
    unique_id = uuid.uuid4()
    
    # Use the original content type for the input file extension (e.g., .mp4, .ogg)
    content_type = uploaded_file.content_type 
    input_ext = os.path.splitext(uploaded_file.filename)[1] or '.mp4' 
    if not input_ext:
        # Fallback for Blobs without explicit filename/extension
        input_ext = '.' + content_type.split('/')[-1] if '/' in content_type else '.mp4'

    input_path = os.path.join(TEMP_DIR, f'input_{unique_id}{input_ext}')
    output_path = os.path.join(TEMP_DIR, f'output_{unique_id}.mp3')

    try:
        # Save the file stream to disk
        uploaded_file.save(input_path)
        app.logger.info(f"Saved file to {input_path}")
        
        # 2. Execute FFmpeg Command for Audio Downscaling
        # Command: -i (input) 
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
        process = subprocess.run(command, 
                                 capture_output=True, 
                                 text=True,
                                 check=False) # check=False allows us to handle errors manually

        if process.returncode != 0:
            app.logger.error(f"FFmpeg Error: {process.stderr}")
            return {"error": "FFmpeg compression failed", "details": process.stderr}, 500

        # 3. Read the compressed file back into memory and serve it
        app.logger.info(f"FFmpeg compression successful. Output file: {output_path}")
        
        return send_file(output_path, 
                         mimetype='audio/mpeg', 
                         as_attachment=True,
                         download_name='compressed_audio.mp3')

    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return {"error": "Internal server error during processing"}, 500

    finally:
        # 4. Clean up temporary files
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.remove(path)
                app.logger.info(f"Cleaned up {path}")

# Note: Render provides the PORT environment variable, which Gunicorn will use.
# if __name__ == '__main__':
#     app.run(debug=True, port=8080)

