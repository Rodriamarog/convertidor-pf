# Windows Server Docker Setup for Windows Containers

This guide covers how to set up Docker for Windows Containers on Windows Server and test a PDF conversion application.

## Prerequisites
- Windows Server 2019 or 2022
- Administrator access
- Internet connection

## Docker Installation

1. Install the Windows Containers feature:
```powershell
Install-WindowsFeature -Name Containers
```

2. Download and install Docker Engine:
```powershell
# Download Docker Engine
Invoke-WebRequest -UseBasicParsing "https://download.docker.com/win/static/stable/x86_64/docker-20.10.9.zip" -OutFile "$env:TEMP\docker.zip"

# Extract Docker files
Expand-Archive -Path "$env:TEMP\docker.zip" -DestinationPath "$env:ProgramFiles" -Force

# Add Docker to system PATH
$env:Path += ";$env:ProgramFiles\docker"
[Environment]::SetEnvironmentVariable("Path", $env:Path, [EnvironmentVariableTarget]::Machine)
```

3. Register and configure Docker service for Windows containers:
```powershell
# Stop any existing Docker service
Stop-Service docker -Force -ErrorAction SilentlyContinue

# Unregister existing service
& "$env:ProgramFiles\docker\dockerd.exe" --unregister-service -ErrorAction SilentlyContinue

# Register Docker service for Windows containers
& "$env:ProgramFiles\docker\dockerd.exe" --register-service --exec-opt isolation=process

# Create Docker configuration
$configJson = @{
  "hosts" = @("npipe:////./pipe/docker_engine")
  "experimental" = $false
} | ConvertTo-Json

New-Item -Path "$env:ProgramData\docker\config" -ItemType Directory -Force
Set-Content -Path "$env:ProgramData\docker\config\daemon.json" -Value $configJson

# Start Docker service
Start-Service docker
```

4. Verify Docker is running correctly:
```powershell
docker version
docker info
```

## Pull and Run the PDF Converter Container

1. Pull the container image:
```powershell
docker pull rodriamarog/pdf-converter:v1
```

2. Run the container:
```powershell
docker run -d -p 5000:5000 --name pdf-converter rodriamarog/pdf-converter:v1
```

3. Verify the container is running:
```powershell
docker ps
```

## Testing the PDF Conversion API

1. Download a sample PDF file:
```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf" -OutFile "C:\test.pdf"
```

2. Convert the PDF using the API:
```powershell
curl.exe -F "file=@C:\test.pdf" http://localhost:5000/api/convert-direct -o C:\converted.pdf
```

3. Verify the conversion was successful:
```powershell
# Check if the converted file exists
Test-Path C:\converted.pdf

# Check the file size
Get-Item C:\converted.pdf | Select-Object Length
```

Here's the updated troubleshooting section:

## Troubleshooting

If Docker doesn't start properly:
```powershell
# Check Docker service status
Get-Service docker

# Check Docker logs
Get-EventLog -LogName System -Source "Service Control Manager" -Newest 10 | Where-Object {$_.Message -like "*docker*"}
```

If the container doesn't start:
```powershell
# Check container logs
docker logs pdf-converter
```

If you encounter a port conflict (port 5000 already in use):
```powershell
# Check what's using port 5000
netstat -ano | findstr :5000

# Run the container on a different port (example: port 5001)
docker run -d -p 5001:5000 --name pdf-converter rodriamarog/pdf-converter:v1
```

If you want the container to start automatically when the server boots:
```powershell
# For a new container
docker run -d -p 5000:5000 --name pdf-converter --restart always rodriamarog/pdf-converter:v1

# For an existing container
docker update --restart always pdf-converter
```

## Additional Commands

Stop and remove the container:
```powershell
docker stop pdf-converter
docker rm pdf-converter
```

Check Docker disk usage:
```powershell
docker system df
```

Command to test the container api locally on my machine
```
curl.exe -X POST -F "file=@TEST.pdf" -o converted.pdf http://localhost:5000/api/convert-direct
```