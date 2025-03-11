# Script to install all required PDF tools
# Run this script as Administrator

# Create a directory for downloads
$toolsDir = "C:\pdf-tools"
$downloadsDir = "$toolsDir\downloads"

Write-Host "Creating directories..." -ForegroundColor Cyan
if (-not (Test-Path $toolsDir)) {
    New-Item -Path $toolsDir -ItemType Directory -Force | Out-Null
}
if (-not (Test-Path $downloadsDir)) {
    New-Item -Path $downloadsDir -ItemType Directory -Force | Out-Null
}

# Function to check if a tool is already installed
function Test-CommandExists {
    param ($command)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $command) { return $true }
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

# Install Ghostscript
if (-not (Test-CommandExists "gs")) {
    Write-Host "Installing Ghostscript..." -ForegroundColor Cyan
    $gsInstallerUrl = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10011/gs10011w64.exe"
    $gsInstallerPath = "$downloadsDir\ghostscript-installer.exe"
    
    Write-Host "Downloading Ghostscript installer..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $gsInstallerUrl -OutFile $gsInstallerPath
    
    Write-Host "Running Ghostscript installer..." -ForegroundColor Gray
    Start-Process -FilePath $gsInstallerPath -ArgumentList "/S" -Wait
    
    # Add Ghostscript to PATH
    $gsPath = "C:\Program Files\gs\gs10.01.1\bin"
    if (Test-Path $gsPath) {
        Write-Host "Adding Ghostscript to PATH..." -ForegroundColor Gray
        $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
        if (-not ($currentPath -split ";" -contains $gsPath)) {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$gsPath", [EnvironmentVariableTarget]::User)
            $env:Path = "$env:Path;$gsPath"
        }
    } else {
        Write-Host "Warning: Ghostscript bin directory not found at $gsPath" -ForegroundColor Yellow
        Write-Host "Please add the Ghostscript bin directory to your PATH manually" -ForegroundColor Yellow
    }
    
    # Verify installation
    if (Test-CommandExists "gs") {
        $version = & gs --version 2>&1
        Write-Host "✓ Ghostscript installed successfully (Version: $version)" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to install Ghostscript" -ForegroundColor Red
    }
} else {
    Write-Host "✓ Ghostscript is already installed" -ForegroundColor Green
}

# Install PDFTK
if (-not (Test-CommandExists "pdftk")) {
    Write-Host "Installing PDFTK..." -ForegroundColor Cyan
    $pdftkInstallerUrl = "https://www.pdflabs.com/tools/pdftk-the-pdf-toolkit/pdftk_free-2.02-win-setup.exe"
    $pdftkInstallerPath = "$downloadsDir\pdftk-installer.exe"
    
    Write-Host "Downloading PDFTK installer..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $pdftkInstallerUrl -OutFile $pdftkInstallerPath
    
    Write-Host "Running PDFTK installer..." -ForegroundColor Gray
    Start-Process -FilePath $pdftkInstallerPath -ArgumentList "/VERYSILENT" -Wait
    
    # Add PDFTK to PATH
    $pdftkPath = "C:\Program Files (x86)\PDFtk\bin"
    if (Test-Path $pdftkPath) {
        Write-Host "Adding PDFTK to PATH..." -ForegroundColor Gray
        $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
        if (-not ($currentPath -split ";" -contains $pdftkPath)) {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$pdftkPath", [EnvironmentVariableTarget]::User)
            $env:Path = "$env:Path;$pdftkPath"
        }
    } else {
        Write-Host "Warning: PDFTK bin directory not found at $pdftkPath" -ForegroundColor Yellow
        Write-Host "Please add the PDFTK bin directory to your PATH manually" -ForegroundColor Yellow
    }
    
    # Verify installation
    if (Test-CommandExists "pdftk") {
        Write-Host "✓ PDFTK installed successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to install PDFTK" -ForegroundColor Red
    }
} else {
    Write-Host "✓ PDFTK is already installed" -ForegroundColor Green
}

# Install QPDF
if (-not (Test-CommandExists "qpdf")) {
    Write-Host "Installing QPDF..." -ForegroundColor Cyan
    $qpdfUrl = "https://github.com/qpdf/qpdf/releases/download/release-qpdf-10.6.3/qpdf-10.6.3-bin-mingw64.zip"
    $qpdfZipPath = "$downloadsDir\qpdf.zip"
    $qpdfExtractPath = "$toolsDir\qpdf"
    
    Write-Host "Downloading QPDF..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $qpdfUrl -OutFile $qpdfZipPath
    
    Write-Host "Extracting QPDF..." -ForegroundColor Gray
    if (Test-Path $qpdfExtractPath) {
        Remove-Item -Path $qpdfExtractPath -Recurse -Force
    }
    Expand-Archive -Path $qpdfZipPath -DestinationPath $qpdfExtractPath
    
    # Add QPDF to PATH
    $qpdfBinPath = "$qpdfExtractPath\qpdf-10.6.3\bin"
    if (Test-Path $qpdfBinPath) {
        Write-Host "Adding QPDF to PATH..." -ForegroundColor Gray
        $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
        if (-not ($currentPath -split ";" -contains $qpdfBinPath)) {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$qpdfBinPath", [EnvironmentVariableTarget]::User)
            $env:Path = "$env:Path;$qpdfBinPath"
        }
    } else {
        Write-Host "Warning: QPDF bin directory not found at $qpdfBinPath" -ForegroundColor Yellow
        Write-Host "Please add the QPDF bin directory to your PATH manually" -ForegroundColor Yellow
    }
    
    # Verify installation
    if (Test-CommandExists "qpdf") {
        $version = & qpdf --version 2>&1
        if ($version -match "qpdf\s+version\s+(\d+\.\d+\.\d+)") {
            $version = $matches[1]
        }
        Write-Host "✓ QPDF installed successfully (Version: $version)" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to install QPDF" -ForegroundColor Red
    }
} else {
    Write-Host "✓ QPDF is already installed" -ForegroundColor Green
}

# Install Poppler Utils
if ((-not (Test-CommandExists "pdftoppm")) -or (-not (Test-CommandExists "pdfinfo")) -or (-not (Test-CommandExists "pdfimages"))) {
    Write-Host "Installing Poppler Utils..." -ForegroundColor Cyan
    $popplerUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.05.0-0/Release-23.05.0-0.zip"
    $popplerZipPath = "$downloadsDir\poppler.zip"
    $popplerExtractPath = "$toolsDir\poppler"
    
    Write-Host "Downloading Poppler Utils..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $popplerUrl -OutFile $popplerZipPath
    
    Write-Host "Extracting Poppler Utils..." -ForegroundColor Gray
    if (Test-Path $popplerExtractPath) {
        Remove-Item -Path $popplerExtractPath -Recurse -Force
    }
    Expand-Archive -Path $popplerZipPath -DestinationPath $popplerExtractPath
    
    # Add Poppler to PATH
    $popplerBinPath = "$popplerExtractPath\poppler-23.05.0\Library\bin"
    if (Test-Path $popplerBinPath) {
        Write-Host "Adding Poppler to PATH..." -ForegroundColor Gray
        $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
        if (-not ($currentPath -split ";" -contains $popplerBinPath)) {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$popplerBinPath", [EnvironmentVariableTarget]::User)
            $env:Path = "$env:Path;$popplerBinPath"
        }
    } else {
        Write-Host "Warning: Poppler bin directory not found at $popplerBinPath" -ForegroundColor Yellow
        Write-Host "Please add the Poppler bin directory to your PATH manually" -ForegroundColor Yellow
    }
    
    # Verify installation
    $allInstalled = $true
    foreach ($tool in @("pdftoppm", "pdfinfo", "pdfimages")) {
        if (Test-CommandExists $tool) {
            Write-Host "✓ $tool installed successfully" -ForegroundColor Green
        } else {
            Write-Host "✗ Failed to install $tool" -ForegroundColor Red
            $allInstalled = $false
        }
    }
    
    if ($allInstalled) {
        Write-Host "✓ Poppler Utils installed successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Some Poppler Utils failed to install" -ForegroundColor Red
    }
} else {
    Write-Host "✓ Poppler Utils are already installed" -ForegroundColor Green
}

# Install Python packages
Write-Host "Installing required Python packages..." -ForegroundColor Cyan
Start-Process -FilePath "pip" -ArgumentList "install", "PyPDF2", "pdfplumber", "PyMuPDF", "Pillow" -Wait -NoNewWindow

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "Please restart your PowerShell session or run 'refreshenv' to update your PATH" -ForegroundColor Yellow
Write-Host "Then run check_tools.ps1 to verify all tools are installed correctly" -ForegroundColor Yellow 