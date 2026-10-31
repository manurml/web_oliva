# Crea (o sustituye) las tareas de Windows que actualizan la web. Solo corren con la sesión iniciada.
$raiz = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path (Split-Path -Parent (Get-Command python).Source) "pythonw.exe"
$script = Join-Path $raiz "pc\actualizar.py"
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

# Cada 30 minutos, de 07:00 a 22:00: actualiza si Oleista ha publicado precios nuevos.
$comprobar = New-ScheduledTaskTrigger -Once -At "07:00" -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 15)
$diario = New-ScheduledTaskTrigger -Daily -At "07:00"
$comprobar.Repetition.StopAtDurationEnd = $true
$diario.Repetition = $comprobar.Repetition
Register-ScheduledTask -TaskName "AOVE al Dia - comprobar precios" -Force -Settings $ajustes -Trigger $diario `
    -Action (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $raiz) | Out-Null

# Al iniciar sesión (con 2 minutos para que haya red) y a las 22:30: publica las noticias aunque hoy no haya precios nuevos.
$alEntrar = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$alEntrar.Delay = "PT2M"
Register-ScheduledTask -TaskName "AOVE al Dia - cierre del dia" -Force -Settings $ajustes -Trigger @($alEntrar, (New-ScheduledTaskTrigger -Daily -At "22:30")) `
    -Action (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`" --completa" -WorkingDirectory $raiz) | Out-Null

Get-ScheduledTask -TaskName "AOVE al Dia*" | ForEach-Object { "$($_.TaskName): $($_.State)" }
