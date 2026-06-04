param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
$PluginName = "codex-traffic-light"
$ChineseName = -join ([char[]]@(0x7ea2, 0x7eff, 0x706f, 0x63d0, 0x793a, 0x706f))
$StartText = -join ([char[]]@(0x542f, 0x52a8))
$DisplayName = "Codex $PluginName"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$HomeDir = [Environment]::GetFolderPath("UserProfile")
$PluginDir = Join-Path $HomeDir "plugins\$PluginName"
$MarketplacePath = Join-Path $HomeDir ".agents\plugins\marketplace.json"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopLauncher = Join-Path $DesktopPath ($StartText + "Codex" + $ChineseName + ".lnk")
$LegacyDesktopBat = Join-Path $DesktopPath ($StartText + "Codex" + $ChineseName + ".bat")

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if (Test-Path -LiteralPath "D:\") {
        $InstallDir = "D:\codex$ChineseName"
    } else {
        $InstallDir = $PluginDir
    }
}

function Write-Utf8NoBom($Path, $Text) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Copy-CleanProject($Source, $Destination) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $sourceResolved = (Resolve-Path -LiteralPath $Source).Path.TrimEnd("\")
    $destinationResolved = (Resolve-Path -LiteralPath $Destination).Path.TrimEnd("\")

    if ($sourceResolved -ne $destinationResolved) {
        Get-ChildItem -LiteralPath $Destination -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notin @("state") } |
            Remove-Item -Recurse -Force
    }

    Get-ChildItem -LiteralPath $Source -Force |
        Where-Object { $_.Name -notin @(".git", "state", "__pycache__") } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }

    Get-ChildItem -LiteralPath $Destination -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
}

function Write-McpConfig($RootDir) {
    $mcp = [ordered]@{
        mcpServers = [ordered]@{
            "codex-traffic-light" = [ordered]@{
                command = "python"
                args = @((Join-Path $RootDir "scripts\mcp_server.py"))
                env = [ordered]@{
                    PYTHONUTF8 = "1"
                    CODEX_TRAFFIC_LIGHT_STATUS = (Join-Path $RootDir "state\status.json")
                }
            }
        }
    }
    Write-Utf8NoBom (Join-Path $RootDir ".mcp.json") ($mcp | ConvertTo-Json -Depth 20)
}

function Update-Marketplace() {
    $marketplaceDir = Split-Path -Parent $MarketplacePath
    New-Item -ItemType Directory -Force -Path $marketplaceDir | Out-Null

    if (Test-Path -LiteralPath $MarketplacePath) {
        $marketplace = Get-Content -LiteralPath $MarketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $marketplace = [pscustomobject]@{
            name = "personal"
            interface = [pscustomobject]@{ displayName = "Personal" }
            plugins = @()
        }
    }

    if (-not $marketplace.PSObject.Properties["interface"]) {
        $marketplace | Add-Member -NotePropertyName "interface" -NotePropertyValue ([pscustomobject]@{ displayName = "Personal" })
    }
    if (-not $marketplace.PSObject.Properties["plugins"]) {
        $marketplace | Add-Member -NotePropertyName "plugins" -NotePropertyValue @()
    }

    $entry = [pscustomobject]@{
        name = $PluginName
        source = [pscustomobject]@{
            source = "local"
            path = "./plugins/$PluginName"
        }
        policy = [pscustomobject]@{
            installation = "AVAILABLE"
            authentication = "ON_INSTALL"
        }
        category = "Productivity"
    }

    $plugins = @($marketplace.plugins | Where-Object { $_.name -ne $PluginName })
    $marketplace.plugins = @($plugins + $entry)
    Write-Utf8NoBom $MarketplacePath ($marketplace | ConvertTo-Json -Depth 20)
}

function Write-DesktopLauncher($RootDir) {
    Remove-Item -LiteralPath $LegacyDesktopBat -Force -ErrorAction SilentlyContinue
    $pythonw = (Get-Command pythonw -ErrorAction Stop).Source
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($DesktopLauncher)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = "`"$RootDir\scripts\traffic_light_window.py`""
    $shortcut.WorkingDirectory = "$RootDir\scripts"
    $shortcut.WindowStyle = 7
    $shortcut.Description = $StartText + " Codex " + $ChineseName
    $shortcut.Save()
}

function Stop-ExistingTrafficLight() {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like "*traffic_light_window.py*" -or $_.CommandLine -like "*codex_traffic_light_watcher.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Start-TrafficLight($RootDir) {
    Start-Process -FilePath "pythonw" -ArgumentList "`"$RootDir\scripts\traffic_light_window.py`"" -WorkingDirectory "$RootDir\scripts" | Out-Null
}

Write-Host "Installing $DisplayName..."
Write-Host "App path: $InstallDir"
Write-Host "Codex plugin path: $PluginDir"

Stop-ExistingTrafficLight
Copy-CleanProject $RepoRoot $InstallDir
Write-McpConfig $InstallDir

$installFullPath = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$pluginFullPath = [System.IO.Path]::GetFullPath($PluginDir).TrimEnd("\")
if ($installFullPath -ne $pluginFullPath) {
    Copy-CleanProject $RepoRoot $PluginDir
}
Write-McpConfig $PluginDir

Update-Marketplace
Write-DesktopLauncher $InstallDir
Start-TrafficLight $InstallDir

Write-Host ""
Write-Host "Install complete."
Write-Host "Desktop launcher: $DesktopLauncher"
Write-Host "Codex marketplace: $MarketplacePath"
Write-Host ""
Write-Host "Open Codex plugin page and install/enable: codex-traffic-light"
