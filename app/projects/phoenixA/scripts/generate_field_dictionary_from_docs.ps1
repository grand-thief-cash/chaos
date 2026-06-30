param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "generate_field_dictionary_from_docs.py"
& $PythonBin $scriptPath --project-root $ProjectRoot

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
