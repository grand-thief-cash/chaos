# Ensure goimports is installed
# Use : powershell -ExecutionPolicy Bypass -File setup_goimports.ps1

go install golang.org/x/tools/cmd/goimports@latest

# Get GOPATH\bin path
$gobin = (go env GOPATH) + "\bin"

# Get user PATH
$oldPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($oldPath -notlike "*$gobin*") {
    $newPath = "$oldPath;$gobin"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Output "Added $gobin to PATH. Please restart PowerShell or CMD to apply changes."
} else {
    Write-Output "$gobin already exists in PATH."
}