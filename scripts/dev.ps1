param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "run", "test", "lint")]
    [string]$Command = "run"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LocalTemp = Join-Path $ProjectRoot "temp"
New-Item -ItemType Directory -Path $LocalTemp -Force | Out-Null
$env:TEMP = $LocalTemp
$env:TMP = $LocalTemp
$PipInstallFlags = @("--disable-pip-version-check", "--no-cache-dir", "--retries", "1", "--timeout", "60")

function Get-SystemPython {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return (Get-Command python).Source
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3 -c "import sys; print(sys.version)" *> $null
            return "py"
        }
        catch {
            # Ignore broken launcher entries and continue.
        }
    }
    throw "Python launcher was not found. Install Python 3 first."
}

function Invoke-SystemPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    if ($Python -eq "py") {
        & py -3 @Args
    }
    else {
        & $Python @Args
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Args -join ' ')"
    }
}

function Invoke-VenvPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & $VenvPython @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Venv Python command failed: $($Args -join ' ')"
    }
}

function Ensure-Venv {
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment not found at .venv. Run: ./scripts/dev.ps1 setup"
    }
}

function Enable-SystemSitePackages {
    $venvCfg = Join-Path $ProjectRoot ".venv\pyvenv.cfg"
    if (-not (Test-Path $venvCfg)) {
        throw "pyvenv.cfg not found. Cannot apply fallback."
    }

    $updated = (Get-Content $venvCfg) -replace '^include-system-site-packages\s*=.*$', 'include-system-site-packages = true'
    Set-Content -Path $venvCfg -Value $updated -Encoding ascii
}

Push-Location $ProjectRoot
try {
    switch ($Command) {
        "setup" {
            $pythonExe = Get-SystemPython
            $needsVenvCreate = (-not (Test-Path ".venv")) -or (-not (Test-Path $VenvPython))
            if ($needsVenvCreate) {
                Invoke-SystemPython -Python $pythonExe -Args @("-m", "venv", ".venv", "--clear")
            }

            $pipAvailable = $true
            try {
                Invoke-VenvPython -Args @("-m", "pip", "--version")
            }
            catch {
                $pipAvailable = $false
            }

            if (-not $pipAvailable) {
                Write-Warning "pip missing in venv; bootstrapping from bundled wheels."
                $stdlibRaw = ""
                if ($pythonExe -eq "py") {
                    $stdlibRaw = & py -3 -c "import sysconfig; print(sysconfig.get_paths()['stdlib'])"
                }
                else {
                    $stdlibRaw = & $pythonExe -c "import sysconfig; print(sysconfig.get_paths()['stdlib'])"
                }
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to locate Python stdlib path for pip bootstrap."
                }

                $stdlib = ($stdlibRaw | Select-Object -First 1).Trim()
                if ([string]::IsNullOrWhiteSpace($stdlib)) {
                    throw "Failed to locate Python stdlib path for pip bootstrap."
                }

                $bundled = Join-Path $stdlib "ensurepip\_bundled"
                $bootstrapPipArgs = @("-m", "pip", "--python", ".venv", "install", "--no-index", "--find-links", $bundled, "pip") + $PipInstallFlags
                Invoke-SystemPython -Python $pythonExe -Args $bootstrapPipArgs
            }

            $requirementsArgs = @("-m", "pip", "install", "-r", "requirements.txt") + $PipInstallFlags
            try {
                Invoke-VenvPython -Args $requirementsArgs
                Write-Host "Setup complete."
            }
            catch {
                Write-Warning "requirements install failed. Enabling system site-packages fallback."
                Enable-SystemSitePackages
                Invoke-VenvPython -Args @("-c", "import click, rich, requests, docx, openpyxl, lxml, dotenv, pydantic, fastapi, uvicorn; print('FALLBACK_IMPORTS_OK')")
                Write-Host "Setup complete (fallback mode: include-system-site-packages=true)."
            }
        }
        "run" {
            Ensure-Venv
            Write-Host "Available CLI commands:"
            Invoke-VenvPython -Args @("main.py", "--help")
            Write-Host ""
            Write-Host "Example command (help only):"
            Invoke-VenvPython -Args @("main.py", "check-updates", "--help")
        }
        "test" {
            Ensure-Venv
            Invoke-VenvPython -Args @("evals/smoke_test.py")
        }
        "lint" {
            Ensure-Venv
            $venvRuff = Join-Path $ProjectRoot ".venv\Scripts\ruff.exe"
            if (Test-Path $venvRuff) {
                & $venvRuff check .
                if ($LASTEXITCODE -ne 0) {
                    throw "Ruff lint failed."
                }
            }
            elseif (Get-Command ruff -ErrorAction SilentlyContinue) {
                & ruff check .
                if ($LASTEXITCODE -ne 0) {
                    throw "Ruff lint failed."
                }
            }
            else {
                Write-Host "No linter configured. Placeholder only."
            }
        }
    }
}
finally {
    Pop-Location
}
