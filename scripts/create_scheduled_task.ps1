# PowerShell Script para registrar el Servicio de Notificaciones en el Programador de Tareas de Windows

$TaskName = "RPA_Servicio_Notificaciones_Telegram"
$PythonExe = "c:\Desarrollo\RPA_3\venv\Scripts\pythonw.exe"
$ScriptPath = "c:\Desarrollo\RPA_3\rpa_framework\servicio_bot_telegram.py"
$WorkDir = "c:\Desarrollo\RPA_3"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "pythonw.exe"
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkDir

# Triggers: Tanto al iniciar el sistema (Boot) como al iniciar sesión (Logon)
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$Triggers = @($TriggerStartup, $TriggerLogon)

# Configuración avanzada: Sin límite de tiempo, disponible en batería, reinicio en fallo
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host "🚀 Registrando tarea programada '$TaskName' en Windows para el usuario: $User..."

try {
    # Eliminar si ya existe
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Registrar nueva tarea con ambos desencadenadores
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings -Force | Out-Null
    
    Write-Host "✅ Tarea programada '$TaskName' registrada exitosamente con inicio en Boot y Login."
} catch {
    Write-Host "❌ Error registrando la tarea programada: $_"
    exit 1
}
