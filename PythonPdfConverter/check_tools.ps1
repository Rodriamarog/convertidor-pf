# Script to check if all required PDF tools are installed
Write-Host "Checking for required PDF tools..." -ForegroundColor Cyan

$tools = @{
    "gs" = "Ghostscript"
    "pdftk" = "PDF Toolkit"
    "qpdf" = "QPDF"
    "pdftoppm" = "Poppler Utils (pdftoppm)"
    "pdfinfo" = "Poppler Utils (pdfinfo)"
    "pdfimages" = "Poppler Utils (pdfimages)"
}

$missing = @()
$installed = @()

foreach ($tool in $tools.Keys) {
    $exists = $false
    $version = "unknown version"
    
    try {
        $result = Get-Command $tool -ErrorAction Stop
        $exists = $true
        
        # Try to get version info
        if ($tool -eq "gs") {
            try { $version = & gs --version 2>&1 } catch { $version = "unknown version" }
        } 
        elseif ($tool -eq "pdftk") {
            try { 
                $versionOutput = & pdftk --version 2>&1
                if ($versionOutput -match "pdftk\s+(\d+\.\d+\.\d+)") {
                    $version = $matches[1]
                }
            } catch { $version = "unknown version" }
        } 
        elseif ($tool -eq "qpdf") {
            try { 
                $versionOutput = & qpdf --version 2>&1
                if ($versionOutput -match "qpdf\s+version\s+(\d+\.\d+\.\d+)") {
                    $version = $matches[1]
                }
            } catch { $version = "unknown version" }
        } 
        elseif ($tool -match "pdf(toppm|info|images)") {
            try { 
                $versionOutput = & $tool -v 2>&1
                if ($versionOutput -match "(\d+\.\d+\.\d+)") {
                    $version = $matches[1]
                }
            } catch { $version = "unknown version" }
        }
        
        Write-Host "✓ $($tools[$tool]) is installed" -ForegroundColor Green
        if ($version -ne "unknown version") {
            Write-Host "  Version: $version" -ForegroundColor Gray
        }
        Write-Host "  Path: $($result.Source)" -ForegroundColor Gray
        $installed += $tool
    } 
    catch {
        Write-Host "✗ $($tools[$tool]) is NOT installed" -ForegroundColor Red
        $missing += $tool
    }
}

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "--------" -ForegroundColor Cyan
Write-Host "Installed: $($installed.Count)/$($tools.Count)" -ForegroundColor $(if ($installed.Count -eq $tools.Count) { "Green" } else { "Yellow" })

if ($missing.Count -gt 0) {
    Write-Host "Missing tools: $($missing -join ', ')" -ForegroundColor Red
    
    Write-Host "`nInstallation Instructions:" -ForegroundColor Cyan
    Write-Host "------------------------" -ForegroundColor Cyan
    
    if ($missing -contains "gs") {
        Write-Host "Ghostscript (gs):" -ForegroundColor Yellow
        Write-Host "  1. Download from: https://www.ghostscript.com/releases/gsdnld.html" -ForegroundColor Gray
        Write-Host "  2. Run the installer and follow the instructions" -ForegroundColor Gray
        Write-Host "  3. Add the bin directory to your PATH" -ForegroundColor Gray
    }
    
    if ($missing -contains "pdftk") {
        Write-Host "PDF Toolkit (pdftk):" -ForegroundColor Yellow
        Write-Host "  1. Download from: https://www.pdflabs.com/tools/pdftk-the-pdf-toolkit/" -ForegroundColor Gray
        Write-Host "  2. Run the installer and follow the instructions" -ForegroundColor Gray
        Write-Host "  3. Add the bin directory to your PATH" -ForegroundColor Gray
    }
    
    if ($missing -contains "qpdf") {
        Write-Host "QPDF:" -ForegroundColor Yellow
        Write-Host "  1. Download from: https://github.com/qpdf/qpdf/releases" -ForegroundColor Gray
        Write-Host "  2. Extract the ZIP file to a directory" -ForegroundColor Gray
        Write-Host "  3. Add the bin directory to your PATH" -ForegroundColor Gray
    }
    
    if (($missing -contains "pdftoppm") -or ($missing -contains "pdfinfo") -or ($missing -contains "pdfimages")) {
        Write-Host "Poppler Utils:" -ForegroundColor Yellow
        Write-Host "  1. Download from: https://github.com/oschwartz10612/poppler-windows/releases" -ForegroundColor Gray
        Write-Host "  2. Extract the ZIP file to a directory" -ForegroundColor Gray
        Write-Host "  3. Add the bin directory to your PATH" -ForegroundColor Gray
    }
} 
else {
    Write-Host "All required tools are installed!" -ForegroundColor Green
}

# Check Python packages
Write-Host "`nChecking Python packages..." -ForegroundColor Cyan
$pythonPackages = @{
    "PyPDF2" = "PyPDF2"
    "pdfplumber" = "pdfplumber"
    "fitz" = "PyMuPDF"
    "PIL" = "Pillow"
}

$missingPackages = @()
$installedPackages = @()

foreach ($package in $pythonPackages.Keys) {
    $cmd = "import $package; print('$package is installed')"
    $result = ""
    
    try {
        $result = python -c $cmd 2>&1
        if ($result -match "is installed") {
            Write-Host "✓ $($pythonPackages[$package]) is installed" -ForegroundColor Green
            $installedPackages += $package
        } 
        else {
            Write-Host "✗ $($pythonPackages[$package]) is NOT installed" -ForegroundColor Red
            $missingPackages += $package
        }
    } 
    catch {
        Write-Host "✗ $($pythonPackages[$package]) is NOT installed" -ForegroundColor Red
        $missingPackages += $package
    }
}

Write-Host "`nPython Packages Summary:" -ForegroundColor Cyan
Write-Host "----------------------" -ForegroundColor Cyan
Write-Host "Installed: $($installedPackages.Count)/$($pythonPackages.Count)" -ForegroundColor $(if ($installedPackages.Count -eq $pythonPackages.Count) { "Green" } else { "Yellow" })

if ($missingPackages.Count -gt 0) {
    Write-Host "Missing packages: $($missingPackages -join ', ')" -ForegroundColor Red
    Write-Host "`nInstall missing packages with:" -ForegroundColor Yellow
    Write-Host "  pip install PyPDF2 pdfplumber PyMuPDF Pillow" -ForegroundColor Gray
} 
else {
    Write-Host "All required Python packages are installed!" -ForegroundColor Green
}

# Final verdict
Write-Host "`nFinal Verdict:" -ForegroundColor Cyan
Write-Host "-------------" -ForegroundColor Cyan
if (($missing.Count -eq 0) -and ($missingPackages.Count -eq 0)) {
    Write-Host "Your system is ready to run the PDF converter application!" -ForegroundColor Green
} 
else {
    Write-Host "Your system is missing some required dependencies." -ForegroundColor Red
    Write-Host "Please install the missing tools and packages before running the application." -ForegroundColor Yellow
    Write-Host "`nRun the install_tools.ps1 script as Administrator to install missing tools:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File install_tools.ps1" -ForegroundColor Gray
} 