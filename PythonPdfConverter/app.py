import os
import uuid
import threading
import json
import time
from flask import Flask, request, render_template, jsonify, send_file, url_for, send_from_directory
from werkzeug.utils import secure_filename
import pdf_converter
# from apscheduler.schedulers.background import BackgroundScheduler
import sys
import subprocess

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
app.config['JOBS_FOLDER'] = 'jobs'  # Nuevo directorio para almacenar información de trabajos
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Track conversion jobs (in-memory cache, backed by files)
conversion_jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_job_info(job_id, job_info):
    """Save job information to a file"""
    job_file = os.path.join(app.config['JOBS_FOLDER'], f"{job_id}.json")
    with open(job_file, 'w') as f:
        # Convert any non-serializable objects to strings
        job_info_copy = job_info.copy()
        for key, value in job_info_copy.items():
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                job_info_copy[key] = str(value)
        json.dump(job_info_copy, f)
    
    # Update in-memory cache
    conversion_jobs[job_id] = job_info

def get_job_info(job_id):
    """Get job information from file or memory"""
    # Check in-memory cache first
    if job_id in conversion_jobs:
        return conversion_jobs[job_id]
    
    # Try to load from file
    job_file = os.path.join(app.config['JOBS_FOLDER'], f"{job_id}.json")
    if os.path.exists(job_file):
        try:
            with open(job_file, 'r') as f:
                job_info = json.load(f)
                conversion_jobs[job_id] = job_info
                return job_info
        except Exception as e:
            print(f"Error loading job info: {e}")
    
    return None

def check_dependencies():
    """Check if all required dependencies are installed"""
    missing = []
    available = []
    
    # Check for Python packages
    try:
        import PyPDF2
        available.append("PyPDF2")
    except ImportError:
        missing.append("PyPDF2")
    
    try:
        import pdfplumber
        available.append("pdfplumber")
    except ImportError:
        missing.append("pdfplumber")
    
    try:
        import fitz  # PyMuPDF
        available.append("PyMuPDF (fitz)")
    except ImportError:
        missing.append("PyMuPDF (fitz)")
    
    try:
        from PIL import Image
        available.append("Pillow")
    except ImportError:
        missing.append("Pillow")
    
    # Check for command-line tools
    tools = ["gs", "pdftk", "qpdf", "pdftoppm", "pdfinfo", "pdfimages"]
    for tool in tools:
        try:
            # Use 'where' on Windows, 'which' on Unix
            if sys.platform.startswith('win'):
                subprocess.run(["where", tool], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            else:
                subprocess.run(["which", tool], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            available.append(tool)
        except subprocess.CalledProcessError:
            missing.append(tool)
    
    if missing:
        print("WARNING: Missing dependencies:")
        print(f"  Python packages: {[pkg for pkg in missing if pkg in ['PyPDF2', 'pdfplumber', 'PyMuPDF (fitz)', 'Pillow']]}")
        print(f"  Command-line tools: {[tool for tool in missing if tool in tools]}")
        print("\nSome features may not work correctly. Please install missing dependencies.")
        
        # Check if we have the minimum required dependencies
        min_required = ["PyPDF2", "PyMuPDF (fitz)"]
        missing_required = [pkg for pkg in min_required if pkg not in available]
        
        if missing_required:
            print("\nCRITICAL: Missing required Python packages:")
            print(f"  {missing_required}")
            print("The application may not function correctly without these packages.")
            print("Please install them with: pip install PyPDF2 PyMuPDF")
        else:
            print("\nGood news: You have the minimum required Python packages installed.")
            print("The application will use pure Python methods for PDF conversion.")
            print("For better quality and performance, consider installing the missing tools.")
        
        return False
    
    print("All dependencies are available. The application will use optimal conversion methods.")
    return True

def process_pdf(job_id, input_path):
    """Process PDF in a separate thread and update job status"""
    try:
        # Get job info
        job_info = get_job_info(job_id)
        if not job_info:
            print(f"Job info not found for job_id: {job_id}")
            return
        
        # Update status
        job_info['status'] = 'processing'
        save_job_info(job_id, job_info)
        
        # Define output path
        output_filename = f"{job_id}.pdf"
        output_path = os.path.join(app.config['RESULT_FOLDER'], output_filename)
        print(f"Output will be saved to: {output_path}")
        
        # Verify input file exists
        if not os.path.exists(input_path):
            print(f"ERROR: Input file does not exist: {input_path}")
            job_info['status'] = 'failed'
            job_info['error'] = f"Input file not found: {input_path}"
            save_job_info(job_id, job_info)
            return
            
        # Redirect stdout to capture progress messages
        import io
        import sys
        import shutil
        original_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Call the PDF converter
            print(f"Starting conversion of {input_path}")
            
            # Get the current working directory
            cwd = os.getcwd()
            print(f"Current working directory: {cwd}")
            
            # Expected output locations
            expected_outputs = [
                os.path.join(cwd, 'output.pdf'),  # CWD
                os.path.join(os.path.dirname(input_path), 'output.pdf'),  # Input directory
                'output.pdf'  # Relative path
            ]
            
            # Call the PDF converter
            try:
                output_file = pdf_converter.main(input_path)
                print(f"PDF converter completed, returned output path: {output_file}")
                
                # If the converter returned a specific output path, add it to expected outputs
                if output_file and output_file not in expected_outputs:
                    expected_outputs.insert(0, output_file)
            except Exception as e:
                print(f"Error in PDF conversion: {e}")
                # Try a simple fallback conversion
                try:
                    print("Attempting fallback conversion...")
                    fallback_output = os.path.join(cwd, 'output.pdf')
                    
                    # Import required modules
                    import fitz  # PyMuPDF
                    
                    # Simple conversion using PyMuPDF
                    doc = fitz.open(input_path)
                    output_doc = fitz.open()
                    
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        pix = page.get_pixmap()
                        
                        # Convert to grayscale
                        gray_pix = fitz.Pixmap(fitz.csGRAY, pix)
                        
                        # Create a new page in the output document
                        output_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
                        
                        # Insert the grayscale image
                        output_page.insert_image(output_page.rect, pixmap=gray_pix)
                    
                    output_doc.save(fallback_output)
                    output_doc.close()
                    doc.close()
                    
                    print(f"Fallback conversion successful, output saved to {fallback_output}")
                except Exception as fallback_error:
                    print(f"Fallback conversion failed: {fallback_error}")
                    # If all else fails, just copy the original file
                    try:
                        fallback_output = os.path.join(cwd, 'output.pdf')
                        shutil.copy(input_path, fallback_output)
                        print(f"Copied original file to {fallback_output}")
                    except Exception as copy_error:
                        print(f"Failed to copy original file: {copy_error}")
                        job_info['status'] = 'failed'
                        job_info['error'] = f"PDF conversion error: {str(e)}"
                        raise
            
            # Check all possible output locations
            output_found = False
            actual_output = None
            
            for expected_output in expected_outputs:
                print(f"Checking for output at: {expected_output}")
                if os.path.exists(expected_output):
                    print(f"Found output file at: {expected_output}")
                    actual_output = expected_output
                    output_found = True
                    break
            
            if output_found:
                print(f"Copying {actual_output} to {output_path}")
                shutil.copy2(actual_output, output_path)
                
                # Remove the original file after copying
                try:
                    os.remove(actual_output)
                    print(f"Removed original output file: {actual_output}")
                except Exception as e:
                    print(f"Warning: Could not remove original output.pdf: {e}")
                
                # Verify the file was copied successfully
                if os.path.exists(output_path):
                    print(f"File successfully copied to {output_path}")
                    job_info['output_path'] = output_path
                    job_info['status'] = 'completed'
                else:
                    print(f"Failed to copy file to {output_path}")
                    job_info['status'] = 'failed'
                    job_info['error'] = 'Failed to save output file'
            else:
                print("Output.pdf not found in any expected location")
                # List files in current directory for debugging
                print(f"Files in current directory: {os.listdir(cwd)}")
                if os.path.exists(os.path.dirname(input_path)):
                    print(f"Files in input directory: {os.listdir(os.path.dirname(input_path))}")
                
                # Last resort - copy the original file
                try:
                    print("Copying original file as last resort")
                    shutil.copy(input_path, output_path)
                    if os.path.exists(output_path):
                        print(f"Successfully copied original file to {output_path}")
                        job_info['output_path'] = output_path
                        job_info['status'] = 'completed'
                        job_info['warning'] = 'Could not convert PDF, original file provided instead'
                    else:
                        job_info['status'] = 'failed'
                        job_info['error'] = 'Conversion failed and could not copy original file'
                except Exception as e:
                    print(f"Failed to copy original file: {e}")
                    job_info['status'] = 'failed'
                    job_info['error'] = 'Conversion failed to produce output file'
        except Exception as e:
            print(f"Error in PDF conversion process: {e}")
            job_info['status'] = 'failed'
            job_info['error'] = str(e)
        finally:
            # Restore stdout and capture the output
            sys.stdout = original_stdout
            job_info['log'] = captured_output.getvalue()
            save_job_info(job_id, job_info)
            
            # Print the log for debugging
            print(f"Conversion log for job {job_id}:")
            print(job_info['log'])
            
        # Clean up the input file
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
                print(f"Removed input file: {input_path}")
        except Exception as e:
            print(f"Error removing input file: {e}")
            
    except Exception as e:
        print(f"Error in process_pdf: {e}")
        try:
            job_info = get_job_info(job_id)
            if job_info:
                job_info['status'] = 'failed'
                job_info['error'] = str(e)
                save_job_info(job_id, job_info)
        except Exception as inner_e:
            print(f"Error updating job info: {inner_e}")

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
    job_info = {
        'status': 'queued',
        'original_filename': filename,
        'input_path': input_path,
        'output_path': None,
        'error': None,
        'log': None,
        'created_at': time.time()
    }
    save_job_info(job_id, job_info)
    
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
    job_info = get_job_info(job_id)
    if not job_info:
        return jsonify({'error': 'Job not found'}), 404
        
    response = {
        'job_id': job_id,
        'status': job_info['status'],
        'original_filename': job_info['original_filename']
    }
    
    if job_info['status'] == 'completed':
        # Usar una URL directa a través de Nginx
        if job_info.get('output_path'):
            filename = os.path.basename(job_info['output_path'])
            nginx_url = f"/downloads/{filename}"
            response['download_url'] = nginx_url
        else:
            response['download_url'] = url_for('download_file', job_id=job_id, _external=True)
            
        # Include any warnings
        if job_info.get('warning'):
            response['warning'] = job_info['warning']
    elif job_info['status'] == 'failed':
        response['error'] = job_info['error']
    
    # Include log for detailed progress
    if job_info.get('log'):
        response['log'] = job_info['log']
        
    return jsonify(response)

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """Serve files from the results directory"""
    try:
        return send_from_directory(app.config['RESULT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        print(f"Error sending file: {e}")
        return f"Error al enviar el archivo: {str(e)}", 500

@app.route('/api/docs')
def api_docs():
    return render_template('api_docs.html')

@app.route('/direct-download/<job_id>', methods=['GET'])
def direct_download(job_id):
    """Ruta alternativa para descargar archivos directamente"""
    print(f"Direct download attempt for job_id: {job_id}")
    
    job_info = get_job_info(job_id)
    if not job_info:
        print(f"Job not found: {job_id}")
        return "Archivo no encontrado", 404
    
    print(f"Job status: {job_info['status']}")
    
    if job_info['status'] != 'completed':
        print(f"Job not completed: {job_id}")
        return "Archivo no disponible - conversión no completada", 404
    
    if not job_info.get('output_path'):
        print(f"No output path for job: {job_id}")
        return "Ruta de archivo no disponible", 404
    
    output_path = job_info['output_path']
    print(f"Output path: {output_path}")
    
    if not os.path.exists(output_path):
        print(f"File does not exist at path: {output_path}")
        return "Archivo no encontrado en el servidor", 404
    
    # Generate a more user-friendly filename
    original_name = os.path.splitext(job_info['original_filename'])[0]
    download_name = f"{original_name}_convertido.pdf"
    
    print(f"Sending file: {output_path} as {download_name}")
    
    try:
        # Usar send_from_directory en lugar de send_file para mayor compatibilidad
        if os.path.isabs(output_path):
            directory = os.path.dirname(output_path)
            filename = os.path.basename(output_path)
        else:
            directory = app.config['RESULT_FOLDER']
            filename = output_path
            
        print(f"Sending from directory: {directory}, filename: {filename}")
        
        # Copiar el archivo a un archivo temporal con un nombre más amigable
        import shutil
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, download_name)
        shutil.copy2(os.path.join(directory, filename), temp_file)
        
        print(f"Copied to temp file: {temp_file}")
        
        return send_file(
            temp_file,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error sending file: {e}")
        return f"Error al enviar el archivo: {str(e)}", 500

@app.route('/api/convert-direct', methods=['POST'])
def convert_pdf_direct():
    """Endpoint para convertir un PDF y devolverlo directamente"""
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
    job_info = {
        'status': 'processing',
        'original_filename': filename,
        'input_path': input_path,
        'output_path': None,
        'error': None,
        'log': None,
        'created_at': time.time()
    }
    save_job_info(job_id, job_info)
    
    # Define output path
    output_filename = f"{job_id}.pdf"
    output_path = os.path.join(app.config['RESULT_FOLDER'], output_filename)
    
    try:
        # Process the PDF synchronously
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
                print(f"Output.pdf exists, copying to {output_path}")
                import shutil
                shutil.copy2('output.pdf', output_path)
                
                try:
                    os.remove('output.pdf')
                except Exception as e:
                    print(f"Warning: Could not remove original output.pdf: {e}")
                
                if os.path.exists(output_path):
                    print(f"File successfully copied to {output_path}")
                    job_info['output_path'] = output_path
                    job_info['status'] = 'completed'
                else:
                    print(f"Failed to copy file to {output_path}")
                    job_info['status'] = 'failed'
                    job_info['error'] = 'Failed to save output file'
                    return jsonify({'error': 'Failed to save output file'}), 500
            else:
                print("Output.pdf not found")
                job_info['status'] = 'failed'
                job_info['error'] = 'Conversion failed to produce output file'
                return jsonify({'error': 'Conversion failed to produce output file'}), 500
        except Exception as e:
            print(f"Error in PDF conversion: {e}")
            job_info['status'] = 'failed'
            job_info['error'] = str(e)
            return jsonify({'error': str(e)}), 500
        finally:
            # Restore stdout and capture the output
            sys.stdout = original_stdout
            job_info['log'] = captured_output.getvalue()
            save_job_info(job_id, job_info)
        
        # Clean up the input file
        try:
            os.remove(input_path)
        except Exception as e:
            print(f"Error removing input file: {e}")
        
        # Generate a more user-friendly filename
        original_name = os.path.splitext(filename)[0]
        download_name = f"{original_name}_convertido.pdf"
        
        # Return the converted PDF directly
        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error in convert_pdf_direct: {e}")
        return jsonify({'error': str(e)}), 500

# Clean up old jobs periodically
@app.before_request
def cleanup_old_jobs():
    # Solo ejecutar la limpieza ocasionalmente (1 de cada 20 solicitudes)
    import random
    if random.random() > 0.05:
        return
        
    try:
        print("Running cleanup job...")
        current_time = time.time()
        cleaned_count = 0
        
        # Check jobs directory for old files
        for filename in os.listdir(app.config['JOBS_FOLDER']):
            if not filename.endswith('.json'):
                continue
                
            job_file = os.path.join(app.config['JOBS_FOLDER'], filename)
            file_age = current_time - os.path.getmtime(job_file)
            
            # Remove files older than 15 minutes (900 seconds)
            if file_age > 900:
                try:
                    # Load job info to get paths
                    with open(job_file, 'r') as f:
                        job_info = json.load(f)
                    
                    # Remove output file if it exists
                    if job_info.get('output_path') and os.path.exists(job_info['output_path']):
                        os.remove(job_info['output_path'])
                        print(f"Removed output file: {job_info['output_path']}")
                    
                    # Remove input file if it exists
                    if job_info.get('input_path') and os.path.exists(job_info['input_path']):
                        os.remove(job_info['input_path'])
                        print(f"Removed input file: {job_info['input_path']}")
                    
                    # Remove job file
                    os.remove(job_file)
                    print(f"Removed job file: {job_file}")
                    
                    # Remove from memory cache
                    job_id = os.path.splitext(filename)[0]
                    if job_id in conversion_jobs:
                        del conversion_jobs[job_id]
                        
                    cleaned_count += 1
                except Exception as e:
                    print(f"Error cleaning up job {filename}: {e}")
        
        # Also check for orphaned files in uploads and results directories
        for directory, prefix in [(app.config['UPLOAD_FOLDER'], ''), (app.config['RESULT_FOLDER'], '')]:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                # Remove files older than 30 minutes (1800 seconds)
                if file_age > 1800:
                    try:
                        os.remove(file_path)
                        print(f"Removed orphaned file: {file_path}")
                        cleaned_count += 1
                    except Exception as e:
                        print(f"Error removing orphaned file {file_path}: {e}")
        
        if cleaned_count > 0:
            print(f"Cleanup completed: removed {cleaned_count} files")
            
    except Exception as e:
        print(f"Error in cleanup_old_jobs: {e}")

# Definir la función de limpieza programada completa
def scheduled_cleanup():
    print("Running scheduled cleanup...")
    current_time = time.time()
    cleaned_count = 0
    
    try:
        # Check jobs directory for old files
        for filename in os.listdir(app.config['JOBS_FOLDER']):
            if not filename.endswith('.json'):
                continue
                
            job_file = os.path.join(app.config['JOBS_FOLDER'], filename)
            file_age = current_time - os.path.getmtime(job_file)
            
            # Remove files older than 15 minutes
            if file_age > 900:
                try:
                    # Load job info to get paths
                    with open(job_file, 'r') as f:
                        job_info = json.load(f)
                    
                    # Remove output file if it exists
                    if job_info.get('output_path') and os.path.exists(job_info['output_path']):
                        os.remove(job_info['output_path'])
                        print(f"Removed output file: {job_info['output_path']}")
                    
                    # Remove input file if it exists
                    if job_info.get('input_path') and os.path.exists(job_info['input_path']):
                        os.remove(job_info['input_path'])
                        print(f"Removed input file: {job_info['input_path']}")
                    
                    # Remove job file
                    os.remove(job_file)
                    print(f"Removed job file: {job_file}")
                    
                    # Remove from memory cache
                    job_id = os.path.splitext(filename)[0]
                    if job_id in conversion_jobs:
                        del conversion_jobs[job_id]
                        
                    cleaned_count += 1
                except Exception as e:
                    print(f"Error cleaning up job {filename}: {e}")
        
        # Also check for orphaned files in uploads and results directories
        for directory, prefix in [(app.config['UPLOAD_FOLDER'], ''), (app.config['RESULT_FOLDER'], '')]:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                # Remove files older than 30 minutes
                if file_age > 1800:
                    try:
                        os.remove(file_path)
                        print(f"Removed orphaned file: {file_path}")
                        cleaned_count += 1
                    except Exception as e:
                        print(f"Error removing orphaned file {file_path}: {e}")
        
        if cleaned_count > 0:
            print(f"Scheduled cleanup completed: removed {cleaned_count} files")
    except Exception as e:
        print(f"Error in scheduled_cleanup: {e}")

# Iniciar el programador
# scheduler = BackgroundScheduler()
# scheduler.add_job(scheduled_cleanup, 'interval', minutes=5)
# scheduler.start()

# Asegurarse de que el programador se detenga cuando la aplicación se cierre
# import atexit
# atexit.register(lambda: scheduler.shutdown())

@app.before_first_request
def before_first_request():
    """Run before the first request to check dependencies"""
    # Create necessary folders if they don't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)
    os.makedirs(app.config['JOBS_FOLDER'], exist_ok=True)
    
    # Check dependencies
    check_dependencies()
    
    print("Application initialized and ready to process PDFs")
    
    # Check if we can write to the necessary directories
    try:
        test_file = os.path.join(app.config['UPLOAD_FOLDER'], 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Successfully verified write access to {app.config['UPLOAD_FOLDER']}")
    except Exception as e:
        print(f"WARNING: Cannot write to upload folder: {e}")
        
    try:
        test_file = os.path.join(app.config['RESULT_FOLDER'], 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Successfully verified write access to {app.config['RESULT_FOLDER']}")
    except Exception as e:
        print(f"WARNING: Cannot write to result folder: {e}")
        
    try:
        test_file = os.path.join(app.config['JOBS_FOLDER'], 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Successfully verified write access to {app.config['JOBS_FOLDER']}")
    except Exception as e:
        print(f"WARNING: Cannot write to jobs folder: {e}")
        
    # Check if we can write to the current directory
    try:
        test_file = os.path.join(os.getcwd(), 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Successfully verified write access to current directory: {os.getcwd()}")
    except Exception as e:
        print(f"WARNING: Cannot write to current directory: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 