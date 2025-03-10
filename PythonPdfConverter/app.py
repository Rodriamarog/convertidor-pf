import os
import uuid
import threading
from flask import Flask, request, render_template, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
import pdf_converter

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Create necessary folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# Track conversion jobs
conversion_jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def process_pdf(job_id, input_path):
    """Process PDF in a separate thread and update job status"""
    try:
        # Set up job status
        conversion_jobs[job_id]['status'] = 'processing'
        
        # Define output path
        output_filename = f"{job_id}.pdf"
        output_path = os.path.join(app.config['RESULT_FOLDER'], output_filename)
        
        # Redirect stdout to capture progress messages
        import io
        import sys
        original_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Call the PDF converter
            pdf_converter.main(input_path)
            
            # Move the output.pdf to our result folder with the job ID
            if os.path.exists('output.pdf'):
                os.rename('output.pdf', output_path)
                conversion_jobs[job_id]['output_path'] = output_path
                conversion_jobs[job_id]['status'] = 'completed'
            else:
                conversion_jobs[job_id]['status'] = 'failed'
                conversion_jobs[job_id]['error'] = 'Conversion failed to produce output file'
        except Exception as e:
            conversion_jobs[job_id]['status'] = 'failed'
            conversion_jobs[job_id]['error'] = str(e)
        finally:
            # Restore stdout and capture the output
            sys.stdout = original_stdout
            conversion_jobs[job_id]['log'] = captured_output.getvalue()
            
        # Clean up the input file
        try:
            os.remove(input_path)
        except:
            pass
            
    except Exception as e:
        conversion_jobs[job_id]['status'] = 'failed'
        conversion_jobs[job_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def convert_pdf():
    # Check if file is in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    
    # Check if a file was selected
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    # Check if the file is a PDF
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Save the uploaded file
    filename = secure_filename(file.filename)
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
    file.save(input_path)
    
    # Initialize job status
    conversion_jobs[job_id] = {
        'status': 'queued',
        'original_filename': filename,
        'input_path': input_path,
        'output_path': None,
        'error': None,
        'log': None
    }
    
    # Start processing in a separate thread
    thread = threading.Thread(target=process_pdf, args=(job_id, input_path))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'status': 'queued',
        'status_url': url_for('job_status', job_id=job_id, _external=True)
    })

@app.route('/api/status/<job_id>', methods=['GET'])
def job_status(job_id):
    if job_id not in conversion_jobs:
        return jsonify({'error': 'Job not found'}), 404
        
    job = conversion_jobs[job_id]
    response = {
        'job_id': job_id,
        'status': job['status'],
        'original_filename': job['original_filename']
    }
    
    if job['status'] == 'completed':
        response['download_url'] = url_for('download_file', job_id=job_id, _external=True)
    elif job['status'] == 'failed':
        response['error'] = job['error']
    
    # Include log for detailed progress
    if job['log']:
        response['log'] = job['log']
        
    return jsonify(response)

@app.route('/api/download/<job_id>', methods=['GET'])
def download_file(job_id):
    if job_id not in conversion_jobs:
        return jsonify({'error': 'Job not found'}), 404
        
    job = conversion_jobs[job_id]
    
    if job['status'] != 'completed' or not job['output_path'] or not os.path.exists(job['output_path']):
        return jsonify({'error': 'File not available'}), 404
        
    # Generate a more user-friendly filename
    original_name = os.path.splitext(job['original_filename'])[0]
    download_name = f"{original_name}_converted.pdf"
    
    return send_file(
        job['output_path'],
        as_attachment=True,
        download_name=download_name,
        mimetype='application/pdf'
    )

@app.route('/api/docs')
def api_docs():
    return render_template('api_docs.html')

# Clean up old jobs periodically (in a production app, you'd use a task scheduler)
@app.before_request
def cleanup_old_jobs():
    # This is a simple implementation - in production, use a proper task scheduler
    import time
    current_time = time.time()
    
    # Remove jobs and files older than 1 hour
    jobs_to_remove = []
    for job_id, job in conversion_jobs.items():
        # Check if job is completed or failed and older than 1 hour
        if job.get('created_at', current_time) < current_time - 3600:
            # Remove output file if it exists
            if job.get('output_path') and os.path.exists(job['output_path']):
                try:
                    os.remove(job['output_path'])
                except:
                    pass
            jobs_to_remove.append(job_id)
    
    # Remove the jobs from the dictionary
    for job_id in jobs_to_remove:
        conversion_jobs.pop(job_id, None)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 