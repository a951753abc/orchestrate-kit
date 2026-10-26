# 驗收清單：工單 #4（訂單列表加「出貨日」欄）

## 產物目錄

`C:/work/shop/.playwright-mcp/verify-wo4/`（session 工作目錄 `C:/work/shop` 下的 Playwright 預設輸出目錄；環境準備步驟 1 建立）

## 環境準備

1. 建產物目錄並重建前端（Bash）→ `C:/work/shop/.playwright-mcp/verify-wo4/00-build.txt`；失敗即停：產物檔末行不是 `rc=0`
   ```bash
   mkdir -p C:/work/shop/.playwright-mcp/verify-wo4 && { echo '$ npm run build && cat dist/build-id.txt'; npm run build 2>&1 && cat dist/build-id.txt; echo "rc=$?"; } > C:/work/shop/.playwright-mcp/verify-wo4/00-build.txt 2>&1
   ```
2. 確認 port 3000 沒被占用（PowerShell）→ `C:/work/shop/.playwright-mcp/verify-wo4/01-port-free.txt`；失敗即停：產物檔末行不是 `rc=0`
   ```powershell
   $s = { $c = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue); $c | Out-String; if ($c.Count) { throw 'port 3000 已被占用' } }; & { "`$ $s"; try { & $s; 'rc=0' } catch { $_; 'rc=1' } } *> C:/work/shop/.playwright-mcp/verify-wo4/01-port-free.txt
   ```
3. 以 Bash `run_in_background` 啟動 dev server → `C:/work/shop/.playwright-mcp/verify-wo4/02-dev-server.txt`
   ```bash
   npm run dev > C:/work/shop/.playwright-mcp/verify-wo4/02-dev-server.txt 2>&1
   ```
4. 等 dev server 可連線（Bash）→ `C:/work/shop/.playwright-mcp/verify-wo4/03-wait.txt`；失敗即停：產物檔末行不是 `rc=0`
   ```bash
   { echo '$ curl -s -o /dev/null -w "%{http_code}" --retry 20 --retry-connrefused --retry-delay 1 http://localhost:3000/login'; curl -s -o /dev/null -w "%{http_code}" --retry 20 --retry-connrefused --retry-delay 1 http://localhost:3000/login 2>&1; rc=$?; echo; echo "rc=$rc"; } > C:/work/shop/.playwright-mcp/verify-wo4/03-wait.txt 2>&1
   ```
5. `browser_navigate`（url：`http://localhost:3000/login`）；失敗即停：頁面打不開
6. `browser_evaluate`（function：`async () => { await Promise.all([...document.scripts].filter(s => s.src).map(s => fetch(s.src, { cache: 'reload' }))); location.reload(); }`，filename：`C:/work/shop/.playwright-mcp/verify-wo4/04-cache-reload.json`）
7. `browser_evaluate`（function：`() => document.querySelector('meta[name="build-id"]')?.content`，filename：`C:/work/shop/.playwright-mcp/verify-wo4/05-page-build-id.json`）

## 驗收步驟

1. `browser_snapshot`（filename：`C:/work/shop/.playwright-mcp/verify-wo4/11-login.md`）
2. `browser_type`（target：`#account`，element：帳號輸入框，text：`demo`）
3. `browser_type`（target：`#password`，element：密碼輸入框，text：`demo-pass`）
4. `browser_click`（target：`button[type=submit]`，element：「登入」按鈕）
5. `browser_snapshot`（filename：`C:/work/shop/.playwright-mcp/verify-wo4/12-after-login.md`）
6. `browser_navigate`（url：`http://localhost:3000/orders`）；失敗即停：頁面打不開
7. `browser_take_screenshot`（scale：`css`，fullPage：true，filename：`C:/work/shop/.playwright-mcp/verify-wo4/13-orders.png`）
8. `browser_snapshot`（filename：`C:/work/shop/.playwright-mcp/verify-wo4/14-orders.md`）
9. `browser_console_messages`（level：`info`，filename：`C:/work/shop/.playwright-mcp/verify-wo4/15-console.txt`）
10. `browser_network_requests`（static：false，filename：`C:/work/shop/.playwright-mcp/verify-wo4/16-network.txt`）

## 還原步驟

1. `browser_close`
2. 停掉環境準備步驟 3 啟動的 dev server：先確認 port 3000 listener 的命令列含 `C:\work\shop\`，才依 PID 終止整棵程序樹（PowerShell）→ `C:/work/shop/.playwright-mcp/verify-wo4/90-stop-dev.txt`
   ```powershell
   $s = { foreach ($id in @(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique)) { $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine; "PID $id 命令列：$cl"; if ($cl -notlike '*C:\work\shop\*') { throw "PID $id 的命令列不含 C:\work\shop\，不終止" }; taskkill /F /T /PID $id; if ($LASTEXITCODE) { throw "taskkill rc=$LASTEXITCODE" } } }; & { "`$ $s"; try { & $s; 'rc=0' } catch { $_; 'rc=1' } } *> C:/work/shop/.playwright-mcp/verify-wo4/90-stop-dev.txt
   ```
3. 記錄 working tree 狀態（Bash）→ `C:/work/shop/.playwright-mcp/verify-wo4/91-git-status.txt`
   ```bash
   { echo '$ git status --short'; git status --short 2>&1; echo "rc=$?"; } > C:/work/shop/.playwright-mcp/verify-wo4/91-git-status.txt 2>&1
   ```

## 禁止事項

- 只用 `demo` 帳號登入
- 不點訂單列表上的「刪除」「標記出貨」按鈕（會改寫本機測試資料）
- 不改 `.env.local` 的 port 設定
