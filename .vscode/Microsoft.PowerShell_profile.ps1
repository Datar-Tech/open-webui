# filepath: c:\\Users\\te-yihsu\\OneDrive - Advanced Micro Devices Inc\\Documents\\WindowsPowerShell\\Microsoft.PowerShell_profile.ps1

# Function to find and activate a Python virtual environment
function Find-And-Activate-Venv {
    if (-not $env:VIRTUAL_ENV) {
        $currentPath = Get-Location
        $foundVenv = $false

        # Search for venv in current and parent directories
        while ($currentPath.Path -ne (Split-Path $currentPath.Path -Parent) -and -not $foundVenv) {
            $venvPath = Join-Path $currentPath.Path "venv"
            $dotVenvPath = Join-Path $currentPath.Path ".venv"

            if (Test-Path $venvPath -PathType Container) {
                $venvActivateScript = Join-Path $venvPath "Scripts\Activate.ps1"
                if (Test-Path $venvActivateScript) {
                    . $venvActivateScript
                    $foundVenv = $true
                }
            } elseif (Test-Path $dotVenvPath -PathType Container) {
                $venvActivateScript = Join-Path $dotVenvPath "Scripts\Activate.ps1"
                if (Test-Path $venvActivateScript) {
                    . $venvActivateScript
                    $foundVenv = $true
                }
            }

            if (-not $foundVenv) {
                $currentPath = Split-Path $currentPath.Path -Parent
            }
        }
    }
}

# Call the function to activate venv when PowerShell starts
Find-And-Activate-Venv

function prompt {
  if ($env:VIRTUAL_ENV) {
    $venvName = Split-Path $env:VIRTUAL_ENV -Leaf
    Write-Host "($venvName) " -NoNewline -ForegroundColor Green # Display venv name in Green
  }
  "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) " # Return the rest of the prompt
} # This closes the prompt function

# Aliases and Functions
Remove-Item Alias:set -Force -ErrorAction SilentlyContinue # Remove built-in 'set' alias
function set {
    Get-ChildItem Env:
}
