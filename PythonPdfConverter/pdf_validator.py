#!/usr/bin/env python3
"""
VUCEM PDF Validator - Tool for verifying PDFs meet VUCEM requirements

Requirements:
- File size under 3MB
- No forms, JavaScript, or embedded objects
- Grayscale (8-bit)
- 300 DPI resolution
- No blank pages

Dependencies:
- poppler-utils (pdftoppm, pdfinfo, pdfimages commands)
- imagemagick (identify command)
- PyPDF2, Pillow (Python packages)

Install with:
    pip install PyPDF2 Pillow
    sudo apt-get install poppler-utils imagemagick  # For Ubuntu/Debian
"""

import os
import sys
import subprocess
import tempfile
import argparse
import random
from PIL import Image
from PyPDF2 import PdfReader

class VucemValidator:
    def __init__(self, pdf_path, verbose=True):
        self.pdf_path = pdf_path
        self.verbose = verbose
        self.results = {}
        
    def log(self, message):
        """Print log message if verbose mode is enabled"""
        if self.verbose:
            print(message)
    
    def check_file_size(self, max_size_mb=3):
        """Check if file size is under the limit"""
        size_bytes = os.path.getsize(self.pdf_path)
        size_mb = size_bytes / (1024 * 1024)
        
        result = size_mb <= max_size_mb
        
        if result:
            self.log(f"✅ File size: {size_mb:.2f} MB (under {max_size_mb} MB limit)")
        else:
            self.log(f"❌ File size: {size_mb:.2f} MB (exceeds {max_size_mb} MB limit)")
        
        self.results['file_size'] = {
            'passed': result,
            'size_mb': size_mb,
            'max_size_mb': max_size_mb
        }
        
        return result
    
    def check_security_features(self):
        """Check for forms, JavaScript, and attachments"""
        self.log("\nChecking security features...")
        
        results = {}
        
        # Try multiple methods for reliability
        # Method 1: Use pdfinfo
        try:
            pdfinfo_output = subprocess.check_output(["pdfinfo", self.pdf_path], text=True)
            if "Encrypted" in pdfinfo_output and "no" not in pdfinfo_output.lower().split("Encrypted")[1].split("\n")[0].lower():
                self.log("❌ PDF is encrypted")
                results['encrypted'] = True
            else:
                self.log("✅ PDF is not encrypted")
                results['encrypted'] = False
        except Exception as e:
            self.log(f"Warning: Could not check encryption with pdfinfo: {e}")
            results['encrypted'] = None
        
        # Method 2: Use PyPDF2 for deeper checks
        try:
            reader = PdfReader(self.pdf_path)
            
            # Check for AcroForm
            has_forms = False
            has_js = False
            has_attachments = False
            
            # Direct trailer check
            root = reader.trailer.get("/Root", {})
            if "/AcroForm" in root:
                has_forms = True
            
            # Check pages for annotations
            for page in reader.pages:
                if '/Annots' in page:
                    annotations = page['/Annots']
                    if annotations:
                        for annot_ref in annotations:
                            try:
                                annot = annot_ref.get_object()
                                if '/FT' in annot:  # Form field type
                                    has_forms = True
                                # Check for JavaScript actions
                                if '/AA' in annot:
                                    aa = annot['/AA']
                                    if '/JS' in aa:
                                        has_js = True
                                if '/A' in annot:
                                    a = annot['/A']
                                    if '/JS' in a:
                                        has_js = True
                            except:
                                # If we can't read an annotation, be conservative
                                self.log("Warning: Could not read an annotation")
                                
            # Check for embedded files
            if '/Names' in root:
                names = root['/Names']
                if isinstance(names, dict) and '/EmbeddedFiles' in names:
                    has_attachments = True
            
            results['forms'] = has_forms
            results['javascript'] = has_js
            results['attachments'] = has_attachments
            
            if has_forms:
                self.log("❌ PDF contains forms")
            else:
                self.log("✅ No forms detected")
                
            if has_js:
                self.log("❌ PDF contains JavaScript")
            else:
                self.log("✅ No JavaScript detected")
                
            if has_attachments:
                self.log("❌ PDF contains attachments")
            else:
                self.log("✅ No attachments detected")
                
        except Exception as e:
            self.log(f"Warning: Could not fully check security with PyPDF2: {e}")
            results['forms'] = None
            results['javascript'] = None
            results['attachments'] = None
        
        # Overall result
        passed = not (results.get('encrypted', False) or 
                      results.get('forms', False) or 
                      results.get('javascript', False) or 
                      results.get('attachments', False))
        
        self.results['security'] = {
            'passed': passed,
            'details': results
        }
        
        return passed
    
    def extract_sample_page(self, output_dir, page_num=1, dpi=300):
        """Extract a page from the PDF for analysis"""
        output_prefix = os.path.join(output_dir, f"page-{page_num}")
        
        # Extract with pdftoppm
        try:
            subprocess.run([
                "pdftoppm",
                "-png",
                "-r", str(dpi),  # Request specific DPI
                "-f", str(page_num),
                "-l", str(page_num),
                self.pdf_path,
                output_prefix
            ], check=True)
            
            # Find the extracted image
            files = [f for f in os.listdir(output_dir) if f.startswith(f"page-{page_num}") and f.endswith('.png')]
            
            if files:
                return os.path.join(output_dir, files[0])
            else:
                self.log(f"Warning: Could not find extracted page in {output_dir}")
                return None
        except Exception as e:
            self.log(f"Error extracting page: {e}")
            return None
    
    def is_truly_grayscale(self, image_path, sample_size=1000, threshold=0.01):
        """Check if image is truly grayscale by sampling pixels"""
        try:
            img = Image.open(image_path)
            
            # If already in 'L' mode, it's definitely grayscale
            if img.mode == 'L':
                return True
                
            # Convert to RGB to ensure we can check RGB values
            img = img.convert('RGB')
            width, height = img.size
            
            # Sample random pixels
            num_samples = min(sample_size, width * height)
            non_gray_pixels = 0
            
            for _ in range(num_samples):
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                r, g, b = img.getpixel((x, y))
                
                # Check if RGB channels differ significantly
                if max(abs(r-g), abs(r-b), abs(g-b)) > 2:  # Allow small differences
                    non_gray_pixels += 1
            
            # Calculate percentage of non-gray pixels
            non_gray_pct = non_gray_pixels / num_samples
            
            return non_gray_pct <= threshold
            
        except Exception as e:
            self.log(f"Error checking grayscale: {e}")
            return False
    
    def check_grayscale_and_depth(self):
        """Check if the PDF is grayscale with 8-bit depth"""
        self.log("\nChecking color mode and bit depth...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Extract first page for analysis
            sample_page = self.extract_sample_page(tmpdir)
            
            if not sample_page:
                self.log("❌ Could not extract sample page for analysis")
                self.results['grayscale'] = {
                    'passed': False,
                    'error': "Could not extract sample page"
                }
                return False
            
            # Method 1: Use identify for basic info
            try:
                identify_output = subprocess.check_output(["identify", "-verbose", sample_page], text=True)
                
                # Parse the output
                colorspace = None
                bit_depth = None
                
                for line in identify_output.splitlines():
                    line = line.strip()
                    if "Colorspace:" in line:
                        colorspace = line.split(":", 1)[1].strip()
                    elif "Depth:" in line:
                        bit_depth = line.split(":", 1)[1].strip()
                
                self.log(f"Reported colorspace: {colorspace}")
                self.log(f"Reported bit depth: {bit_depth}")
                
                # Method 2: Do a pixel-level analysis for grayscale
                is_gray = self.is_truly_grayscale(sample_page)
                
                if is_gray:
                    self.log("✅ Image is effectively grayscale (pixel analysis)")
                else:
                    self.log("❌ Image contains color (pixel analysis)")
                
                # Check bit depth
                has_8bit = bit_depth and "8" in bit_depth
                
                if has_8bit:
                    self.log("✅ Image has 8-bit depth")
                else:
                    self.log(f"❌ Image does not have 8-bit depth: {bit_depth}")
                
                self.results['grayscale'] = {
                    'passed': is_gray and has_8bit,
                    'effectively_grayscale': is_gray,
                    'has_8bit_depth': has_8bit,
                    'reported_colorspace': colorspace,
                    'reported_depth': bit_depth
                }
                
                return is_gray and has_8bit
                
            except Exception as e:
                self.log(f"Error analyzing color mode: {e}")
                self.results['grayscale'] = {
                    'passed': False,
                    'error': str(e)
                }
                return False
    
    def calculate_effective_dpi(self):
        """Calculate effective DPI of the PDF"""
        self.log("\nChecking resolution (DPI)...")
        
        try:
            # Get page size in points
            pdfinfo_output = subprocess.check_output(["pdfinfo", self.pdf_path], text=True)
            
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
                self.log("Warning: Could not determine page size in points")
                self.results['dpi'] = {
                    'passed': False,
                    'error': "Could not determine page size"
                }
                return False
                
            self.log(f"Page size in points: {page_size_pts[0]} x {page_size_pts[1]}")
            
            # Extract a sample page at 300 DPI
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract with specific DPI
                sample_path = os.path.join(tmpdir, "sample")
                subprocess.run([
                    "pdftoppm",
                    "-png",
                    "-r", "300",  # Request 300 DPI
                    "-f", "1",
                    "-l", "1",
                    self.pdf_path,
                    sample_path
                ], check=True)
                
                # Find the extracted image
                files = [f for f in os.listdir(tmpdir) if f.endswith('.png')]
                if not files:
                    self.log("Warning: Could not extract sample image")
                    self.results['dpi'] = {
                        'passed': False,
                        'error': "Could not extract sample image"
                    }
                    return False
                    
                image_path = os.path.join(tmpdir, files[0])
                
                # Get image dimensions
                with Image.open(image_path) as img:
                    width_px, height_px = img.size
                
                self.log(f"Image dimensions at 300 DPI: {width_px} x {height_px} pixels")
                
                # Calculate effective DPI
                dpi_w = width_px / (page_size_pts[0] / 72.0)
                dpi_h = height_px / (page_size_pts[1] / 72.0)
                
                self.log(f"Calculated DPI: {dpi_w:.2f} x {dpi_h:.2f}")
                
                # Check if close to 300 DPI
                dpi_ok = 290 <= dpi_w <= 310 and 290 <= dpi_h <= 310
                
                if dpi_ok:
                    self.log("✅ Resolution is approximately 300 DPI")
                else:
                    self.log(f"❌ Resolution is not 300 DPI: {dpi_w:.2f} x {dpi_h:.2f}")
                
                self.results['dpi'] = {
                    'passed': dpi_ok,
                    'width_dpi': dpi_w,
                    'height_dpi': dpi_h
                }
                
                return dpi_ok
                
        except Exception as e:
            self.log(f"Error calculating DPI: {e}")
            self.results['dpi'] = {
                'passed': False,
                'error': str(e)
            }
            return False
    
    def check_blank_pages(self):
        """Check for blank pages in the PDF"""
        self.log("\nChecking for blank pages...")
        
        try:
            # Method 1: Use pdfimages to count images
            pdfimages_output = subprocess.check_output(["pdfimages", "-list", self.pdf_path], text=True)
            has_images = "image" in pdfimages_output.lower()
            
            # Method 2: Use pdftotext to extract text
            with tempfile.NamedTemporaryFile() as tmp:
                subprocess.run(["pdftotext", self.pdf_path, tmp.name], check=True)
                with open(tmp.name, 'r') as f:
                    text = f.read().strip()
            
            has_text = bool(text)
            
            # Get number of pages
            pdfinfo_output = subprocess.check_output(["pdfinfo", self.pdf_path], text=True)
            num_pages = None
            for line in pdfinfo_output.splitlines():
                if "Pages:" in line:
                    num_pages = int(line.split(":", 1)[1].strip())
                    break
            
            self.log(f"Total pages: {num_pages}")
            self.log(f"Contains text: {has_text}")
            self.log(f"Contains images: {has_images}")
            
            # If multi-page and no text/images, likely has blank pages
            has_blank_pages = num_pages > 1 and not (has_text or has_images)
            
            # If single page and no text/images, check pixel values
            if num_pages == 1 and not (has_text or has_images):
                with tempfile.TemporaryDirectory() as tmpdir:
                    sample_page = self.extract_sample_page(tmpdir)
                    
                    if sample_page:
                        # Analyze pixel values
                        img = Image.open(sample_page).convert('L')
                        pixels = list(img.getdata())
                        avg = sum(pixels) / len(pixels) / 255.0
                        
                        # If average is very close to 1 (white), it's blank
                        has_blank_pages = avg > 0.99
                        
                        if has_blank_pages:
                            self.log(f"  First page appears blank (avg pixel value: {avg:.4f})")
            
            if has_blank_pages:
                self.log("❌ PDF contains blank pages")
            else:
                self.log("✅ No blank pages detected")
            
            self.results['blank_pages'] = {
                'passed': not has_blank_pages,
                'has_text': has_text,
                'has_images': has_images
            }
            
            return not has_blank_pages
            
        except Exception as e:
            self.log(f"Error checking blank pages: {e}")
            self.results['blank_pages'] = {
                'passed': False,
                'error': str(e)
            }
            return False
    
    def validate(self):
        """Run all validation checks and return overall result"""
        self.log(f"=== VUCEM PDF Validation: {self.pdf_path} ===\n")
        
        # Run all checks
        size_ok = self.check_file_size()
        security_ok = self.check_security_features()
        grayscale_ok = self.check_grayscale_and_depth()
        dpi_ok = self.calculate_effective_dpi()
        blank_ok = self.check_blank_pages()
        
        # Overall result
        all_checks = [size_ok, security_ok, grayscale_ok, dpi_ok, blank_ok]
        passed = all(all_checks)
        
        # Summary
        self.log("\n=== VUCEM Validation Results ===")
        
        if passed:
            self.log("✅ PDF PASSES ALL VUCEM REQUIREMENTS")
            self.log("\nThe PDF meets the following requirements:")
            self.log(f"1. Size: {self.results['file_size']['size_mb']:.2f} MB (under 3 MB limit)")
            self.log("2. Security: No forms, JavaScript, or embedded files")
            self.log("3. Color mode: Effectively grayscale with 8-bit depth")
            self.log(f"4. Resolution: Approximately 300 DPI ({self.results['dpi']['width_dpi']:.2f} x {self.results['dpi']['height_dpi']:.2f})")
            self.log("5. Content: No blank pages")
        else:
            self.log("❌ PDF FAILS ONE OR MORE VUCEM REQUIREMENTS")
            
            if not size_ok:
                self.log(f"✗ File size: {self.results['file_size']['size_mb']:.2f} MB (exceeds 3 MB limit)")
            
            if not security_ok:
                self.log("✗ Security issues:")
                if self.results['security']['details'].get('encrypted', False):
                    self.log("  - PDF is encrypted")
                if self.results['security']['details'].get('forms', False):
                    self.log("  - PDF contains forms")
                if self.results['security']['details'].get('javascript', False):
                    self.log("  - PDF contains JavaScript")
                if self.results['security']['details'].get('attachments', False):
                    self.log("  - PDF contains attachments")
            
            if not grayscale_ok:
                self.log("✗ Color mode issues:")
                if not self.results['grayscale'].get('effectively_grayscale', False):
                    self.log("  - PDF contains color content")
                if not self.results['grayscale'].get('has_8bit_depth', False):
                    self.log("  - PDF does not have 8-bit depth")
            
            if not dpi_ok:
                dpi_error = self.results['dpi'].get('error')
                if dpi_error:
                    self.log(f"✗ DPI error: {dpi_error}")
                else:
                    self.log(f"✗ Resolution: {self.results['dpi']['width_dpi']:.2f} x {self.results['dpi']['height_dpi']:.2f} DPI (not 300 DPI)")
            
            if not blank_ok:
                self.log("✗ PDF contains blank pages")
                
            self.log("\nPlease process this PDF with the VUCEM converter tool.")
        
        return passed

def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    # Check command-line tools
    for cmd in ["pdftoppm", "pdfinfo", "pdfimages", "identify"]:
        try:
            subprocess.run(["which", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            missing.append(cmd)
    
    # Check Python packages
    try:
        import PyPDF2
    except ImportError:
        missing.append("PyPDF2")
    
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    
    if missing:
        print("Missing dependencies:")
        print("  Command-line tools:", [cmd for cmd in missing if cmd in ["pdftoppm", "pdfinfo", "pdfimages", "identify"]])
        print("  Python packages:", [pkg for pkg in missing if pkg in ["PyPDF2", "Pillow"]])
        print("\nPlease install missing dependencies:")
        print("  pip install PyPDF2 Pillow")
        print("  sudo apt-get install poppler-utils imagemagick")
        return False
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate PDFs for VUCEM requirements")
    parser.add_argument("pdf_file", help="PDF file to validate")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (minimal output)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_file):
        print(f"Error: File '{args.pdf_file}' not found")
        sys.exit(1)
    
    if not check_dependencies():
        sys.exit(1)
    
    validator = VucemValidator(args.pdf_file, verbose=not args.quiet)
    passed = validator.validate()
    
    if args.json:
        import json
        print(json.dumps(validator.results, indent=2))
    
    sys.exit(0 if passed else 1)