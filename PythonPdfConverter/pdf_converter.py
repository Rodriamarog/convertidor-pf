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
    # Use explicit parameters to force 300 DPI and grayscale
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dColorConversionStrategy=/Gray',
        '-dProcessColorModel=/DeviceGray',
        '-dPDFSETTINGS=/prepress',  # Higher quality setting
        '-dCompatibilityLevel=1.4',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
        # Force color conversion
        '-dUseCIEColor',
        # Explicit resolution settings
        '-dDownsampleColorImages=true',
        '-dDownsampleGrayImages=true',
        '-dDownsampleMonoImages=true',
        '-dColorImageResolution=300',
        '-dGrayImageResolution=300',
        '-dMonoImageResolution=300',
        # Ensure output DPI is set correctly
        '-r300',
        # Make sure we're thorough in color conversion
        '-sColorConversionStrategyForImages=/Gray',
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
        
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        for num in non_blank:
            writer.add_page(reader.pages[num - 1])
        with open(output_pdf, 'wb') as f:
            writer.write(f)

def check_and_compress(input_pdf, max_size=3*1024*1024):
    if os.path.getsize(input_pdf) <= max_size:
        return input_pdf
    
    qualities = ['/printer', '/ebook', '/screen']
    for quality in qualities:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            gs_command = [
                'gs',
                '-sDEVICE=pdfwrite',
                f'-dPDFSETTINGS={quality}',
                '-dCompatibilityLevel=1.4',
                '-dNOPAUSE',
                '-dBATCH',
                '-dQUIET',
                # Maintain 300 DPI
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=300',
                '-dGrayImageResolution=300',
                '-dMonoImageResolution=300',
                f'-sOutputFile={tmp.name}',
                input_pdf
            ]
            subprocess.run(gs_command)
            if os.path.getsize(tmp.name) <= max_size:
                return tmp.name
    print("Warning: Unable to compress below 3 MB.")
    return input_pdf

def force_dpi_fix(input_pdf, output_pdf):
    """Additional step to ensure 300 DPI by rasterizing and rebuilding"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract all pages as images at 300 DPI
        extract_cmd = [
            'pdftoppm',
            '-png',
            '-r', '300',  # 300 DPI
            '-gray',      # Ensure grayscale
            input_pdf,
            os.path.join(tmpdir, 'page')
        ]
        subprocess.run(extract_cmd, check=True)
        
        # Combine the images back into a PDF
        img_files = sorted([os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith('.png')])
        
        if not img_files:
            print("Warning: No pages extracted, skipping DPI fix")
            shutil.copy(input_pdf, output_pdf)
            return
            
        img2pdf_cmd = [
            'convert',
            '-density', '300',  # Set density to 300 DPI
            '-units', 'PixelsPerInch',
            '-compress', 'JPEG',
            '-quality', '100',
            *img_files,
            output_pdf
        ]
        
        try:
            subprocess.run(img2pdf_cmd, check=True)
        except subprocess.CalledProcessError:
            print("Warning: Error in ImageMagick convert, trying alternative method")
            # Fallback to img2pdf if ImageMagick fails
            try:
                import img2pdf
                with open(output_pdf, "wb") as f:
                    f.write(img2pdf.convert(img_files, dpi=300))
            except ImportError:
                print("Warning: img2pdf not available, copying original")
                shutil.copy(input_pdf, output_pdf)

def main(input_path):
    check_encrypted(input_path)
    temp_files = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as flattened, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step1, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step2, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step3, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step4:

            temp_files.extend([flattened.name, step1.name, step2.name, step3.name, step4.name])
            
            print("1. Flattening PDF forms to preserve text content...")
            flatten_pdf_forms(input_path, flattened.name)
            
            print("2. Removing forms, JavaScript, and attachments...")
            remove_forms_js_attachments(flattened.name, step1.name)
            
            print("3. Converting to grayscale at 300 DPI...")
            convert_grayscale_300dpi(step1.name, step2.name)
            
            print("4. Ensuring 300 DPI for all content...")
            force_dpi_fix(step2.name, step3.name)
            
            print("5. Removing blank pages...")
            remove_blank_pages(step3.name, step4.name)
            
            print("6. Checking file size and compressing if needed...")
            final_pdf = check_and_compress(step4.name)
            if final_pdf != step4.name:
                temp_files.append(final_pdf)

            # Cross-device safe copy
            shutil.copy(final_pdf, 'output.pdf')
            
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