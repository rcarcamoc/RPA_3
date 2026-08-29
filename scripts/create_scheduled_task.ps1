# PowerShell Script para registrar el Servicio de Notificaciones en el Programador de Tareas de Windows

$TaskName = "RPA_Servicio_Notificaciones_Telegram"
$PythonExe = "c:\Desarrollo\RPA_3\venv\Scripts\python.exe"
$ScriptPath = "c:\Desarrollo\RPA_3\rpa_framework\servicio_bot_telegram.py"
$WorkDir = "c:\Desarrollo\RPA_3"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkDir

# Triggers: Al iniciar sistema (Boot), al iniciar sesión (Logon) y Diario a las 08:30 AM con despertar
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At "08:30"
$Triggers = @($TriggerStartup, $TriggerLogon, $TriggerDaily)

# Configuración avanzada: Despertar PC, disponible en batería, no duplicar instancias
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -Priority 4

$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest

Write-Host "🚀 Registrando tarea programada '$TaskName' en Windows para el usuario: $User..."

try {
    # Eliminar si ya existe
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Intentar registro completo con privilegios elevados y Boot
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal -Force -ErrorAction Stop | Out-Null
    Write-Host "✅ Tarea programada '$TaskName' registrada exitosamente (Boot, Login, Diario 08:30, WakeToRun, IgnoreNew)."
} catch {
    Write-Host "⚠️ No se pudo registrar con nivel Highest/Boot (requiere Admin). Intentando registro estándar de usuario (Login + Diario)..."
    try {
        $TriggersUser = @($TriggerLogon, $TriggerDaily)
        $SettingsUser = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -WakeToRun `
            -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)
        
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $TriggersUser -Settings $SettingsUser -Force | Out-Null
        Write-Host "✅ Tarea programada '$TaskName' registrada exitosamente (Login, Diario 08:30, WakeToRun, IgnoreNew)."
    } catch {
        Write-Host "❌ Error registrando la tarea programada: $_"
        exit 1
    }
}
