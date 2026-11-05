# Включает автопостинг «Канала 15»: задача Планировщика Windows запускает autopost.py каждые 15 минут и при входе в систему.
# Запуск:   powershell -ExecutionPolicy Bypass -File "G:\Claude\gruzovichki\promo\telegram\install_autopost.ps1"
# Выключить: тот же файл с параметром -Remove
param([switch]$Remove)

$name = 'Kanal15-Autopost'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Host "Автопостинг выключен (задача $name удалена)."
    return
}

$py  = 'C:\Users\stray\AppData\Local\Programs\Python\Python313\pythonw.exe'   # pythonw = без окна
$dir = $PSScriptRoot
$action = New-ScheduledTaskAction -Execute $py -Argument "-I `"$dir\autopost.py`"" -WorkingDirectory $dir
$every  = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15)
$logon  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Description "Канал 15: посты из $dir\schedule.json" `
    -Action $action -Trigger $every, $logon -Settings $set -Force | Out-Null

Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 5
$info = Get-ScheduledTaskInfo -TaskName $name
Write-Host "Автопостинг включён. Последний запуск: $($info.LastRunTime), код: $($info.LastTaskResult) (0 = всё хорошо). Следующий: $($info.NextRunTime)"
