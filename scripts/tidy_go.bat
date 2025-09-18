@echo off
REM Get the parent dir of the script location
set "work_dir=%~dp0.."
pushd "%work_dir%"
for %%P in (
    "app/infra/go/common"
    "app/infra/go/application"
    "app/poc/infra/go/application"
    "app/poc/infra/go/client"
) do (
    set "full_path=%work_dir%\%%~P"
    if exist "%%~P" (
        echo Running 'go mod tidy && go mod vendor' in %work_dir%\%%~P
        pushd "%%~P"
        go mod tidy
        go mod vendor
        popd
    ) else (
        echo Directory %work_dir%\%%~P does not exist, skipping.
    )
)
popd