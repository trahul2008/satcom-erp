<#
.SYNOPSIS
Builds the ERPNext demo VM (satcom-erp) on this Hyper-V host - the live host is Server B.

.DESCRIPTION
A demo, deliberately NOT redundant: no Hyper-V Replica, no failover. Same recipe as
New-NextcloudVM.ps1 (Ubuntu 24.04 autoinstall from a CIDATA seed disk), reusing the ISO it
downloaded. ERPNext is Linux-only, and Docker Desktop is not on these Windows servers, so the
containers live inside this small VM.

Stages, run in order:
  -Stage Create    Gen 2 Secure Boot VM, 6 vCPU, 12 GB static RAM, one 200 GB dynamic VHDX,
                   MAC 00:15:5D:01:5C:91 (192.168.1.91 on the router later), 172.20.90.11 on VM-NAT.
  -Stage Confirm   Sends Y, E, S, Enter to the console (Ubuntu 24.04 asks "Continue with
                   autoinstall?"); call it ~90 s after Create. Harmless if sent twice.
  -Stage Finalize  After the installer powered the VM off: detach ISO + seed disk, boot from disk.
  -Stage Status    Show the VM (changes nothing).

Never overwrites: Create refuses if the VM or its disks exist.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateSet('Create', 'Confirm', 'Finalize', 'Status')] [string]$Stage,
    [string]$SshPublicKeyFile = 'C:\ProgramData\satcom\nextcloud-vm-key.pub',
    [string]$SwitchName = 'VM-NAT',
    [string]$SeedSource,
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

$vmName  = 'satcom-erp'
$root    = 'D:\Hyper-V'
$vhdDir  = Join-Path $root 'Virtual Hard Disks'
$isoPath = Join-Path $root 'ISO\ubuntu-24.04.5-live-server-amd64.iso'
$isoSha  = '97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8'
$osVhd   = Join-Path $vhdDir "$vmName-os.vhdx"
$seedVhd = Join-Path $vhdDir "$vmName-seed.vhdx"
$mac     = '00155D015C91'
if (-not $SeedSource) { $SeedSource = Join-Path $PSScriptRoot '..\erpnext\autoinstall' }

function Write-Step([string]$msg) {
    Write-Output ('{0}  {1}{2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $(if ($WhatIf) { '[WhatIf] ' } else { '' }), $msg)
}

switch ($Stage) {
'Create' {
    if (Get-VM -Name $vmName -ErrorAction SilentlyContinue) { throw "REFUSED: VM $vmName already exists" }
    foreach ($p in $osVhd, $seedVhd) { if (Test-Path $p) { throw "REFUSED: $p already exists" } }
    if (-not (Test-Path $isoPath)) { throw "ISO $isoPath missing - run New-NextcloudVM.ps1 -Stage Download" }
    if ((Get-FileHash $isoPath -Algorithm SHA256).Hash -ne $isoSha.ToUpper()) { throw 'ISO hash mismatch' }
    if (-not (Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue)) { throw "switch $SwitchName not found" }
    $key = (Get-Content $SshPublicKeyFile -Raw).Trim()
    if ($key -notmatch '^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+') { throw 'public key file is not an OpenSSH public key' }
    $userData = (Get-Content (Join-Path $SeedSource 'user-data') -Raw).Replace('__SSH_KEY__', $key)
    $metaData = Get-Content (Join-Path $SeedSource 'meta-data') -Raw
    Write-Step "creating $osVhd (200 GB dynamic), seed disk, VM $vmName (6 vCPU, 12 GB) on $SwitchName"
    if ($WhatIf) { return }

    New-VHD -Path $osVhd -SizeBytes 200GB -Dynamic -BlockSizeBytes 1MB | Out-Null
    New-VHD -Path $seedVhd -SizeBytes 256MB -Dynamic | Out-Null
    $disk = Mount-VHD -Path $seedVhd -Passthru | Get-Disk
    try {
        Initialize-Disk -Number $disk.Number -PartitionStyle MBR
        $part = New-Partition -DiskNumber $disk.Number -UseMaximumSize -AssignDriveLetter
        Format-Volume -Partition $part -FileSystem FAT32 -NewFileSystemLabel 'CIDATA' -Confirm:$false | Out-Null
        $drive = (Get-Partition -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber).DriveLetter
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [IO.File]::WriteAllText("${drive}:\user-data", ($userData -replace "`r`n", "`n"), $utf8)
        [IO.File]::WriteAllText("${drive}:\meta-data", ($metaData -replace "`r`n", "`n"), $utf8)
    } finally { Dismount-VHD -Path $seedVhd }

    New-VM -Name $vmName -Generation 2 -MemoryStartupBytes 12GB -Path $root -VHDPath $osVhd -SwitchName $SwitchName | Out-Null
    Set-VM -Name $vmName -ProcessorCount 6 -StaticMemory -AutomaticStartAction Start -AutomaticStartDelay 90 `
        -AutomaticStopAction ShutDown -CheckpointType Production -AutomaticCheckpointsEnabled $false
    Set-VMNetworkAdapter -VMName $vmName -StaticMacAddress $mac
    Add-VMHardDiskDrive -VMName $vmName -Path $seedVhd
    $dvd = Add-VMDvdDrive -VMName $vmName -Path $isoPath -Passthru
    Set-VMFirmware -VMName $vmName -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority -FirstBootDevice $dvd
    Enable-VMIntegrationService -VMName $vmName -Name 'Guest Service Interface'
    Start-VM -Name $vmName
    Write-Step "started $vmName - installer runs unattended; run -Stage Confirm after ~90 s"
}
'Confirm' {
    $cs = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_ComputerSystem -Filter "ElementName='$vmName'"
    $kb = Get-CimAssociatedInstance -InputObject $cs -ResultClassName Msvm_Keyboard
    foreach ($code in 89, 69, 83, 13) {   # Y E S Enter
        Invoke-CimMethod -InputObject $kb -MethodName TypeKey -Arguments @{ keyCode = [uint32]$code } | Out-Null
        Start-Sleep -Milliseconds 300
    }
    Write-Step 'sent Y E S Enter'
}
'Finalize' {
    $vm = Get-VM -Name $vmName
    if ($vm.State -ne 'Off') { throw "VM is $($vm.State) - wait for the installer to power it off" }
    Write-Step 'detaching ISO and seed disk, booting from the OS disk'
    if ($WhatIf) { return }
    Get-VMDvdDrive -VMName $vmName | Remove-VMDvdDrive
    Get-VMHardDiskDrive -VMName $vmName | Where-Object Path -eq $seedVhd | Remove-VMHardDiskDrive
    $os = Get-VMHardDiskDrive -VMName $vmName | Where-Object Path -eq $osVhd
    Set-VMFirmware -VMName $vmName -FirstBootDevice $os
    Start-VM -Name $vmName
    Write-Step "started $vmName from its OS disk"
}
'Status' {
    $vm = Get-VM -Name $vmName -ErrorAction SilentlyContinue
    if (-not $vm) { "VM $vmName does not exist"; return }
    '{0}  state={1}  cpu={2}  mem={3:N0} GB  uptime={4}' -f $vm.Name, $vm.State, $vm.ProcessorCount, ($vm.MemoryStartup / 1GB), $vm.Uptime
    Get-VMNetworkAdapter -VMName $vmName | ForEach-Object { "  nic switch=$($_.SwitchName) mac=$($_.MacAddress) ip=$($_.IPAddresses -join ',')" }
    Get-VMHardDiskDrive -VMName $vmName | ForEach-Object { $v = Get-VHD -Path $_.Path; '  disk {0}  {1:N0} GB max, {2:N1} GB used' -f $_.Path, ($v.Size / 1GB), ($v.FileSize / 1GB) }
}
}
