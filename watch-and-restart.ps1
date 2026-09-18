# Watches a worldserver: restarts it after a crash, and after a freeze - a world that stops
# updating keeps its process alive and writes nothing more, so a log untouched for a few minutes
# is the tell. Before killing a frozen server it captures the thread stacks, when a capture script
# is available: that is usually what tells you why it froze.
#
#   powershell -ExecutionPolicy Bypass -File watch-and-restart.ps1 -Server C:\my-server\server
#
# Put a Discord webhook URL in the file named by -WebhookFile and incidents are announced there.
# With no such file, nothing is ever sent anywhere.
param(
    [string] $Server = (Join-Path $PSScriptRoot "server"),
    [int] $FreezeMinutes = 5,
    [string] $Journal = (Join-Path $PSScriptRoot "watch.txt"),
    [string] $WebhookFile = (Join-Path $PSScriptRoot "alerte-discord.txt"),
    [string] $StackScript = "",          # optional, called as <script> <pid> <exe> <base> <samples>
    [string] $Python = "python",
    [string[]] $TrimLogs = @("Chat.log"),   # logs kept to the last $TrimHours; empty to never trim
    [int] $TrimHours = 24,
    [int] $TrimEveryMinutes = 60
)
$ErrorActionPreference = 'Continue'

function Log {
    param($text)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $text"
    Write-Host $line
    Add-Content -LiteralPath $Journal $line
}

function Alert {
    param($text)
    if (-not (Test-Path $WebhookFile)) { return }
    $url = (Get-Content $WebhookFile -Raw).Trim()
    if (-not $url.StartsWith('https://')) { return }
    try {
        $body = @{ content = "**SquidBots** - $text" } | ConvertTo-Json -Compress
        Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json; charset=utf-8' `
            -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 20 | Out-Null
    } catch { Log "   Discord alert failed: $($_.Exception.Message)" }
}

# A chat log of a thousand bots grows about a megabyte an hour, and nothing ever shortens it.
# The worldserver holds the file open, so renaming or replacing it would leave the server writing
# into a file no one can see any more: the only safe move is to rewrite it in place, keeping the
# tail. It is opened shared, so at worst one line written during the rewrite is lost.
function Trim-Log {
    param([string] $Path, [int] $Hours)
    if (-not (Test-Path $Path)) { return }
    $cutoff = (Get-Date).AddHours(-$Hours)
    try {
        $lines = [IO.File]::ReadAllLines($Path)
    } catch { Log "   cannot read $(Split-Path $Path -Leaf): $($_.Exception.Message)"; return }
    if ($lines.Length -eq 0) { return }

    $keepFrom = -1
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]
        if ($line.Length -lt 19) { continue }
        $when = [datetime]::MinValue
        if ([datetime]::TryParseExact($line.Substring(0, 19), 'yyyy-MM-dd HH:mm:ss',
                [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref] $when)) {
            if ($when -ge $cutoff) { $keepFrom = $i; break }
        }
    }
    if ($keepFrom -le 0) { return }          # nothing older than the window, or no date at all

    $kept = [string]::Join("`r`n", $lines[$keepFrom..($lines.Length - 1)]) + "`r`n"
    $bytes = [Text.Encoding]::UTF8.GetBytes($kept)
    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.SetLength($bytes.Length)
        $stream.Close()
        Log "$(Split-Path $Path -Leaf) trimmed: $($lines.Length - $keepFrom) lines kept of $($lines.Length), the last $Hours h"
    } catch { Log "   cannot trim $(Split-Path $Path -Leaf): $($_.Exception.Message)" }
}

function Get-World {
    Get-Process worldserver -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Server\*" }
}

function Start-World {
    $world = Start-Process -FilePath "$Server\worldserver.exe" -WorkingDirectory $Server -WindowStyle Hidden -PassThru
    Log "server restarted, pid $($world.Id)"
    return $world
}

Log "watching $Server (a freeze is $FreezeMinutes minutes without a log line)"
$lastTrim = Get-Date
while ($true) {
    Start-Sleep 60
    $world = Get-World

    if ($TrimLogs -and ((Get-Date) - $lastTrim).TotalMinutes -ge $TrimEveryMinutes) {
        $lastTrim = Get-Date
        foreach ($name in $TrimLogs) { Trim-Log (Join-Path "$Server\logs" $name) $TrimHours }
    }

    if (-not $world) {
        $crashes = Get-ChildItem "$Server\Crashes" -Filter *.txt -ErrorAction SilentlyContinue |
            Where-Object LastWriteTime -gt (Get-Date).AddMinutes(-5)
        foreach ($crash in $crashes) { Log "crash: $($crash.Name) ($($crash.Length) bytes)" }
        if (-not $crashes) { Log 'process gone, with no crash report' }
        $entry = Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=(Get-Date).AddMinutes(-5)} -ErrorAction SilentlyContinue |
            Where-Object { $_.Message -like '*worldserver*' } | Select-Object -First 1
        if ($entry) {
            Log "  faulting module: $(($entry.Message -split "`n" | Select-String 'module' | Select-Object -First 1).ToString().Trim())"
        }
        Alert "crash at $(Get-Date -Format 'HH:mm:ss'), the server is being restarted."
        Start-World | Out-Null
        continue
    }

    $last = (Get-Item "$Server\logs\Server.log").LastWriteTime
    if (((Get-Date) - $last).TotalMinutes -gt $FreezeMinutes) {
        Log "log frozen since $($last.ToString('HH:mm:ss')), pid $($world.Id)"
        if ($StackScript -and (Test-Path $StackScript)) {
            $stacks = Join-Path $PSScriptRoot "stacks-$(Get-Date -Format yyyyMMdd-HHmm).txt"
            $base = '{0:X}' -f [int64]((Get-Process -Id $world.Id).Modules |
                Where-Object ModuleName -eq 'worldserver.exe').BaseAddress
            & $Python $StackScript $world.Id "$Server\worldserver.exe" $base 2 > $stacks 2>&1
            Log "  thread stacks: $stacks"
        }
        Alert "world frozen since $($last.ToString('HH:mm:ss')), restarting."
        Stop-Process -Id $world.Id -Force
        Start-Sleep 8
        Start-World | Out-Null
    }
}
