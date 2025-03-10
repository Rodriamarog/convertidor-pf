import os
import sys
import subprocess
import tempfile
import shutil
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, ArrayObject
import pdfplumber
import fitz  # PyMuPDF
import io
from PIL import Image
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

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

def compress_grayscale_300dpi(input_pdf, output_pdf, quality_level="low"):
    """Convert to grayscale at 300 DPI with compression settings"""
    
    # Set resolution based on quality level
    if quality_level == "high":
        image_res = 300
        downsample_threshold = 1.5
    elif quality_level == "medium":
        image_res = 200
        downsample_threshold = 1.2
    elif quality_level == "low":
        image_res = 150
        downsample_threshold = 1.0
    else:  # minimum
        image_res = 100
        downsample_threshold = 1.0
    
    print(f"  Using quality level: {quality_level} (resolution: {image_res} DPI)")
    
    gs_command = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dColorConversionStrategy=/Gray',
        '-dProcessColorModel=/DeviceGray',
        '-dCompatibilityLevel=1.4',
        '-dNOPAUSE',
        '-dBATCH',
        '-dQUIET',
        # Set overall quality based on level
        f'-dPDFSETTINGS=/{"prepress" if quality_level == "high" else "printer" if quality_level == "medium" else "ebook" if quality_level == "low" else "screen"}',
        # Font settings for size reduction
        '-dCompressFonts=true',
        '-dEmbedAllFonts=true',
        '-dSubsetFonts=true',
        # Image settings
        '-dColorImageDownsampleType=/Bicubic',
        '-dGrayImageDownsampleType=/Bicubic',
        '-dMonoImageDownsampleType=/Bicubic',
        f'-dColorImageResolution={image_res}',
        f'-dGrayImageResolution={image_res}',
        f'-dMonoImageResolution={image_res}',
        '-dDownsampleColorImages=true',
        '-dDownsampleGrayImages=true',
        '-dDownsampleMonoImages=true',
        f'-dColorImageDownsampleThreshold={downsample_threshold}',
        f'-dGrayImageDownsampleThreshold={downsample_threshold}',
        f'-dMonoImageDownsampleThreshold={downsample_threshold}',
        # Use JPEG compression for images
        '-dAutoFilterColorImages=false',
        '-dAutoFilterGrayImages=false',
        '-dColorImageFilter=/DCTEncode',
        '-dGrayImageFilter=/DCTEncode',
        # Set JPEG quality
        f'-dJPEGQ={85 if quality_level == "high" else 75 if quality_level == "medium" else 65 if quality_level == "low" else 50}',
        # Output
        f'-sOutputFile={output_pdf}',
        input_pdf
    ]
    
    try:
        subprocess.run(gs_command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error during compression: {e}")
        return False

def remove_blank_pages(input_pdf, output_pdf):
    """Remove blank pages from PDF"""
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

def ensure_grayscale(input_pdf, output_pdf, preserve_quality=False):
    """Convert PDF to grayscale, with option to preserve quality for small files"""
    print("Convirtiendo PDF a escala de grises...")
    
    # Determinar si el archivo ya está en escala de grises
    is_grayscale = check_if_grayscale(input_pdf)
    if is_grayscale:
        print("  El PDF ya está en escala de grises, omitiendo conversión.")
        shutil.copy(input_pdf, output_pdf)
        return
    
    # Para archivos pequeños donde queremos preservar calidad
    if preserve_quality:
        try:
            print("  Usando método de alta calidad para conversión a escala de grises...")
            # Usar Ghostscript con configuración de alta calidad
            gs_cmd = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dColorConversionStrategy=/Gray',
                '-dProcessColorModel=/DeviceGray',
                '-dCompatibilityLevel=1.4',
                '-dNOPAUSE',
                '-dBATCH',
                '-dQUIET',
                # Configuración de alta calidad
                '-dPDFSETTINGS=/prepress',
                '-dColorImageResolution=300',
                '-dGrayImageResolution=300',
                '-dMonoImageResolution=300',
                # No comprimir imágenes
                '-dAutoFilterColorImages=false',
                '-dAutoFilterGrayImages=false',
                '-dColorImageFilter=/FlateEncode',
                '-dGrayImageFilter=/FlateEncode',
                f'-sOutputFile={output_pdf}',
                input_pdf
            ]
            subprocess.run(gs_cmd, check=True)
            print("  Conversión a escala de grises completada con alta calidad")
            return
        except Exception as e:
            print(f"  Error en conversión de alta calidad: {e}")
            print("  Intentando método alternativo...")
    
    # Método estándar (el original)
    print("  Intentando PyMuPDF para conversión a escala de grises...")
    try:
        # Method 1: Try PyMuPDF (fitz) first - highest quality
        doc = fitz.open(input_pdf)
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
        
        output_doc.save(output_pdf)
        output_doc.close()
        doc.close()
        return True
    except Exception as e:
        print(f"  PyMuPDF grayscale conversion failed: {e}")
    
    # Method 2: Try Pillow with pdf2image
    if convert_from_path:
        try:
            print("  Trying pdf2image and Pillow for grayscale conversion...")
            success = grayscale_with_pillow(input_pdf, output_pdf)
            if success:
                print("  Successfully converted to grayscale using Pillow")
                return True
        except Exception as e:
            print(f"  Pillow grayscale conversion failed: {e}")
    
    # Method 3: Fallback to Ghostscript
    try:
        print("  Falling back to Ghostscript for grayscale conversion...")
        gs_command = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dColorConversionStrategy=/Gray',
            '-dProcessColorModel=/DeviceGray',
            '-dCompatibilityLevel=1.4',
            '-dNOPAUSE',
            '-dBATCH',
            '-dQUIET',
            # Preserve quality
            '-dPDFSETTINGS=/prepress',
            # Don't downsample images
            '-dDownsampleColorImages=false',
            '-dDownsampleGrayImages=false',
            '-dDownsampleMonoImages=false',
            # Output
            f'-sOutputFile={output_pdf}',
            input_pdf
        ]
        subprocess.run(gs_command, check=True)
        print("  Successfully converted to grayscale using Ghostscript")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Ghostscript grayscale conversion failed: {e}")
        # If all methods fail, copy the input to output and continue
        shutil.copy(input_pdf, output_pdf)
        print("  WARNING: All grayscale conversion methods failed")
        return False

def grayscale_with_pymupdf(input_pdf, output_pdf):
    """Convert PDF to grayscale using PyMuPDF"""
    doc = fitz.open(input_pdf)
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
    
    output_doc.save(output_pdf)
    output_doc.close()
    doc.close()
    return True

def grayscale_with_pillow(input_pdf, output_pdf):
    """Convert PDF to grayscale using Pillow and pdf2image"""
    # Convert PDF pages to images
    images = convert_from_path(input_pdf)
    
    # Convert each image to grayscale
    grayscale_images = []
    for img in images:
        gray_img = img.convert('L')  # 'L' mode is grayscale
        grayscale_images.append(gray_img)
    
    # Save the first grayscale image to PDF
    first_img = grayscale_images[0]
    if len(grayscale_images) == 1:
        first_img.save(output_pdf, 'PDF')
    else:
        # Save all images to PDF
        first_img.save(
            output_pdf, 'PDF', resolution=300.0, 
            save_all=True, append_images=grayscale_images[1:]
        )
    
    return True

def aggressive_compress(input_pdf, output_pdf, max_size_mb=3):
    """Aggressively compress PDF until it's under the size limit"""
    max_size_bytes = max_size_mb * 1024 * 1024
    original_size = os.path.getsize(input_pdf)
    
    # Already small enough?
    if original_size <= max_size_bytes:
        print(f"  File is already under {max_size_mb}MB ({original_size/1024/1024:.2f}MB)")
        shutil.copy(input_pdf, output_pdf)
        return True
    
    print(f"  Original size: {original_size/1024/1024:.2f}MB, needs compression")
    
    # Try progressively stronger compression until the file is small enough
    quality_levels = ["high", "medium", "low", "minimum"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_output = os.path.join(tmpdir, "compressed.pdf")
        
        for quality in quality_levels:
            print(f"  Trying {quality} quality compression...")
            compress_grayscale_300dpi(input_pdf, temp_output, quality)
            
            current_size = os.path.getsize(temp_output)
            print(f"  Size after {quality} compression: {current_size/1024/1024:.2f}MB")
            
            if current_size <= max_size_bytes:
                print(f"  Successfully compressed to under {max_size_mb}MB")
                shutil.copy(temp_output, output_pdf)
                return True
        
        # If we get here, try super aggressive compression as a last resort
        if current_size > max_size_bytes:
            print("  Still too large, trying image-based conversion...")
            if downsample_to_images(input_pdf, temp_output, max_size_bytes):
                shutil.copy(temp_output, output_pdf)
                return True
        
        # If all else fails, we need to offer more drastic options
        print(f"  WARNING: Could not compress below {max_size_mb}MB with quality preservation")
        print(f"  Final size: {os.path.getsize(temp_output)/1024/1024:.2f}MB")
        
        # Copy our best attempt anyway
        shutil.copy(temp_output, output_pdf)
        return False

def downsample_to_images(input_pdf, output_pdf, max_size_bytes):
    """Last resort: Convert PDF to downsampled images and rebuild"""
    try:
        # Start with a reasonable DPI
        for dpi in [150, 120, 100, 75]:
            print(f"  Trying image-based conversion at {dpi} DPI...")
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract pages as images
                extract_cmd = [
                    'pdftoppm',
                    '-png',
                    '-r', str(dpi),
                    '-gray',
                    input_pdf,
                    os.path.join(tmpdir, 'page')
                ]
                subprocess.run(extract_cmd, check=True)
                
                # Find all generated images
                img_files = sorted([
                    os.path.join(tmpdir, f) 
                    for f in os.listdir(tmpdir) 
                    if f.endswith('.png')
                ])
                
                if not img_files:
                    print("  No images extracted!")
                    return False
                
                # Combine into a PDF with tight compression
                temp_pdf = os.path.join(tmpdir, "temp.pdf")
                
                try:
                    # Try img2pdf first (usually better size/quality ratio)
                    import img2pdf
                    with open(temp_pdf, "wb") as f:
                        f.write(img2pdf.convert(img_files, dpi=dpi))
                except ImportError:
                    # Fall back to ImageMagick
                    convert_cmd = [
                        'convert',
                        '-density', str(dpi),
                        '-quality', '50',
                        '-compress', 'JPEG',
                        *img_files,
                        temp_pdf
                    ]
                    subprocess.run(convert_cmd, check=True)
                
                # Check if we're now under the size limit
                if os.path.getsize(temp_pdf) <= max_size_bytes:
                    print(f"  Successfully compressed to {os.path.getsize(temp_pdf)/1024/1024:.2f}MB using {dpi} DPI images")
                    shutil.copy(temp_pdf, output_pdf)
                    return True
        
        # If we get here, even the lowest quality didn't work
        return False
        
    except Exception as e:
        print(f"  Error during image-based compression: {e}")
        return False

def check_if_grayscale(input_pdf):
    """Verifica si un PDF ya está en escala de grises"""
    try:
        # Usar PyMuPDF para verificar si el PDF ya está en escala de grises
        doc = fitz.open(input_pdf)
        
        # Verificar una muestra de páginas (hasta 5)
        pages_to_check = min(5, len(doc))
        for page_num in range(pages_to_check):
            page = doc[page_num]
            pix = page.get_pixmap(alpha=False)
            
            # Verificar si la imagen ya está en escala de grises
            # En PyMuPDF, podemos verificar el espacio de color
            if pix.colorspace and pix.colorspace.name != "DeviceGray":
                doc.close()
                return False
        
        doc.close()
        return True
    except Exception as e:
        print(f"  Error al verificar escala de grises: {e}")
        # En caso de error, asumimos que no está en escala de grises
        return False

def main(input_path):
    check_encrypted(input_path)
    temp_files = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as flattened, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step1, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step2, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as step3:

            temp_files.extend([flattened.name, step1.name, step2.name, step3.name])
            
            # Verificar tamaño inicial
            original_size = os.path.getsize(input_path) / (1024 * 1024)
            max_size_mb = 3
            
            print(f"Tamaño original del archivo: {original_size:.2f}MB")
            
            # Siempre realizar estos pasos para cumplir con requisitos de seguridad
            print("1. Aplanando formularios PDF para preservar el contenido de texto...")
            flatten_pdf_forms(input_path, flattened.name)
            
            print("2. Eliminando formularios, JavaScript y adjuntos...")
            remove_forms_js_attachments(flattened.name, step1.name)
            
            print("3. Eliminando páginas en blanco...")
            remove_blank_pages(step1.name, step2.name)
            
            # Verificar tamaño después de limpieza
            current_size = os.path.getsize(step2.name) / (1024 * 1024)
            output_pdf = 'output.pdf'
            
            # Para archivos pequeños, usar conversión a escala de grises de alta calidad
            if current_size <= max_size_mb:
                print(f"El archivo es menor a {max_size_mb}MB ({current_size:.2f}MB), usando conversión de alta calidad.")
                print("4. Convirtiendo a escala de grises (modo alta calidad)...")
                ensure_grayscale(step2.name, output_pdf, preserve_quality=True)
                success = True
            else:
                print(f"El archivo es mayor a {max_size_mb}MB ({current_size:.2f}MB), aplicando conversión estándar.")
                print("4. Convirtiendo a escala de grises...")
                ensure_grayscale(step2.name, step3.name)
                
                print("5. Optimizando con compresión a 300 DPI...")
                success = aggressive_compress(step3.name, output_pdf)
            
            if not success:
                print("\nADVERTENCIA: No se pudo reducir el PDF a menos de 3MB manteniendo la calidad.")
                print("Considere estas opciones:")
                print("1. Intente eliminar manualmente páginas innecesarias")
                print("2. Divida el documento en partes más pequeñas")
                print("3. Pruebe con una herramienta de PDF diferente")
                
            final_size = os.path.getsize(output_pdf) / (1024 * 1024)
            print(f"\nTamaño final del archivo: {final_size:.2f}MB")
            
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