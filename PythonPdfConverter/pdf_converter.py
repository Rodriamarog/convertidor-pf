import os
import sys
import subprocess
import tempfile
import shutil
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, ArrayObject
import pdfplumber

def check_encrypted(input_pdf):
    reader = PdfReader(input_pdf)
    if reader.is_encrypted:
        print("Error: Encrypted PDFs are not supported.")
        sys.exit(1)

def flatten_pdf_forms(input_pdf, output_pdf):
    """Flatten PDF forms to preserve text content while removing interactivity"""
    print("Flattening PDF forms to preserve entered text...")
    
    # Try using pdftk first (most reliable for form flattening)
    try:
        subprocess.run(['pdftk', input_pdf, 'output', output_pdf, 'flatten'], check=True)
        print("  Used pdftk for form flattening")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  pdftk not available or failed, trying alternative method...")
    
    # Try using qpdf as an alternative
    try:
        subprocess.run(['qpdf', '--flatten-annotations=all', input_pdf, output_pdf], check=True)
        print("  Used qpdf for form flattening")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  qpdf not available or failed, trying Ghostscript...")
    
    # Use Ghostscript as a last resort
    try:
        gs_cmd = [
            'gs',
            '-dSAFER',
            '-dBATCH',
            '-dNOPAUSE',
            '-sDEVICE=pdfwrite',
            '-dFIXEDMEDIA',
            '-dPDFFitPage',
            '-dCompatibilityLevel=1.4',
            f'-sOutputFile={output_pdf}',
            input_pdf
        ]
        subprocess.run(gs_cmd, check=True)
        print("  Used Ghostscript for form flattening")
        return
    except subprocess.CalledProcessError:
        print("  All flattening methods failed, continuing without flattening")
        # If all methods fail, copy the input to output and continue
        shutil.copy(input_pdf, output_pdf)

def remove_forms_js_attachments(input_pdf, output_pdf):
    """Remove forms, JavaScript, and attachments but preserve content"""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        if '/Annots' in page:
            annots = page['/Annots']
            new_annots = []
            for annot_ref in annots:
                annot = annot_ref.get_object()
                # Only remove JavaScript and form interactivity, not the content
                # This is safer now because we've already flattened the forms
                if '/JS' in annot.get('/AA', {}) or '/FT' in annot:
                    continue
                new_annots.append(annot_ref)
            page[NameObject('/Annots')] = ArrayObject(new_annots)
        writer.add_page(page)

    # Remove form definitions but not the content (already flattened)
    if '/AcroForm' in writer._root_object:
        del writer._root_object['/AcroForm']
    
    # Remove embedded files
    names = writer._root_object.get('/Names', {})
    if isinstance(names, dict) and '/EmbeddedFiles' in names:
        del names['/EmbeddedFiles']

    with open(output_pdf, 'wb') as f:
        writer.write(f)

def convert_grayscale_300dpi(input_pdf, output_pdf):
    """Convert to grayscale at 300 DPI while optimizing file size"""
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dColorConversionStrategy=/Gray',
        '-dProcessColorModel=/DeviceGray',
        '-dPDFSETTINGS=/printer',  # Balance quality and size
        '-dCompatibilityLevel=1.4',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
        # Optimize for smaller file size
        '-dCompressFonts=true',
        '-dEmbedAllFonts=true',
        '-dSubsetFonts=true',
        # Specify resolution without excessive upsampling
        '-dColorImageResolution=300',
        '-dGrayImageResolution=300',
        '-dMonoImageResolution=300',
        # Only downsample images with resolution higher than 300 DPI
        '-dDownsampleColorImages=true',
        '-dColorImageDownsampleThreshold=1.5',
        '-dDownsampleGrayImages=true',
        '-dGrayImageDownsampleThreshold=1.5',
        '-dDownsampleMonoImages=true',
        '-dMonoImageDownsampleThreshold=1.5',
        f'-sOutputFile={output_pdf}',
        input_pdf
    ]
    subprocess.run(gs_command, check=True)

def check_dpi(input_pdf):
    """Check if PDF already has 300 DPI or close to it"""
    try:
        # Use pdfinfo to extract page size
        pdfinfo_output = subprocess.check_output(["pdfinfo", input_pdf], text=True)
        
        page_size_pts = None
        for line in pdfinfo_output.splitlines():
            if "Page size:" in line and "pts" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    size_part = parts[1].strip()
                    pts_parts = size_part.split("pts")[0].strip().split("x")
                    if len(pts_parts) == 2:
                        page_size_pts = (float(pts_parts[0].strip()), float(pts_parts[1].strip()))
        
        if not page_size_pts:
            print("  Could not determine page size, assuming DPI needs fixing")
            return False
            
        # Extract an image at 300 DPI and check dimensions
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_path = os.path.join(tmpdir, "sample")
            subprocess.run([
                "pdftoppm",
                "-png",
                "-r", "300",
                "-f", "1",
                "-l", "1",
                input_pdf,
                sample_path
            ], check=True)
            
            # Find the extracted image
            files = [f for f in os.listdir(tmpdir) if f.endswith('.png')]
            if not files:
                print("  Could not extract sample image, assuming DPI needs fixing")
                return False
                
            image_path = os.path.join(tmpdir, files[0])
            identify_output = subprocess.check_output(["identify", image_path], text=True)
            
            # Parse dimensions
            parts = identify_output.split()
            dimensions = parts[2].split("x")
            width_px = int(dimensions[0])
            height_px = int(dimensions[1])
            
            # Calculate effective DPI
            dpi_w = width_px / (page_size_pts[0] / 72.0)
            dpi_h = height_px / (page_size_pts[1] / 72.0)
            
            # Check if close to 300 DPI
            dpi_ok = 290 <= dpi_w <= 310 and 290 <= dpi_h <= 310
            
            if dpi_ok:
                print(f"  PDF already has approximately 300 DPI ({dpi_w:.2f} x {dpi_h:.2f})")
                return True
            else:
                print(f"  PDF has {dpi_w:.2f} x {dpi_h:.2f} DPI, needs fixing")
                return False
    
    except Exception as e:
        print(f"  Error checking DPI: {e}")
        return False

def selective_dpi_fix(input_pdf, output_pdf):
    """Fix DPI only if needed, using a more efficient method"""
    # First check if DPI is already correct
    if check_dpi(input_pdf):
        # Just copy the file if DPI is already 300
        shutil.copy(input_pdf, output_pdf)
        return
    
    # If DPI needs fixing, use a more efficient method
    # This avoids full rasterization when possible
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.4',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
        # Set the output resolution
        '-r300',
        # Control image handling
        '-dColorImageResolution=300',
        '-dGrayImageResolution=300',
        '-dMonoImageResolution=300',
        # Only downsample images with resolution higher than 300 DPI
        '-dDownsampleColorImages=true',
        '-dColorImageDownsampleThreshold=1.5',
        '-dDownsampleGrayImages=true',
        '-dGrayImageDownsampleThreshold=1.5',
        '-dDownsampleMonoImages=true',
        '-dMonoImageDownsampleThreshold=1.5',
        # Set page size accurately
        '-dFIXEDMEDIA',
        '-dPDFFitPage',
        # Preserve vector content
        '-dNOCACHE',
        f'-sOutputFile={output_pdf}',
        input_pdf
    ]
    subprocess.run(gs_command, check=True)

def remove_blank_pages(input_pdf, output_pdf):
    with pdfplumber.open(input_pdf) as pdf:
        non_blank = []
        for page in pdf.pages:
            if page.extract_text() or len(page.images) > 0:
                non_blank.append(page.page_number)
        
        # If all pages seem blank, keep the first page
        if not non_blank and len(pdf.pages) > 0:
            non_blank = [1]
        
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        for num in non_blank:
            writer.add_page(reader.pages[num - 1])
        with open(output_pdf, 'wb') as f:
            writer.write(f)

def optimize_pdf_size(input_pdf, output_pdf, max_size=3*1024*1024):
    """Optimize PDF file size while maintaining quality"""
    initial_size = os.path.getsize(input_pdf)
    
    if initial_size <= max_size:
        shutil.copy(input_pdf, output_pdf)
        return
    
    print(f"  Initial size: {initial_size/1024/1024:.2f} MB, compressing...")
    
    # Start with moderate compression
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dPDFSETTINGS=/printer',  # Good balance of quality/size
        '-dCompatibilityLevel=1.4',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
        # Font settings
        '-dCompressFonts=true',
        '-dEmbedAllFonts=true',
        '-dSubsetFonts=true',
        # JPEG compression for images
        '-dAutoFilterColorImages=false',
        '-dColorImageFilter=/DCTEncode',
        '-dColorImageDownsampleType=/Bicubic',
        '-dColorImageResolution=150',  # Lower resolution to save space
        '-dGrayImageDownsampleType=/Bicubic',
        '-dGrayImageResolution=150',
        f'-sOutputFile={output_pdf}',
        input_pdf
    ]
    
    subprocess.run(gs_command, check=True)
    compressed_size = os.path.getsize(output_pdf)
    
    # If still too large, try more aggressive compression
    if compressed_size > max_size:
        print(f"  Still too large ({compressed_size/1024/1024:.2f} MB), applying stronger compression...")
        stronger_cmd = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dPDFSETTINGS=/ebook',  # More aggressive compression
            '-dCompatibilityLevel=1.4',
            '-dNOPAUSE',
            '-dBATCH',
            '-dQUIET',
            # JPEG quality setting
            '-dAutoFilterColorImages=false',
            '-dColorImageFilter=/DCTEncode',
            '-dColorImageDownsampleType=/Bicubic',
            '-dColorImageResolution=120',  # Even lower resolution
            '-dGrayImageDownsampleType=/Bicubic',
            '-dGrayImageResolution=120',
            f'-sOutputFile={output_pdf}.tmp',
            input_pdf
        ]
        
        subprocess.run(stronger_cmd, check=True)
        final_size = os.path.getsize(f"{output_pdf}.tmp")
        
        if final_size <= max_size:
            shutil.move(f"{output_pdf}.tmp", output_pdf)
        else:
            # If still too large, use screen quality (most aggressive)
            print(f"  Still too large ({final_size/1024/1024:.2f} MB), applying maximum compression...")
            max_cmd = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dPDFSETTINGS=/screen',  # Maximum compression
                '-dCompatibilityLevel=1.4',
                '-dNOPAUSE',
                '-dBATCH',
                '-dQUIET',
                f'-sOutputFile={output_pdf}',
                input_pdf
            ]
            subprocess.run(max_cmd, check=True)
            os.remove(f"{output_pdf}.tmp")
    
    final_size = os.path.getsize(output_pdf)
    print(f"  Final size: {final_size/1024/1024:.2f} MB (reduced by {(1 - final_size/initial_size)*100:.2f}%)")

def main(input_path):
    check_encrypted(input_path)
    temp_files = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as flattened, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step1, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step2, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step3:

            temp_files.extend([flattened.name, step1.name, step2.name, step3.name])
            
            print("1. Flattening PDF forms to preserve text content...")
            flatten_pdf_forms(input_path, flattened.name)
            
            print("2. Removing forms, JavaScript, and attachments...")
            remove_forms_js_attachments(flattened.name, step1.name)
            
            print("3. Converting to grayscale at 300 DPI...")
            convert_grayscale_300dpi(step1.name, step2.name)
            
            print("4. Checking for and removing blank pages...")
            remove_blank_pages(step2.name, step3.name)
            
            print("5. Optimizing file size...")
            output_pdf = 'output.pdf'
            optimize_pdf_size(step3.name, output_pdf)
            
    finally:
        # Cleanup all temporary files
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python pdf_converter.py input.pdf")
        sys.exit(1)
    
    print(f"Processing PDF: {sys.argv[1]}")
    main(sys.argv[1])
    print("Processing complete. Output saved as output.pdf")