$ErrorActionPreference = "Stop"
$PluginName = "codex-traffic-light"
$ChineseName = -join ([char[]]@(0x7ea2, 0x7eff, 0x706f, 0x63d0, 0x793a, 0x706f))
$StartText = -join ([char[]]@(0x542f, 0x52a8))
$AutoStartText = -join ([char[]]@(0x81ea, 0x52a8, 0x542f, 0x52a8))
$HomeDir = [Environment]::GetFolderPath("UserProfile")
$PluginDir = Join-Path $HomeDir "plugins\$PluginName"
$MarketplacePath = Join-Path $HomeDir ".agents\plugins\marketplace.json"
$DesktopLauncher = Join-Path ([Environment]::GetFolderPath("Desktop")) ($StartText + "Codex" + $ChineseName + ".lnk")
$LegacyDesktopBat = Join-Path ([Environment]::GetFolderPath("Desktop")) ($StartText + "Codex" + $ChineseName + ".bat")
$DefaultDInstall = "D:\codex$ChineseName"
$StartupLauncher = Join-Path ([Environment]::GetFolderPath("Startup")) ("Codex" + $ChineseName + "AutoStart.bat")
$LegacyStartupLauncher = Join-Path ([Environment]::GetFolderPath("Startup")) ("Codex" + $ChineseName + $AutoStartText + ".bat")

function Write-Utf8NoBom($Path, $Text) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*traffic_light_window.py*" -or $_.CommandLine -like "*codex_traffic_light_watcher.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Remove-Item -LiteralPath $DesktopLauncher -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $LegacyDesktopBat -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $StartupLauncher -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $LegacyStartupLauncher -Force -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $MarketplacePath) {
    $marketplace = Get-Content -LiteralPath $MarketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($marketplace.PSObject.Properties["plugins"]) {
        $marketplace.plugins = @($marketplace.plugins | Where-Object { $_.name -ne $PluginName })
        Write-Utf8NoBom $MarketplacePath ($marketplace | ConvertTo-Json -Depth 20)
    }
}

Remove-Item -LiteralPath $PluginDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $DefaultDInstall -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Codex traffic light indicator uninstalled."
