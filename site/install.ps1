# Install ArenaHub on Windows with one command, from PowerShell:
#
#   irm https://evilchuck666.github.io/ArenaHub/install.ps1 | iex
#
# Downloads the latest release's Windows package, checks it against SHA256SUMS.txt,
# installs ArenaHub.exe in %LOCALAPPDATA%\Programs\ArenaHub and adds shortcuts to the
# Start menu and the desktop. Run it again to update. Works in Windows PowerShell 5.1
# and PowerShell 7. GNU/Linux and macOS use install.sh instead.
#
# This file must stay ASCII: Windows PowerShell decodes downloaded scripts without
# knowing their encoding.

function Install-ArenaHub {
    # Errors end this function with a message; 'exit' would close the console that
    # ran 'irm ... | iex'.
    $ErrorActionPreference = 'Stop'
    # The progress bar makes Invoke-WebRequest many times slower in PowerShell 5.1.
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $repo = 'Evilchuck666/ArenaHub'
    $download = "https://github.com/$repo/releases/latest/download"
    $package = 'ArenaHub-windows-x64.zip'
    $installDir = Join-Path $env:LOCALAPPDATA 'Programs\ArenaHub'
    $exe = Join-Path $installDir 'ArenaHub.exe'

    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'ArenaHub needs a 64-bit version of Windows.'
    }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        Write-Host '==> Windows on ARM: ArenaHub runs as an x64 application under emulation.'
    }

    $version = $null
    try {
        $release = Invoke-RestMethod -UseBasicParsing "https://api.github.com/repos/$repo/releases/latest"
        $version = $release.tag_name.TrimStart('v')
    } catch {
        # Only used in the messages; the download links don't need it.
        Write-Verbose "Could not read the latest version: $_"
    }

    $work = Join-Path ([IO.Path]::GetTempPath()) ('arenahub-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        Write-Host "==> Downloading $package"
        $zip = Join-Path $work $package
        $sums = Join-Path $work 'SHA256SUMS.txt'
        Invoke-WebRequest -UseBasicParsing -Uri "$download/$package" -OutFile $zip
        Invoke-WebRequest -UseBasicParsing -Uri "$download/SHA256SUMS.txt" -OutFile $sums

        $expected = $null
        foreach ($line in Get-Content $sums) {
            $fields = $line -split '\s+'
            if ($fields.Count -ge 2 -and $fields[1] -eq $package) { $expected = $fields[0] }
        }
        if (-not $expected) { throw "SHA256SUMS.txt has no checksum for $package." }
        $actual = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash
        if ($actual -ne $expected) { throw "Checksum mismatch for $package; try again." }

        $extracted = Join-Path $work 'extracted'
        Expand-Archive -Path $zip -DestinationPath $extracted
        $newExe = Join-Path $extracted 'ArenaHub.exe'
        if (-not (Test-Path $newExe)) { throw "$package does not contain ArenaHub.exe." }

        Write-Host "==> Installing $exe"
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
        try {
            Copy-Item -Path $newExe -Destination $exe -Force
        } catch {
            throw 'Could not replace ArenaHub.exe. Close ArenaHub and run this again.'
        }
        Unblock-File -Path $exe

        $shell = New-Object -ComObject WScript.Shell
        $shortcuts = @(
            (Join-Path ([Environment]::GetFolderPath('Programs')) 'ArenaHub.lnk'),
            (Join-Path ([Environment]::GetFolderPath('Desktop')) 'ArenaHub.lnk')
        )
        foreach ($path in $shortcuts) {
            $shortcut = $shell.CreateShortcut($path)
            $shortcut.TargetPath = $exe
            $shortcut.WorkingDirectory = $installDir
            $shortcut.IconLocation = "$exe,0"
            $shortcut.Description = 'Install and play Quake III Arena, Team Arena and classic mods'
            $shortcut.Save()
        }
    } finally {
        Remove-Item -Recurse -Force -Path $work -ErrorAction SilentlyContinue
    }

    if ($version) { Write-Host "==> Installed ArenaHub $version." } else { Write-Host '==> Installed ArenaHub.' }
    Write-Host '==> Open it from the Start menu or the ArenaHub shortcut on your desktop.'
    Write-Host '==> To uninstall, delete these:'
    Write-Host "      $installDir"
    foreach ($path in $shortcuts) { Write-Host "      $path" }
}

try {
    Install-ArenaHub
} catch {
    Write-Host "error: $($_.Exception.Message)" -ForegroundColor Red
}
