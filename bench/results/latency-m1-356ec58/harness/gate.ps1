$os = Get-CimInstance Win32_OperatingSystem
$free = [math]::Round($os.FreePhysicalMemory/1MB,2)
$avail = [math]::Round((Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue/1024,2)
$commit = "{0:N0}/{1:N0} MB" -f (($os.TotalVirtualMemorySize-$os.FreeVirtualMemory)/1KB), ($os.TotalVirtualMemorySize/1KB)
$s = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 5).CounterSamples | % { $_.CookedValue }
$avg = [math]::Round(($s | Measure -Average).Average,1)
$pass = ($avail -ge 3) -and ($avg -le 15)
"GATE free_GB=$free avail_GB=$avail commit=$commit cpu_avg=$avg samples=$(($s | % { '{0:N1}' -f $_ }) -join ',') pass=$pass"
if (-not $pass) {
  "top5 by working set:"; Get-Process | Sort WS -Desc | Select -First 5 Name,Id,@{n='WS_MB';e={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String
  "top5 by commit (private bytes):"; Get-Process | Sort PrivateMemorySize64 -Desc | Select -First 5 Name,Id,@{n='Private_MB';e={[math]::Round($_.PrivateMemorySize64/1MB)}} | Format-Table -AutoSize | Out-String
}
