# PDF Converter and Validator

Tools for converting and validating PDFs to meet specific requirements:
- File size under 3MB
- Grayscale (8-bit)
- 300 DPI resolution
- No forms, JavaScript, or embedded objects
- No blank pages

## System Dependencies

These tools require several system utilities:

### For Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils ghostscript imagemagick pdftk qpdf
```

### For Fedora/RHEL/CentOS:
```bash
sudo dnf install -y poppler-utils ghostscript ImageMagick pdftk qpdf
```

### For macOS (using Homebrew):
```bash
brew install poppler ghostscript imagemagick pdftk qpdf
```

## Python Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Usage

### PDF Converter

Converts a PDF to meet the requirements:

```bash
python pdf_converter.py input.pdf
# Output will be saved as output.pdf
```

### PDF Validator

Validates if a PDF meets the requirements:

```bash
python pdf_validator.py input.pdf
```

## Notes

- The converter uses a multi-step approach to preserve quality while meeting requirements
- If the PDF cannot be compressed below 3MB, the tool will provide suggestions
- The validator performs detailed checks and provides specific feedback on issues 