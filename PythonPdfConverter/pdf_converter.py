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

def remove_forms_js_attachments(input_pdf, output_pdf):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        if '/Annots' in page:
            annots = page['/Annots']
            new_annots = []
            for annot_ref in annots:
                annot = annot_ref.get_object()
                if '/JS' in annot.get('/AA', {}) or '/FT' in annot:
                    continue
                new_annots.append(annot_ref)
            page[NameObject('/Annots')] = ArrayObject(new_annots)
        writer.add_page(page)

    if '/AcroForm' in writer._root_object:
        del writer._root_object['/AcroForm']
    
    names = writer._root_object.get('/Names', {})
    if isinstance(names, dict) and '/EmbeddedFiles' in names:
        del names['/EmbeddedFiles']

    with open(output_pdf, 'wb') as f:
        writer.write(f)

def convert_grayscale_300dpi(input_pdf, output_pdf):
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dColorConversionStrategy=/Gray',
        '-dProcessColorModel=/DeviceGray',
        '-dPDFSETTINGS=/printer',
        '-dCompatibilityLevel=1.4',
        '-dNEWPDF=false',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
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
                '-dNEWPDF=false',  # Added here too
                '-dNOPAUSE',
                '-dBATCH',
                '-dQUIET',
                f'-sOutputFile={tmp.name}',
                input_pdf
            ]
            subprocess.run(gs_command)
            if os.path.getsize(tmp.name) <= max_size:
                return tmp.name
    print("Warning: Unable to compress below 3 MB.")
    return input_pdf

def main(input_path):
    check_encrypted(input_path)
    temp_files = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step1, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step2, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step3:

            temp_files.extend([step1.name, step2.name, step3.name])
            
            remove_forms_js_attachments(input_path, step1.name)
            convert_grayscale_300dpi(step1.name, step2.name)
            remove_blank_pages(step2.name, step3.name)
            
            final_pdf = check_and_compress(step3.name)
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
    main(sys.argv[1])
    print("Processing complete. Output saved as output.pdf")