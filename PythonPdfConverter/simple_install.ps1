# Simple script to install required PDF tools
# Run this script as Administrator

Write-Host "Installing required PDF tools for PDF Converter..." -ForegroundColor Cyan
Write-Host "This script will download and install several tools." -ForegroundColor Yellow
Write-Host "Please be patient as this may take a few minutes." -ForegroundColor Yellow
Write-Host ""

# Create a directory for downloads
$toolsDir = "C:\pdf-tools"
$downloadsDir = "$toolsDir\downloads"

# Create directories
if (-not (Test-Path $toolsDir)) {
    New-Item -Path $toolsDir -ItemType Directory -Force | Out-Null
}
if (-not (Test-Path $downloadsDir)) {
    New-Item -Path $downloadsDir -ItemType Directory -Force | Out-Null
}

# 1. Install Ghostscript
Write-Host "1. Installing Ghostscript..." -ForegroundColor Cyan
$gsInstallerUrl = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10011/gs10011w64.exe"
$gsInstallerPath = "$downloadsDir\ghostscript-installer.exe"

# Download
Write-Host "   Downloading Ghostscript..." -ForegroundColor Gray
Invoke-WebRequest -Uri $gsInstallerUrl -OutFile $gsInstallerPath

# Install
Write-Host "   Installing Ghostscript..." -ForegroundColor Gray
Start-Process -FilePath $gsInstallerPath -ArgumentList "/S" -Wait

# Add to PATH
$gsPath = "C:\Program Files\gs\gs10.01.1\bin"
if (Test-Path $gsPath) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if (-not ($currentPath -split ";" -contains $gsPath)) {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$gsPath", [EnvironmentVariableTarget]::User)
        $env:Path = "$env:Path;$gsPath"
    }
}

# 2. Install PDFTK
Write-Host "2. Installing PDFTK..." -ForegroundColor Cyan
$pdftkInstallerUrl = "https://www.pdflabs.com/tools/pdftk-the-pdf-toolkit/pdftk_free-2.02-win-setup.exe"
$pdftkInstallerPath = "$downloadsDir\pdftk-installer.exe"

# Download
Write-Host "   Downloading PDFTK..." -ForegroundColor Gray
Invoke-WebRequest -Uri $pdftkInstallerUrl -OutFile $pdftkInstallerPath

# Install
Write-Host "   Installing PDFTK..." -ForegroundColor Gray
Start-Process -FilePath $pdftkInstallerPath -ArgumentList "/VERYSILENT" -Wait

# Add to PATH
$pdftkPath = "C:\Program Files (x86)\PDFtk\bin"
if (Test-Path $pdftkPath) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if (-not ($currentPath -split ";" -contains $pdftkPath)) {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$pdftkPath", [EnvironmentVariableTarget]::User)
        $env:Path = "$env:Path;$pdftkPath"
    }
}

# 3. Install QPDF
Write-Host "3. Installing QPDF..." -ForegroundColor Cyan
$qpdfUrl = "https://github.com/qpdf/qpdf/releases/download/release-qpdf-10.6.3/qpdf-10.6.3-bin-mingw64.zip"
$qpdfZipPath = "$downloadsDir\qpdf.zip"
$qpdfExtractPath = "$toolsDir\qpdf"

# Download
Write-Host "   Downloading QPDF..." -ForegroundColor Gray
Invoke-WebRequest -Uri $qpdfUrl -OutFile $qpdfZipPath

# Extract
Write-Host "   Extracting QPDF..." -ForegroundColor Gray
if (Test-Path $qpdfExtractPath) {
    Remove-Item -Path $qpdfExtractPath -Recurse -Force
}
Expand-Archive -Path $qpdfZipPath -DestinationPath $qpdfExtractPath

# Add to PATH
$qpdfBinPath = "$qpdfExtractPath\qpdf-10.6.3\bin"
if (Test-Path $qpdfBinPath) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if (-not ($currentPath -split ";" -contains $qpdfBinPath)) {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$qpdfBinPath", [EnvironmentVariableTarget]::User)
        $env:Path = "$env:Path;$qpdfBinPath"
    }
}

# 4. Install Poppler Utils
Write-Host "4. Installing Poppler Utils..." -ForegroundColor Cyan
$popplerUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.05.0-0/Release-23.05.0-0.zip"
$popplerZipPath = "$downloadsDir\poppler.zip"
$popplerExtractPath = "$toolsDir\poppler"

# Download
Write-Host "   Downloading Poppler Utils..." -ForegroundColor Gray
Invoke-WebRequest -Uri $popplerUrl -OutFile $popplerZipPath

# Extract
Write-Host "   Extracting Poppler Utils..." -ForegroundColor Gray
if (Test-Path $popplerExtractPath) {
    Remove-Item -Path $popplerExtractPath -Recurse -Force
}
Expand-Archive -Path $popplerZipPath -DestinationPath $popplerExtractPath

# Add to PATH
$popplerBinPath = "$popplerExtractPath\poppler-23.05.0\Library\bin"
if (Test-Path $popplerBinPath) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if (-not ($currentPath -split ";" -contains $popplerBinPath)) {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$popplerBinPath", [EnvironmentVariableTarget]::User)
        $env:Path = "$env:Path;$popplerBinPath"
    }
}

# 5. Install Python packages
Write-Host "5. Installing Python packages..." -ForegroundColor Cyan
pip install PyPDF2 pdfplumber PyMuPDF Pillow pdf2image img2pdf

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "Please restart your PowerShell session to update your PATH" -ForegroundColor Yellow
Write-Host "Then run check_tools.ps1 to verify all tools are installed correctly" -ForegroundColor Yellow 