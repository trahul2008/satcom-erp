<#
.SYNOPSIS
The SMB share on Server A that receives the ERPNext VM's nightly Borg backup (same pattern as
Set-NextcloudBackupShare.ps1).

.DESCRIPTION
  - Local account "erpbackup": used only by this share. Password: 32 random characters, generated
    here, never printed; kept in C:\ProgramData\satcom\erpbackup-smb.txt and, in the form the Linux
    mount wants, erpbackup-cifs-cred (both SYSTEM + Administrators only). Reruns keep it unless -Rotate.
  - Borg passphrase for the ERP repository: generated here once, never printed, kept in
    C:\ProgramData\satcom\erpbackup-borg-pass.txt (SYSTEM + Administrators only). It is piped to the
    VM over SSH; a restore anywhere needs it, so keep a copy in the password manager too.
  - D:\ErpBackup: NTFS access for SYSTEM, Administrators and erpbackup only.
  - Hidden share ErpBackup$ for erpbackup only, SMB encryption required.
  - Firewall: nothing new. The VM reaches A as 192.168.1.86 (behind B's NAT), which the existing
    rule "Satcom Nextcloud backup (SMB from the VM only)" already allows; this script checks that and
    stops if it does not. When the VM moves to VM-LAN (192.168.1.91) that rule needs .91 added.
The credentials go to the VM by piping erpbackup-cifs-cred over SSH into a root-only file - see
backup/mount-backup.sh.

.PARAMETER WhatIf
Show what would be done.
#>
[CmdletBinding()]
param([switch]$WhatIf, [switch]$Rotate)

$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'WIN-PONPEP3A3BC') { throw "REFUSED: the backup share lives on Server A, this is $env:COMPUTERNAME" }

$user     = 'erpbackup'
$dir      = 'D:\ErpBackup'
$share    = 'ErpBackup$'
$stateDir = 'C:\ProgramData\satcom'
$pwFile   = Join-Path $stateDir 'erpbackup-smb.txt'
$credFile = Join-Path $stateDir 'erpbackup-cifs-cred'
$borgFile = Join-Path $stateDir 'erpbackup-borg-pass.txt'
$fwName   = 'Satcom Nextcloud backup (SMB from the VM only)'
$vmSource = '192.168.1.86'

function Write-Step([string]$msg) { "$(if ($WhatIf) { '[WhatIf] ' })$msg" }
function Protect-File([string]$path) {
    & icacls.exe $path /inheritance:r /grant:r 'SYSTEM:F' 'BUILTIN\Administrators:F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls failed on $path" }
}
function New-Secret {
    $chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes = New-Object byte[] 32; $rng.GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

$rule = Get-NetFirewallRule -DisplayName $fwName -ErrorAction SilentlyContinue
if (-not $rule -or (($rule | Get-NetFirewallAddressFilter).RemoteAddress -notcontains $vmSource)) {
    throw "firewall rule '$fwName' missing or not allowing ${vmSource}: not changing the firewall here, stop"
}
Write-Step "firewall: existing rule '$fwName' already allows TCP 445 from $vmSource (unchanged)"

$needPw = $Rotate -or -not (Test-Path $pwFile) -or -not (Get-LocalUser $user -ErrorAction SilentlyContinue)
if ($needPw) {
    Write-Step "$(if (Get-LocalUser $user -ErrorAction SilentlyContinue) { 'setting a new' } else { 'creating account with a' }) random password for $user (stored in $pwFile, not shown)"
    if (-not $WhatIf) {
        $plain = New-Secret
        $secure = ConvertTo-SecureString $plain -AsPlainText -Force
        try {
            if (Get-LocalUser $user -ErrorAction SilentlyContinue) { Set-LocalUser -Name $user -Password $secure }
            else {
                New-LocalUser -Name $user -Password $secure -PasswordNeverExpires -UserMayNotChangePassword `
                    -AccountNeverExpires -Description 'ERPNext VM backup share only' | Out-Null
            }
            [IO.File]::WriteAllText($pwFile, $plain); Protect-File $pwFile
            [IO.File]::WriteAllText($credFile, "username=$user`npassword=$plain`ndomain=$env:COMPUTERNAME`n"); Protect-File $credFile
        } catch {
            throw "account/password step failed: $($_.Exception.GetType().Name)"   # never echo the value
        } finally { $plain = $null }
    }
} else { Write-Step "account $user and its password file exist (use -Rotate for a new password)" }

if (-not (Test-Path $borgFile)) {
    Write-Step "generating the Borg passphrase (stored in $borgFile, not shown)"
    if (-not $WhatIf) {
        $p = New-Secret; try { [IO.File]::WriteAllText($borgFile, $p); Protect-File $borgFile } finally { $p = $null }
    }
} else { Write-Step "Borg passphrase file exists (never rotated here: old archives need it)" }

if (-not (Test-Path $dir)) { Write-Step "creating $dir"; if (-not $WhatIf) { New-Item -ItemType Directory -Path $dir | Out-Null } }
Write-Step "NTFS on ${dir}: SYSTEM, Administrators full; $user modify; no inheritance"
if (-not $WhatIf) {
    & icacls.exe $dir /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' "${user}:(OI)(CI)M" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls failed on $dir" }
}

$s = Get-SmbShare -Name $share -ErrorAction SilentlyContinue
if (-not $s) {
    Write-Step "share $share -> $dir, full access for $user only, encryption required"
    if (-not $WhatIf) { New-SmbShare -Name $share -Path $dir -FullAccess $user -EncryptData $true -FolderEnumerationMode AccessBased | Out-Null }
} else {
    Write-Step "share $share exists (encrypt=$($s.EncryptData)); access: $((Get-SmbShareAccess -Name $share | ForEach-Object { "$($_.AccountName)=$($_.AccessRight)" }) -join ', ')"
}
