# In-game test driver for Skyrim SE: scancode key input (DirectInput-compatible), mouse
# moves and screen captures. Usage: sky.ps1 "<action>;<action>;..."
#   focus | wait <ms> | tap <hexscan> [holdms] | hold <hexscan> <ms> | down <hexscan> | up <hexscan>
#   type <text> | enter | console (toggle ~) | mouse <dx> <dy> | shot <path.png> [scale]
#   holdmany <ms> <hexscan,hexscan,...>
param([string]$Script)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class SkyIn {
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Explicit)] public struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTUNION u; }
  [DllImport("user32.dll", SetLastError=true)] public static extern uint SendInput(uint n, INPUT[] inputs, int size);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  public static void Key(ushort scan, bool up) {
    var i = new INPUT[1]; i[0].type = 1; i[0].u.ki.wScan = scan;
    uint f = 0x0008; if (up) f |= 0x0002; if (scan > 0xFF) { f |= 0x0001; i[0].u.ki.wScan = (ushort)(scan & 0xFF); }
    i[0].u.ki.dwFlags = f; SendInput(1, i, Marshal.SizeOf(typeof(INPUT)));
  }
  public static void Mouse(int dx, int dy) {
    var i = new INPUT[1]; i[0].type = 0; i[0].u.mi.dx = dx; i[0].u.mi.dy = dy; i[0].u.mi.dwFlags = 0x0001;
    SendInput(1, i, Marshal.SizeOf(typeof(INPUT)));
  }
}
"@
$scan = @{
  'a'=0x1E;'b'=0x30;'c'=0x2E;'d'=0x20;'e'=0x12;'f'=0x21;'g'=0x22;'h'=0x23;'i'=0x17;'j'=0x24;'k'=0x25;'l'=0x26;'m'=0x32;
  'n'=0x31;'o'=0x18;'p'=0x19;'q'=0x10;'r'=0x13;'s'=0x1F;'t'=0x14;'u'=0x16;'v'=0x2F;'w'=0x11;'x'=0x2D;'y'=0x15;'z'=0x2C;
  '1'=0x02;'2'=0x03;'3'=0x04;'4'=0x05;'5'=0x06;'6'=0x07;'7'=0x08;'8'=0x09;'9'=0x0A;'0'=0x0B;
  ' '=0x39;'.'=0x34;','=0x33;'-'=0x0C;'='=0x0D;'/'=0x35;';'=0x27;"'"=0x28
}
$global:sky = $null
function Guard { if (-not $global:sky -or [SkyIn]::GetForegroundWindow() -ne $global:sky) { Write-Output "FOCUS_LOST - aborting"; exit 3 } }
function Tap([int]$s, [int]$ms = 60) { Guard; [SkyIn]::Key($s, $false); Start-Sleep -Milliseconds $ms; [SkyIn]::Key($s, $true); Start-Sleep -Milliseconds 60 }
function Focus {
  $p = Get-Process SkyrimSE -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $p) { Write-Output "NO_SKYRIM_WINDOW"; return }
  [SkyIn]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
  [SkyIn]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 400
  $global:sky = $p.MainWindowHandle
  Write-Output ("FOCUSED " + ([SkyIn]::GetForegroundWindow() -eq $p.MainWindowHandle))
}
function Shot([string]$path, [double]$scale = 0.5) {
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); $g.Dispose()
  $w = [int]($b.Width * $scale); $h = [int]($b.Height * $scale)
  $small = New-Object System.Drawing.Bitmap $bmp, $w, $h
  $small.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $small.Dispose(); $bmp.Dispose()
  Write-Output "SHOT $path"
}
Add-Type -AssemblyName System.Windows.Forms
foreach ($raw in $Script.Split(';')) {
  $a = $raw.Trim(); if (-not $a) { continue }
  $parts = $a.Split(' ', 2); $cmd = $parts[0]; $arg = if ($parts.Count -gt 1) { $parts[1] } else { '' }
  switch ($cmd) {
    'focus'   { Focus }
    'wait'    { Start-Sleep -Milliseconds ([int]$arg) }
    'tap'     { $x = $arg.Split(' '); $ms = if ($x.Count -gt 1) { [int]$x[1] } else { 60 }; Tap ([Convert]::ToInt32($x[0], 16)) $ms }
    'hold'    { $x = $arg.Split(' '); Tap ([Convert]::ToInt32($x[0], 16)) ([int]$x[1]) }
    'holdmany'{ $x = $arg.Split(' '); $ks = $x[1].Split(',') | ForEach-Object { [Convert]::ToInt32($_, 16) }
                Guard; foreach ($k in $ks) { [SkyIn]::Key($k, $false); Start-Sleep -Milliseconds 30 }
                Start-Sleep -Milliseconds ([int]$x[0])
                foreach ($k in $ks) { [SkyIn]::Key($k, $true); Start-Sleep -Milliseconds 30 } }
    'down'    { Guard; [SkyIn]::Key([Convert]::ToInt32($arg, 16), $false) }
    'up'      { [SkyIn]::Key([Convert]::ToInt32($arg, 16), $true) }
    'console' { Tap 0x29 }
    'enter'   { Tap 0x1C }
    'type'    { foreach ($ch in $arg.ToLower().ToCharArray()) { $s = $scan[[string]$ch]; if ($s) { Tap $s 35 } } }
    'mouse'   { $x = $arg.Split(' '); $dx = [int]$x[0]; $dy = [int]$x[1]; $steps = 20
                for ($i = 0; $i -lt $steps; $i++) { Guard; [SkyIn]::Mouse([int]($dx / $steps), [int]($dy / $steps)); Start-Sleep -Milliseconds 15 } }
    'shot'    { $x = $arg.Split('|'); $sc = if ($x.Count -gt 1) { [double]$x[1] } else { 0.5 }; Shot $x[0] $sc }
    default   { Write-Output "UNKNOWN $cmd" }
  }
}
