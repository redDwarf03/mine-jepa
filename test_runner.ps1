$logPath = "C:\SSe\app\mine-jepa\logs\coldstart_commit4_n20.log"
$scriptPath = "C:\SSe\app\mine-jepa\scripts\play_minerl_multi.py"
$configPath = "C:\SSe\app\mine-jepa\configs\play_craft_commit4.yaml"

Set-Location "C:\SSe\app\mine-jepa"

Write-Host "Starting test with redirect to $logPath"

# Run using & notation, pipe to tee, wait for completion
& "C:\SSe\app\mine-jepa\run.bat" scripts/play_minerl_multi.py --episodes 20 --script scripts/play_craft.py --config configs/play_craft_commit4.yaml 2>&1 | Tee-Object -FilePath $logPath

Write-Host "Test complete"
