# Crea (o sustituye) la tarea de Windows que actualiza la web. Solo corre con la sesión iniciada.
$raiz = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path (Split-Path -Parent (Get-Command python).Source) "pythonw.exe"
$script = Join-Path $raiz "pc\actualizar.py"
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

# Tareas anteriores (cada 30 minutos y cierre a las 22:30)
Get-ScheduledTask -TaskName "AOVE al Dia - *" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false

# Una vez al día, lo que ocurra antes: a las 09:00 o al iniciar sesión (con 2 minutos para que haya red).
# actualizar.py se encarga de no repetir si ya se ha ejecutado hoy.
$alEntrar = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$alEntrar.Delay = "PT2M"
Register-ScheduledTask -TaskName "AOVE al Dia - actualizacion diaria" -Force -Settings $ajustes -Trigger @($alEntrar, (New-ScheduledTaskTrigger -Daily -At "09:00")) `
    -Action (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`" --completa" -WorkingDirectory $raiz) | Out-Null

Get-ScheduledTask -TaskName "AOVE al Dia*" | ForEach-Object { "$($_.TaskName): $($_.State)" }
