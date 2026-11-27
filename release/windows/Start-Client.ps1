# 从相邻组合版读取登录地址，允许 Windows 玩家用本地配置或命令行覆盖。
param(
    [string]$ServerAddress,
    [ValidateRange(1, 65535)]
    [int]$LoginPort,
    [switch]$ShowConnection
)
$ErrorActionPreference = 'Stop'
$values = @{ SERVER_PUBLIC_IP = '127.0.0.1'; LOGIN_PORT = '18101' }
$composeConfig = Join-Path (Split-Path -Parent $PSScriptRoot) 'wendao163-compose\.env'
$localConfig = Join-Path $PSScriptRoot 'server.env'
foreach ($file in @($composeConfig, $localConfig)) {
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        foreach ($line in Get-Content -LiteralPath $file) {
            if ($line -match '^\s*(?:export\s+)?(SERVER_PUBLIC_IP|LOGIN_PORT)\s*=\s*(.*?)\s*(?:\s+#.*)?$') {
                $values[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
            }
        }
    }
}
if (-not $PSBoundParameters.ContainsKey('ServerAddress')) {
    $ServerAddress = $values.SERVER_PUBLIC_IP
}
if (-not $PSBoundParameters.ContainsKey('LoginPort')) {
    if (-not [int]::TryParse($values.LOGIN_PORT, [ref]$LoginPort)) {
        throw 'Invalid LOGIN_PORT in connection settings.'
    }
}
$address = $null
if (-not [System.Net.IPAddress]::TryParse($ServerAddress, [ref]$address) -or
    $address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $address.ToString() -ne $ServerAddress -or $ServerAddress -eq '0.0.0.0') {
    throw 'Enter the IPv4 address that this Windows PC can reach.'
}
if ($LoginPort -lt 1 -or $LoginPort -gt 65535) {
    throw 'LOGIN_PORT must be between 1 and 65535.'
}
if ($ShowConnection) {
    Write-Output ("${address}:${LoginPort}")
    exit 0
}
# 使用原生客户端的直接连接参数，区名由 GBK 字节生成以兼容 Windows PowerShell 5.1。
$realm = [Text.Encoding]::GetEncoding(936).GetString([byte[]](0xbb,0xf0,0xca,0xf7,0xd2,0xf8,0xbb,0xa8))
$binary = Join-Path $PSScriptRoot 'asktao.mod'
if (!(Test-Path -LiteralPath $binary -PathType Leaf)) {
    throw 'Client files are missing. Extract all volumes of the Windows client into one directory.'
}
$info = New-Object System.Diagnostics.ProcessStartInfo
$info.FileName = $binary
$info.WorkingDirectory = $PSScriptRoot
$info.UseShellExecute = $false
$info.Arguments = "$realm;$address;$LoginPort;kbd:0;swictch:0;paroxy:0;flag:;uncheck"
$info.EnvironmentVariables['__COMPAT_LAYER'] = 'WIN7 DISABLEDXMAXIMIZEDWINDOWEDMODE'
[void][System.Diagnostics.Process]::Start($info)
