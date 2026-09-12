# 提交并推送，**自动适应网络**（直连 / 本地代理 两种都试）
#
# 背景：本仓库的远程是 GitHub，而本机网络环境**会变** ——
#   有时 `github.com:443` 被阻断、必须走本地代理（FlClash，127.0.0.1:10910）；
#   有时代理没开、但直连通。写死任何一种都会在另一种情况下推不上去
#   （实测：代理关掉后 `git push` 直接 `Failed to connect to 127.0.0.1 port 10910`）。
#
# 用法：
#   pwsh -File tools\push.ps1                      # 提交所有改动并推送
#   pwsh -File tools\push.ps1 -MessageFile msg.txt  # 用文件里的多行提交信息（推荐，避免中文引号被 PowerShell 吞掉）
#   pwsh -File tools\push.ps1 -NoCommit             # 只推送，不提交
#
# ⚠️ 提交信息含多行/中文标点时**务必用 -MessageFile**：`-m "..."` 里的中文引号
#    （“”）会被 PowerShell 当成字符串结束符，把消息截断并让 git 报 pathspec 错误。
[CmdletBinding()]
param(
    [string]$MessageFile,
    [string]$Message,
    [switch]$NoCommit,
    [string]$Branch = ""
)

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# ---- 1. 可选提交 ----
if (-not $NoCommit) {
    git add -A | Out-Null
    $staged = (git diff --cached --name-only | Measure-Object).Count
    if ($staged -eq 0) {
        Write-Host "[i] 没有待提交的改动"
    } else {
        if ($MessageFile) {
            $mf = if ([System.IO.Path]::IsPathRooted($MessageFile)) { $MessageFile }
                  else { Join-Path $repo $MessageFile }
            if (-not (Test-Path $mf)) { Write-Error "提交信息文件不存在: $mf"; exit 2 }
            git -c i18n.commitEncoding=utf-8 commit -F $mf | Out-Null
        } elseif ($Message) {
            git -c i18n.commitEncoding=utf-8 commit -m $Message | Out-Null
        } else {
            Write-Error "需要 -MessageFile 或 -Message"; exit 2
        }
        if ($LASTEXITCODE -ne 0) { Write-Error "提交失败"; exit 1 }
        Write-Host ("[OK] 已提交 {0} 个文件: {1}" -f $staged, (git log --oneline -1))
    }
}

# ---- 2. 确定分支与 remote ----
if (-not $Branch) { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() }
if ($Branch -eq 'HEAD') { Write-Error "处于 detached HEAD，无法推送"; exit 2 }
Write-Host "[i] 分支 $Branch"

# ---- 3. 依次尝试：直连 → 本地代理（哪个通用哪个）----
#    每次都**显式覆盖** repo-local 的 http.proxy，避免上次留下的配置干扰。
$attempts = @(
    @{ Name = '直连';   Args = @('-c', 'http.proxy=', '-c', 'https.proxy=') },
    @{ Name = '本地代理 127.0.0.1:10910'; Args = @('-c', 'http.proxy=http://127.0.0.1:10910',
                                                   '-c', 'https.proxy=http://127.0.0.1:10910') }
)

foreach ($a in $attempts) {
    Write-Host ("[..] 尝试 {0} 推送…" -f $a.Name)
    $out = & git @($a.Args) push origin $Branch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("[OK] 推送成功（{0}）" -f $a.Name)
        $out | Select-Object -Last 3 | ForEach-Object { Write-Host ("     " + $_) }
        Write-Host ("[i] " + (git status -sb | Select-Object -First 1))
        exit 0
    }
    Write-Host ("[!] {0} 失败：{1}" -f $a.Name, (($out | Select-Object -Last 1) -replace '\s+', ' '))
}

Write-Error "两种方式都推不上去 —— 检查：代理是否开启 / 网络是否可达 github.com:443"
exit 1
