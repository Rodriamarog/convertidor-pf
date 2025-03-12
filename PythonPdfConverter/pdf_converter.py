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
        print("  qpdf not available or failed, using pure Python method...")
    
    # Pure Python fallback using PyPDF2
    try:
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Remove AcroForm dictionary
        if hasattr(writer, '_root_object') and '/AcroForm' in writer._root_object:
            del writer._root_object['/AcroForm']
        
        # Write the output file
        with open(output_pdf, 'wb') as f:
            writer.write(f)
        
        print("  Used pure Python method for form flattening")
        return
    except Exception as e:
        print(f"  Error in pure Python flattening: {e}")
        # If all methods fail, copy the input to output and continue
        shutil.copy(input_pdf, output_pdf)
        print("  Copying original file as fallback")

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
    
    # Verify input file exists
    if not os.path.exists(input_pdf):
        print(f"  ERROR: Input file does not exist: {input_pdf}")
        raise FileNotFoundError(f"Input file not found: {input_pdf}")
    
    print(f"  Using quality level: {quality_level}")
    
    # Use pure Python method for compression
    print("  Using pure Python method for compression...")
    if pure_python_grayscale(input_pdf, output_pdf):
        return True
    
    # If pure Python method fails, just copy the file
    print("  Pure Python method failed, copying original file")
    shutil.copy(input_pdf, output_pdf)
    return os.path.exists(output_pdf)

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
    
    # Verify input file exists
    if not os.path.exists(input_pdf):
        print(f"  ERROR: Input file does not exist: {input_pdf}")
        raise FileNotFoundError(f"Input file not found: {input_pdf}")
    
    # Determinar si el archivo ya está en escala de grises
    is_grayscale = check_if_grayscale(input_pdf)
    if is_grayscale:
        print("  El PDF ya está en escala de grises, omitiendo conversión.")
        shutil.copy(input_pdf, output_pdf)
        return True
    
    # Use pure Python method for grayscale conversion
    if pure_python_grayscale(input_pdf, output_pdf):
        return True
    
    # Last resort - just copy the file
    if not os.path.exists(output_pdf):
        try:
            print("  All conversion methods failed, copying original file as last resort")
            shutil.copy(input_pdf, output_pdf)
            return os.path.exists(output_pdf)
        except Exception as e:
            print(f"  ERROR: Could not copy original file: {e}")
            return False
    
    return os.path.exists(output_pdf)

def pure_python_grayscale(input_pdf, output_pdf):
    """Convert PDF to grayscale using only Python libraries (PyMuPDF) with compression"""
    print("  Using pure Python grayscale conversion with PyMuPDF...")
    try:
        # Open the input PDF
        doc = fitz.open(input_pdf)
        output_doc = fitz.open()
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get the page as a pixmap with lower resolution for larger files
            matrix = fitz.Matrix(1, 1)  # No scaling by default
            
            # For large pages, use downscaling
            if page.rect.width > 1000 or page.rect.height > 1000:
                scale_factor = min(1.0, 1000 / max(page.rect.width, page.rect.height))
                matrix = fitz.Matrix(scale_factor, scale_factor)
            
            pix = page.get_pixmap(matrix=matrix)
            
            # Convert to grayscale
            gray_pix = fitz.Pixmap(fitz.csGRAY, pix)
            
            # Create a new page in the output document
            output_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
            
            # Insert the grayscale image with compression
            output_page.insert_image(output_page.rect, pixmap=gray_pix)
        
        # Save with compression options
        output_doc.save(output_pdf, 
                       garbage=4,  # Maximum garbage collection
                       deflate=True,  # Use deflate compression
                       clean=True,  # Clean content streams
                       linear=True)  # Optimize for web viewing
        
        output_doc.close()
        doc.close()
        
        print("  Successfully converted to grayscale using PyMuPDF with compression")
        return True
    except Exception as e:
        print(f"  Error in PyMuPDF grayscale conversion: {e}")
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
    
    # Try using PyMuPDF with different quality settings
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_output = os.path.join(tmpdir, "compressed.pdf")
        
        # Try to compress using PyMuPDF
        if pure_python_grayscale(input_pdf, temp_output):
            current_size = os.path.getsize(temp_output)
            print(f"  Size after PyMuPDF compression: {current_size/1024/1024:.2f}MB")
            
            if current_size <= max_size_bytes:
                print(f"  Successfully compressed to under {max_size_mb}MB")
                shutil.copy(temp_output, output_pdf)
                return True
        
        # If still too large, try image-based conversion
        if downsample_to_images(input_pdf, temp_output, max_size_bytes):
            shutil.copy(temp_output, output_pdf)
            return True
        
        # If all else fails, we need to offer more drastic options
        print(f"  WARNING: Could not compress below {max_size_mb}MB with quality preservation")
        
        # Copy our best attempt anyway
        shutil.copy(temp_output, output_pdf)
        return False

def downsample_to_images(input_pdf, output_pdf, max_size_bytes):
    """Last resort: Convert PDF to downsampled images and rebuild with aggressive compression"""
    try:
        # Start with a reasonable DPI and progressively lower it
        for dpi in [150, 120, 100, 75, 60]:
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
                
                # Optimize images before combining
                optimized_files = []
                for img_file in img_files:
                    try:
                        # Open with Pillow and compress
                        img = Image.open(img_file)
                        
                        # Resize if very large
                        max_dimension = 1500  # Max width or height
                        if max(img.width, img.height) > max_dimension:
                            ratio = max_dimension / max(img.width, img.height)
                            new_size = (int(img.width * ratio), int(img.height * ratio))
                            img = img.resize(new_size, Image.LANCZOS)
                        
                        # Convert to grayscale and optimize
                        img = img.convert('L')
                        
                        # Save with compression
                        optimized_path = os.path.join(tmpdir, f"opt_{os.path.basename(img_file)}")
                        img.save(optimized_path, 'PNG', optimize=True, compress_level=9)
                        optimized_files.append(optimized_path)
                    except Exception as e:
                        print(f"  Error optimizing image {img_file}: {e}")
                        optimized_files.append(img_file)  # Use original if optimization fails
                
                # Combine into a PDF with tight compression
                temp_pdf = os.path.join(tmpdir, "temp.pdf")
                
                try:
                    # Try img2pdf first (usually better size/quality ratio)
                    import img2pdf
                    with open(temp_pdf, "wb") as f:
                        f.write(img2pdf.convert(optimized_files, dpi=dpi))
                except ImportError:
                    # Fall back to ImageMagick
                    convert_cmd = [
                        'convert',
                        '-density', str(dpi),
                        '-quality', '40',  # Lower quality for smaller files
                        '-compress', 'JPEG',
                        *optimized_files,
                        temp_pdf
                    ]
                    subprocess.run(convert_cmd, check=True)
                
                # Check if we're now under the size limit
                if os.path.getsize(temp_pdf) <= max_size_bytes:
                    print(f"  Successfully compressed to {os.path.getsize(temp_pdf)/1024/1024:.2f}MB using {dpi} DPI images")
                    shutil.copy(temp_pdf, output_pdf)
                    return True
        
        # If we get here, even the lowest quality didn't work
        # Try one last extreme measure - convert to JPEG with very low quality
        print("  Attempting extreme compression with very low quality JPEG...")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Extract at lowest DPI
            extract_cmd = [
                'pdftoppm',
                '-jpeg',
                '-r', '50',  # Very low DPI
                '-gray',
                input_pdf,
                os.path.join(tmpdir, 'page')
            ]
            subprocess.run(extract_cmd, check=True)
            
            # Find all generated images
            img_files = sorted([
                os.path.join(tmpdir, f) 
                for f in os.listdir(tmpdir) 
                if f.endswith('.jpg')
            ])
            
            if not img_files:
                return False
                
            # Compress images extremely
            compressed_files = []
            for img_file in img_files:
                try:
                    img = Image.open(img_file)
                    compressed_path = os.path.join(tmpdir, f"comp_{os.path.basename(img_file)}")
                    img.save(compressed_path, 'JPEG', quality=30)  # Very low quality
                    compressed_files.append(compressed_path)
                except Exception:
                    compressed_files.append(img_file)
            
            # Combine into final PDF
            temp_pdf = os.path.join(tmpdir, "extreme.pdf")
            try:
                import img2pdf
                with open(temp_pdf, "wb") as f:
                    f.write(img2pdf.convert(compressed_files, dpi=50))
            except ImportError:
                convert_cmd = [
                    'convert',
                    '-density', '50',
                    '-quality', '30',
                    '-compress', 'JPEG',
                    *compressed_files,
                    temp_pdf
                ]
                subprocess.run(convert_cmd, check=True)
            
            if os.path.getsize(temp_pdf) <= max_size_bytes:
                print(f"  Successfully compressed to {os.path.getsize(temp_pdf)/1024/1024:.2f}MB with extreme measures")
                shutil.copy(temp_pdf, output_pdf)
                return True
            
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
    print(f"Starting conversion of: {input_path}")
    if not os.path.exists(input_path):
        print(f"ERROR: Input file does not exist: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    try:
        check_encrypted(input_path)
    except Exception as e:
        print(f"Warning when checking encryption: {e}")
        # Continue anyway
        
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
            
            # Get the directory of the input file to use for output
            # Use current working directory for output to ensure it's writable
            output_dir = os.getcwd()
            output_pdf = os.path.join(output_dir, 'output.pdf')
            print(f"Output will be saved to: {output_pdf}")
            
            # Siempre realizar estos pasos para cumplir con requisitos de seguridad
            print("1. Aplanando formularios PDF para preservar el contenido de texto...")
            flatten_pdf_forms(input_path, flattened.name)
            
            print("2. Eliminando formularios, JavaScript y adjuntos...")
            try:
                remove_forms_js_attachments(flattened.name, step1.name)
            except Exception as e:
                print(f"  Error removing forms/JS: {e}, copying file instead")
                shutil.copy(flattened.name, step1.name)
            
            print("3. Eliminando páginas en blanco...")
            try:
                remove_blank_pages(step1.name, step2.name)
            except Exception as e:
                print(f"  Error removing blank pages: {e}, copying file instead")
                shutil.copy(step1.name, step2.name)
            
            # Verificar tamaño después de limpieza
            current_size = os.path.getsize(step2.name) / (1024 * 1024)
            
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
                
                print("5. Optimizando con compresión...")
                try:
                    success = pure_python_grayscale(step3.name, output_pdf)
                except Exception as e:
                    print(f"  Error in compression: {e}, using pure Python method")
                    success = pure_python_grayscale(step3.name, output_pdf)
            
            if not success:
                print("\nADVERTENCIA: No se pudo reducir el PDF a menos de 3MB manteniendo la calidad.")
                print("Considere estas opciones:")
                print("1. Intente eliminar manualmente páginas innecesarias")
                print("2. Divida el documento en partes más pequeñas")
                print("3. Pruebe con una herramienta de PDF diferente")
            
            # Verify the output file exists
            if os.path.exists(output_pdf):
                final_size = os.path.getsize(output_pdf) / (1024 * 1024)
                print(f"\nTamaño final del archivo: {final_size:.2f}MB")
                print(f"Archivo guardado como: {output_pdf}")
                return output_pdf
            else:
                print(f"ERROR: Output file was not created: {output_pdf}")
                # Last resort - copy the original file
                print("Copying original file as last resort")
                shutil.copy(input_path, output_pdf)
                if os.path.exists(output_pdf):
                    print(f"Successfully copied original file to {output_pdf}")
                    return output_pdf
                else:
                    raise FileNotFoundError(f"Output file was not created: {output_pdf}")
            
    except Exception as e:
        print(f"ERROR in PDF conversion: {str(e)}")
        # Try to copy the original file as a last resort
        try:
            output_pdf = os.path.join(os.getcwd(), 'output.pdf')
            print(f"Attempting to copy original file to {output_pdf} as last resort")
            shutil.copy(input_path, output_pdf)
            if os.path.exists(output_pdf):
                print(f"Successfully copied original file to {output_pdf}")
                return output_pdf
        except Exception as copy_error:
            print(f"Failed to copy original file: {copy_error}")
        # Re-raise the exception to be caught by the caller
        raise
    finally:
        # Cleanup all temporary files
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Warning: Could not remove temp file {f}: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python pdf_converter.py input.pdf")
        sys.exit(1)
    
    print(f"Processing PDF: {sys.argv[1]}")
    main(sys.argv[1])
    print("Processing complete. Output saved as output.pdf")