param(
    [string]$ServiceName = "simulacion-final",
    [string]$RepoUrl = "https://github.com/juanitoppd/simulacion-final",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

function Convert-SecureStringToPlainText {
    param([securestring]$SecureValue)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Invoke-RenderApi {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $headers = @{
        "Accept" = "application/json"
        "Authorization" = "Bearer $script:RenderApiKey"
    }

    $uri = "https://api.render.com/v1$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
    }

    $headers["Content-Type"] = "application/json"
    $jsonBody = $Body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $jsonBody
}

Write-Host ""
Write-Host "Render deploy automatico para $ServiceName"
Write-Host "Repo: $RepoUrl"
Write-Host "Branch: $Branch"
Write-Host ""

$secureKey = Read-Host "Pega tu Render API Key" -AsSecureString
$script:RenderApiKey = Convert-SecureStringToPlainText $secureKey

Write-Host ""
Write-Host "Consultando workspaces de Render..."
$ownersResponse = Invoke-RenderApi -Method GET -Path "/owners?limit=100"
$owners = @($ownersResponse)
if ($ownersResponse.psobject.Properties.Name -contains "owners") {
    $owners = @($ownersResponse.owners)
}
elseif ($ownersResponse.psobject.Properties.Name -contains "data") {
    $owners = @($ownersResponse.data)
}

if ($owners.Count -eq 0) {
    throw "No se encontraron workspaces para esta API Key."
}

if ($owners.Count -eq 1) {
    $owner = $owners[0]
}
else {
    Write-Host ""
    Write-Host "Workspaces disponibles:"
    for ($i = 0; $i -lt $owners.Count; $i++) {
        Write-Host "[$($i + 1)] $($owners[$i].name) - $($owners[$i].id)"
    }
    $selection = Read-Host "Elige el numero del workspace"
    $index = [int]$selection - 1
    if ($index -lt 0 -or $index -ge $owners.Count) {
        throw "Seleccion invalida."
    }
    $owner = $owners[$index]
}

Write-Host ""
Write-Host "Workspace: $($owner.name) ($($owner.id))"
Write-Host "Creando Web Service en Render..."

$body = @{
    type = "web_service"
    name = $ServiceName
    ownerId = $owner.id
    repo = $RepoUrl
    branch = $Branch
    autoDeploy = "yes"
    serviceDetails = @{
        runtime = "python"
        plan = "free"
        buildCommand = "pip install -r requirements.txt && python main.py --salida assets"
        startCommand = "gunicorn src.app:app"
        env = "python"
    }
}

try {
    $created = Invoke-RenderApi -Method POST -Path "/services" -Body $body
}
catch {
    Write-Host ""
    Write-Host "Render no pudo crear el servicio con ese nombre."
    Write-Host "Si ya existe como Static Site, crea uno nuevo con otro nombre:"
    Write-Host ".\scripts\deploy_render.ps1 -ServiceName simulacion-final-web"
    Write-Host ""
    throw
}

$service = $created.service
Write-Host ""
Write-Host "Servicio creado correctamente:"
Write-Host "ID: $($service.id)"
Write-Host "Dashboard: $($service.dashboardUrl)"
Write-Host ""
Write-Host "Render ya debe estar construyendo el deploy inicial."
Write-Host "Cuando termine, abre la URL .onrender.com que aparece en el dashboard."
