# 每轮训练后把经验同步到 GitHub。
#
# 用法：
#   .\tools\sync.ps1 -Message "第 2 轮：从参考成片归纳节奏规则"
#   .\tools\sync.ps1 -Message "..." -SkipPush     # 只提交不推送
#
# 注意：本机访问 GitHub HTTPS 需要代理（FlClash）。脚本会自动探测常见端口，
#       并把代理写进本仓库的 .git/config（不污染全局配置）。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Message,

    [switch]$SkipPush
)

$ErrorActionPreference = 'Stop'

# 切到仓库根目录（脚本位于 tools/ 下）
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> 仓库: $root" -ForegroundColor Cyan

# ---- 1. 确保代理可用 ----
if (-not $SkipPush) {
    $configured = (git config --local --get http.proxy)
    $probePorts = @(10910, 7890, 7897, 10809, 1080)

    if ($configured -match ':(\d+)') {
        $probePorts = @([int]$Matches[1]) + ($probePorts | Where-Object { $_ -ne [int]$Matches[1] })
    }

    $alive = $null
    foreach ($port in $probePorts) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $client.Connect('127.0.0.1', $port)
            $alive = $port
            break
        } catch {
            # 端口未开，继续试下一个
        } finally {
            $client.Dispose()
        }
    }

    if (-not $alive) {
        Write-Host "!! 未发现可用代理（探测端口: $($probePorts -join ', ')）。" -ForegroundColor Yellow
        Write-Host "   仍继续提交；推送阶段会自行诊断是被沙箱还是被网络挡住。" -ForegroundColor Yellow
    } else {
        git config --local http.proxy  "http://127.0.0.1:$alive"
        git config --local https.proxy "http://127.0.0.1:$alive"
        Write-Host "==> 代理: 127.0.0.1:$alive" -ForegroundColor Cyan
    }
}

# ---- 2. 提醒更新经验日志 ----
$lessons = Join-Path $root 'docs/lessons.md'
if (Test-Path $lessons) {
    $dirty = git status --porcelain -- $lessons
    if (-not $dirty) {
        Write-Host "提示: docs/lessons.md 本轮没有改动，确认经验已记录？" -ForegroundColor Yellow
    }
}

# ---- 3. 提交 ----
git add -A

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "==> 没有需要提交的改动" -ForegroundColor Yellow
    if (-not $SkipPush) { git push }
    exit 0
}

Write-Host "==> 暂存文件：" -ForegroundColor Cyan
$staged | ForEach-Object { Write-Host "    $_" }

git commit -m $Message
if ($LASTEXITCODE -ne 0) { throw "git commit 失败" }

# ---- 4. 推送 ----
if ($SkipPush) {
    Write-Host "==> 已提交（按要求跳过推送）" -ForegroundColor Green
    exit 0
}

# ⚠️ 本脚本开头是 $ErrorActionPreference = 'Stop'，而 git 把 SSL 错误写到 stderr：
#    用 `2>&1` 捕获时，PowerShell 会把它变成**终止性错误**，脚本会在下面的判断之前就挂掉，
#    诊断信息根本来不及打印（实测踩过）。所以这里必须临时切回 Continue。
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$pushOut = & git push 2>&1
$pushCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap

if ($pushCode -ne 0) {
    $pushOut | ForEach-Object { Write-Host $_ }
    if (($pushOut -join ' ') -match 'SEC_E_NO_CREDENTIALS|AcquireCredentialsHandle') {
        Write-Host "!! 推送失败：**不是网络问题**，是执行环境限制了 schannel/SSPI 的 TLS 凭据初始化。" -ForegroundColor Red
        Write-Host "   本轮提交已在本地完成（未丢）。修法：以更宽权限重跑本脚本，或人工 git push。" -ForegroundColor Yellow
        exit 3
    }
    Write-Host "!! 推送失败。检查代理是否运行、凭据是否有效。" -ForegroundColor Red
    exit 1
}

Write-Host "==> 推送完成" -ForegroundColor Green
git log --oneline -3
