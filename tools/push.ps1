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

            # ⚠️ **主动拒绝含引号或换行的 -Message**。
            # 中文提交信息里常出现中文引号，而 PowerShell 会把它们当成字符串结束符，
            # 把消息**截断**、剩余部分变成位置参数 —— 最终 git 只报一句
            # `error: switch 'F' requires a value`，完全看不出真因。本项目已踩过两次。
            if ($Message -match '[\u201c\u201d\u2018\u2019"]' -or $Message.Contains([char]10)) {
                Write-Error "-Message 含引号或换行，会被 PowerShell 截断（已踩过两次）。请写进文件并改用 -MessageFile <路径>。"
                exit 2
            }
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



# ---- 3. 依次尝试：直连 → 本地代理，**来回两轮** ----

#    每次都**显式覆盖** repo-local 的 http.proxy，避免上次留下的配置干扰。

#    ⚠️ 为什么要两轮：本机网络会在"直连通 / 代理通 / 都不通"之间变。

#    实测过一次：第一轮直连失败、代理也报 `Failed to connect to 127.0.0.1 port 10910`，

#    但**紧接着手工再走代理就成功了** —— 代理是那一刻才起来的。

#    所以别把"一次失败"当结论，压短超时重试一轮更实用。

$attempts = @(

    @{ Name = '直连';   Args = @('-c', 'http.proxy=', '-c', 'https.proxy=') },

    @{ Name = '本地代理 127.0.0.1:10910'; Args = @('-c', 'http.proxy=http://127.0.0.1:10910',

                                                   '-c', 'https.proxy=http://127.0.0.1:10910') }

)

# 压短连接超时（默认 21s × 两路太慢）

$env:GIT_HTTP_CONNECT_TIMEOUT = '8'

$env:GIT_HTTP_LOW_SPEED_LIMIT = '1000'

$env:GIT_HTTP_LOW_SPEED_TIME  = '20'

# 记录是否撞上『沙箱挡住 schannel/SSPI』——它长得像网络问题，但不是。
$sandboxBlocked = $false



foreach ($round in 1..2) {

    foreach ($a in $attempts) {

        Write-Host ("[..] 第 {0} 轮 · 尝试 {1}…" -f $round, $a.Name)

        $out = & git @($a.Args) push origin $Branch 2>&1

        if (($out -join ' ') -match 'SEC_E_NO_CREDENTIALS|AcquireCredentialsHandle') {
            $sandboxBlocked = $true
        }

        if ($LASTEXITCODE -eq 0) {

            Write-Host ("[OK] 推送成功（{0}）" -f $a.Name)

            $out | Select-Object -Last 3 | ForEach-Object { Write-Host ("     " + $_) }

            Write-Host ("[i] " + (git status -sb | Select-Object -First 1))

            exit 0

        }

        Write-Host ("[!] {0} 失败：{1}" -f $a.Name, (($out | Select-Object -Last 1) -replace '\s+', ' '))

    }

}



# 先判沙箱：这种情况两路都会挂，且 `git ls-remote` 也一样挂，跟代理/网络无关。
if ($sandboxBlocked) {

    Write-Host "[!] 诊断：**不是网络问题** —— 是执行环境限制了 schannel/SSPI 的 TLS 凭据初始化。" -ForegroundColor Red

    Write-Host "    判据：git ls-remote 也会报同样的 SEC_E_NO_CREDENTIALS。"

    Write-Host "    修法：以更宽权限重跑本脚本，或人工在终端执行 git push。"

    exit 3

}

Write-Host "[i] 诊断提示（本机实测）："

Write-Host "      github.com:443        —— 常被墙，直连会挂"

Write-Host "      ssh.github.com:443 / github.com:22 —— 往往仍通（可改用 SSH remote）"

Write-Host "      127.0.0.1:10910       —— 本地代理（FlClash 等），没开就没有这一路"

Write-Error "两种方式 × 两轮都推不上去 —— 检查代理是否开启 / 网络是否可达 github.com:443"

exit 1

