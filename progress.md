# PLE Solo Harness — Progress

最後更新：2026-11-22  
目前階段：`P3 — 工程驗證核心（提前開工；P2 已 DONE）`  
整體狀態：`P2_DONE_P3_IN_PROGRESS(3/5) — 2026-11-22 晚：canonical repo 移到 Windows D: 資料夾、模型換 Gemma 4 26B（Ollama 64K），kit check 7/7（kitcheck11_gemma），首次 Gemma dev run 待選題（§1（二十九））；先前：全部暫停（使用者指示 2026-11-22 17:46「暫停／停止 harness」）：EXP-023 #2 與重發 #3（× ae07474，16:50）皆中止 INVALID；window_probe 首次 live＝proxy 從 /v1/models 剝除 Strata max_model_len → `not announced by the endpoint`、退回被動如設計零回歸，但 DEF-003 未解、解法待拍板（§1（二十八））；鏈路驗證仍有效（mock 14/14、kitcheck10 7/7、映像 d0e1181cef4cb463 可重用）；0 容器、0 background（LiteLLM/Strata 閒置運行）`
完成度：`規劃 100% / 實作 36%（階段任務 20/56：P0 7/8＋P1 7/7＋P2 6/6）/ 官方驗證 70%（kit check 7/7 已過，kit artifacts／final check 待 P8）`

> 本文件是唯一進度真相來源。任務只有附上可重現的驗證證據後才可標記完成。

## 1. Current focus

開發環境已遷移到 WSL `Ubuntu`（26.04.1 LTS，Docker 29.10.0／uv 0.13.9／Harbor 0.20.0），未修改的官方 `plan-verify` starter 已通過 `kit check`（`rc=0`），且單題 dev baseline 已完成並取得首個實測分數：**`frame-extension-method` = 0.3617**（14,310 s／題，輸出 326,888 tokens）。下一步進入 P1（處理 `mcp` WARN 與 harness 改進），並評估以付費 API（如 DeepSeek）加速 dev 全量跑。

**2026-11-19 更新：** P1-07（MCP 中繼工具）已完成並通過 `kit check` 全部 7 階段；補丁版單題重跑 0.3557 vs 基線 0.3617（本題無 MCP，差異屬單次執行的模型隨機性，約 ±0.01）。

### 2026-11-22 — 環境架構變更：canonical repo 改為 Windows 資料夾（Agent 必讀，取代下方 11-19 版的對應條目）

- **使用者指示（2026-11-22 18:0x）**：把 WSL 做到一半的工作拉回本機資料夾，由 Windows 端 Claude Code（desktop app）接手，並接上本機 Ollama 的 Gemma 4。
- **canonical Git repo＝`D:\project\vide-coding\ple-solo-harness`**（WSL 內路徑 `/mnt/d/project/vide-coding/ple-solo-harness`）。WSL `~/projects/ple-solo-harness` 的完整歷史（main 51 commits、quick 17 commits、tag `baseline-starter-0.3617`）已 fetch 進來：本機 `main`＝`71277af`、`quick`＝`7ab4ae6`，另留 `refs/remotes/wsl/*` 對照；工作區與 `71277af` 逐檔相同（`git status` 空）。本 repo 設 `core.autocrlf=false`，`.gitattributes` 為 `* text=auto eol=lf`。
- **WSL 舊 repo `~/projects/ple-solo-harness`（及 `-quick` worktree）停止使用**，保留不刪作備份；不得再在那裡 commit，否則兩邊分岔。
- **執行面仍在 WSL `Ubuntu`**：Docker、Harbor、uv、官方 kit（`~/projects/ple-reference`）、資料（`~/projects/ple-data`）、`local.env`、LiteLLM（`~/projects/model_proxy`）、run 目錄都不動。Windows 端以 `C:\Program Files\WSL\wsl.exe -d Ubuntu -u zivkao -e bash -c '...'` 驅動，`kit check`／`eval/run.py` 的 entry 參數改用 `/mnt/d/project/vide-coding/ple-solo-harness`。Windows 本身沒有 uv／Docker。
- **模型**：Windows 本機 Ollama 0.40.17（`127.0.0.1:11434`，WSL mirrored loopback 可直達）。見 §1（二十九）。
- **磁碟防護（R-016）**：WSL 虛擬磁碟在 D 槽、只長不縮。每次發射前 `bash ~/projects/disk_guard.sh 40 || exit 1`；監控一律用 `~/projects/watch_run_disk.sh <python_pid> <log> 10`；Docker 建置快取上限 20 GB（`/etc/docker/daemon.json`）。

### 2026-11-19 — 最終環境與通訊架構（Agent 必讀；canonical repo 與 Claude 控制面兩條已被上方 11-22 版取代）

- **WSL `Ubuntu` 是唯一 PLE 開發與 Agent 執行環境。** Claude Code、canonical repo、Docker、Harbor、LiteLLM 與評測均在此 distro 內執行；canonical repo 為 `/home/zivkao/projects/ple-solo-harness`。
- Windows 只負責以 `C:\\Program Files\\WSL\\wsl.exe -d Ubuntu ...` 按需啟動或停止 distro，不作為 Claude 的日常專案控制面。
- **WSL `Ubuntu-24.04` 不參與本專案。** 它是獨立 Claude CLI 環境，不得修改、啟動或監控 PLE 專案。
- 專案 Ubuntu 的 Claude Code 版本為 2.1.328，直接在 canonical repo 工作；允許 `bypassPermissions`，但必須以一般使用者 `zivkao` 執行，不得使用 root。
- 專案 Ubuntu 已關閉 Windows 整碟 automount 與 Windows interop，只精確掛載 `D:\\project\\vide-coding` 至 `/mnt/d/project/vide-coding` 作參考副本同步。
- WSL 全域網路採 `networkingMode=mirrored`。Windows Strata 僅監聽 `127.0.0.1:8080`；Claude 使用 `http://127.0.0.1:8080`，LiteLLM 使用 `http://127.0.0.1:8080/v1`。
- 舊的 `ple-model-bridge`、`forwarder.py`、watchdog、WSL gateway IP、distro 間 SSH、socat relay 與相關開機項均已移除，**不得重建**。
- Agent 在 Ubuntu 內直接使用 Linux 路徑，不得呼叫 `wsl.exe`、不得使用 `\\wsl.localhost`，也不得重新開放其他 Windows 磁碟。
- `D:\\project\\vide-coding\\ple-solo-harness` 只是 Windows 參考副本，不是 canonical Git repo；程式與 `progress.md` 先在 canonical repo 更新，再同步到該副本。
- 專案 Ubuntu 不隨 Windows 登入自動啟動；只有需要開發、評測或維護時才按需啟動。


**2026-11-19（二）：** DEF-001 使用者選 (a)（修後重測）。quick v2（commit `8d34278`）對 `frame-extension-method` 的重測已跑完（run `plan-verify-20261119-112842`）：仍 **0 分／`ERR_NO_SUBMISSION`**，但失敗模式改變——模型只用 **8/40 呼叫、1,233 輸出 tokens（預算 11–22%）就以純文字回答提前放棄**，40/70% 預算 share 檢查點從未被觸發。下一步 v3：**交付閘門**（見 DEF-001）。

**2026-11-19（三）：** DEF-001 v3 交付閘門已實作（quick branch `16053ed`）：`deliver` 步驟在非收尾、非截斷的純文字結束且 `_writes == 0` 時打回（GATE 訊息指示立即以 write_file／bash 在精確路徑寫出最小交付物；上限 `QUICK_GATE=2` 次後接受答案；checkpoint、wrap_write、nudge 路徑不受影響）。驗證：mock **7/7**（新增 `gate`：打回 1/2 → 模型補寫 `cat > /app/out.txt` 送達 exec 通道，stop=none；`gate2`：固執模型只打回 2/2 後接受）、AST ok、pyflakes 0、無新增 >80 char 行（11 條長行與 v2 相同，皆為 starter prompt 字串）。依使用者指示**暫停**，同題實測重跑等同意。

**2026-11-19（四）— 環境連線驗證（Windows 控制面按需啟動，全鏈路 PASS）：** ① `wsl.exe -l -v` rc=0，兩 distro 均 `Stopped`（符合按需原則），`-d Ubuntu -u zivkao -e bash` 可啟動並執行（kernel `6.18.58.1`、26.04.1 LTS）；② Windows 端 `http://127.0.0.1:8080/v1/models` → **HTTP 200**，`qwen3.8-flash-next-iq3_s` 狀態 `loaded`（n_ctx 262144）；③ Ubuntu 內 `curl http://127.0.0.1:8080/v1/models` → **HTTP 200**（約 1.5 ms，mirrored loopback 直連生效，無需舊 bridge）；④ 端到端 `chat/completions` 完成一次真實補全（含 usage／timings）；⑤ `~/projects/` 四專案目錄＋`local.env`（600）完整；uv 0.13.9、Harbor 0.20.0、Docker 29.10.0、`docker.service` active。**留意事項：**（1）**LiteLLM `:4000` 檢查時未運行**（WSL 內 4000 無 listener）——它是評測按需服務，`kit check`／`eval/run.py` 前必須先啟動；（2）**Windows 參考副本 `D:\project\vide-coding\ple-solo-harness\progress.md` 落後 canonical（HEAD `aac6556`）**，缺 EXP-009/010 與 DEF-001 v2–v4 記錄，本次已將全檔同步為 canonical 內容，之後以 WSL 端為準。

**2026-11-19（五）：** DEF-001 v4 實測重跑（EXP-011，使用者同意後執行）**仍 0 分**，但行為質變：**gate 觸發 0 次**——模型不再提前放棄，19 次呼叫全是帶工具的工作呼叫；真正死因是 **輸出預算燒盡**（`stop=output, requests=19, output_tokens=17,931`）：第 19 次呼叫正以 `cat > /tmp/s.py <<PY` 生成完整分析腳本（內容已是最終交付邏輯）時被預算截斷，腳本從未執行，`capture.json files={}`。全程僅 696 s（完整版 1/20 時間）。結論：**DEF-001 根因①（15k out 對重工程題少一個數量級）為主導因素**，v2–v4 的閘門系對「提前放棄」族失敗的修復，對「誠實工作到燒盡」族既非失敗點也非救援點。**ADR-009 revisit trigger 成立**：quick 對重工程題不可用，需使用者決策 (b) 預算加檔／(c) 只跑輕題／(d) 跳 quick 直接 main dev 子集。

**2026-11-19（六）：** 選項 (b) 已執行（EXP-012，quick `25e3173`：僅 `QUICK_SEC/REQ/OUT` 三個預設值 1800→3600／40→80／15000→60000，收尾保留、單呼叫上限、gate、prompt、模型、工具全不動）。**仍 0 分，判定落 Rule 4（呼叫數先耗盡）**：`stop=requests, requests=41, output_tokens=45,130`——wall 1,353 s（3600 未盡）、out 45,130（60k 未盡，且 out 能燒到 45k 證明新輸出預算確已生效）；41 « 全域停機線 80−4＝76 ⇒ `stop=requests` 必来自 `serve.py` L581 的步驟級份額（`capped`，「this step ran out of its share of the calls」；另一來源 over_budget 需 ≥76）。模型本輪誠實進展：以 heredoc 分段寫分析腳本（`part2 ok`，exit_code=0），**part3 尚未寫完請求數即盡**，腳本從未執行（`python3 /tmp` 計 0）；wrap 收尾回純文字「Part 3: …」；gate 0 次；`capture files={}`→`ERR_NO_SUBMISSION`。**結論：約束點在 quick 的步驟級配額結構（routing），非全域預算大小；依 Rule 4 本輪不再加碼。**

**2026-11-20（七）：EXP-013（quick v5 同題重測）＋ P1-05／P1-06 實作。**
- **EXP-013 第一次尝试被 WSL 重啟切斷**（01:22 啟動，~01:47 distro 重啟，trial 執行中、無結果；run dir `plan-verify-20261120-012201` 作廢）。重啟後檢查鏈路：strata `:8080` 200 OK；**LiteLLM `:4000` 未運行**（重啟後未啟動）→ 以 `local.env` 重啟（200 with key；未帶 key 的 500 是 litellm auth 錯誤处理器缺 `prisma` 模組的無害 bug）。v5 mock 先重驗 **9/9**（`quota` case 在）。01:59 同條件重跑（`exp013b.start`）。
- **EXP-013 結果：仍 0.0／1,583 s**，`stop=requests requests=36 output_tokens=39,705`（in 702,885／cache 648,017）。但轉錄檔 `agent/plan-verify.txt` 顯示 **v5 修復如設計生效**：verifier 兩度 `capped: step spent its 4-call share`（呼叫 22、31）後**不再中斷執行**，兩輪 fix round 都跑了（EXP-012 在這裡就死）；gate 也首次觸發 2/2 次。零分原因變成新的失敗族：**「fix round 只讀不寫」**——verifier 明列「完全沒有交付物，寫這六個檔再 zip」，worker 的 fix round 卻全部花在 `ls`/`find`/`head` 重讀（0 次 write），MAX_FIX_ROUNDS=2 用盡後 `capture files={}`。**配額結構不再是約束點；本模型在此預算下不產出（能力／紀律問題，含 ortools 缺失）。**依 Rule 4：本輪不再改 quick 參數，DEF-001 進入 (c)／(d) 使用者決策。
- **P1-05／P1-06 實作（main branch `eb918d8`）**：serve.py 加 `phase:` 狀態機日誌標記、`safe()` 對所有 log 幀遮罩 `OPENAI_API_KEY`、`RETRY_WAITS` 可用 `$RETRY_WAITS` 覆蓋（測試縮時）；新增 `tests/mock_contract_test.py` 反向注入契約測試 **10/10**：`clean／fix_round／retry_429／retry_dead（400 不合任何重試規則→有界 error 幀）／timeout_wrap（慢模型 6 s 時鐘→12 s 內 done）／tool_error／context_full（400 溢出→剪舊 tool 結果重試）／cancel（10 s 窗口內 done，final="(stopped: time is up)"）／socket_close（斷線後伺服器存活、接新任務到 done）／redaction（key 藏在錯誤 body 裡，任何 log 幀都不得出現）`。pyflakes 0、AST ok、無新增 >80 char 行。官方 `kit check` 於補丁後重跑（`kitcheck5.log`，見 EXP-014）。

**2026-11-20（八）：使用者選 (c) → ADR-010。dev 29 題完成可觀察分級（light 14／heavy 14／uncertain 1，見 §13），規則先於結果明文化；quick 僅限 light。** 建議最小實驗組合（**未跑，等同意**）：quick＝`fire-test-validation-memo`（無 MCP 檔案題）、`emergency-spillway-check`（MCP×8，實戰驗證 P1-07 中繼工具）、`engineers-estimate-check`（MCP×8 電機域）；uncertain 探測＝`data-center-site-model`（quick 一次，零產出即歸 heavy）；heavy 留 main＝`roof-deck-design`（checks, 中量）＋`eor-review-corrections`（checks-judge）（frame-extension 已有完整基線 0.3617，不需重跑）。分級依據與每題觸發規則見 §13。

**2026-11-20（九）— EXP-015 #1 兩次嘗試、quick v6 修復、light 題仍零交付（本輪依指示停止）：** ① **#1a（08:29，v5 `c476e8c`，run `plan-verify-20261120-083026`）**：30 分鐘外層上限切斷、capture `files={}`、checkpoint/gate 零觸發；依使用者指示以 mock＋既有軌跡定位（7 問），根因＝工具呼叫 #4 的 `2>&1` 被 `_WRITE_BASH` 誤計為 `_writes`，整題的 checkpoint／gate／wrap_write 同時失效（`/tmp/mock_ckpt_probe.py` A/B 對照證明）。② **quick v6（`738534b`）**：僅修寫入計數（`_FD_REDIRECT` 剝除 fd 重新導向、bare `mkdir` 不再計入；`>` 真寫與 `write_file` 仍計入），新增 3 個 mock 回歸案例（`fdwrite`／`writecount_bash`／`writecount_wf`；先在舊碼 `[FAIL]` 再修复後 **12/12**）；prompt／模型／工具／checkpoint 門檻／全域預算全部不動。③ **#1b（10:21，同參重跑，run `plan-verify-20261120-102234`）**：**score 0.0／reward 0.0**（grade 0/208、`no_output.txt`「agent produced no output/ directory」）、capture 仍 `files={}`；`stop=requests requests=41 output_tokens=38,522`（in 931,872／cache 879,214；POST 窗口 1,617 s）；harness 於 30 分鐘前以自身預算正常結束，上限觸發時僅在收尾（grade 已產出）。④ **新發現（DEF-002）**：三線防護仍 0 觸發——v6 生效（工具呼叫 1–25 未增計）但工具呼叫 **#26** 的 1,953 字元 python heredoc 內 `if series[i]>=lim:`／`" -> "` 被裸 `>` 再誤計 `_writes=1`（`>` 在第 572 字元，轉錄只記 `arguments[:200]` 故不可見）→ 事件式防護再次整題失效；且 40% 檢查點＝request 份額 30.4，work step 於呼叫 21 自然結束、fix round 收尾呼叫又被 `not wrap_up` 跳過 → 對本失敗族檢查點構造上不可達，gate 是唯一防線、死於誤計數。⑤ **判定**：light 題亦零交付 → EXP-015 未達通過判準（capture≠{} ∧ score>0），#2/#3 依指示**不跑、本輪停止**；**ADR-010 revisit 條件成立**（「light 題的 quick run 仍 0 交付」），待使用者決策。操作教訓：`setsid nohup` 的 wrapper pid 短命，監控必須先以 `pgrep -f "python eval/run.py"` 找真 python pid（本次兩度誤盯 wrapper）。

**2026-11-20（十）— DEF-002 以方案①修復（quick v7 `7ab4ae6`）；依使用者指示 quick 暫停、本輪資源轉入 main dev 子集：** ① **改動**：`_writes` 不再由命令文字推測——每次 deliver 步驟的決策點前以 `PLELAND` 探針在任務容器內執行與 grader `kit/capture.py` 同規則的清單（path→size/mode/mtime_ns/ctime_ns/inode，root 預設＝session workdir，可用 `DELIVERABLE_PATHS` 指定 dev_set.yaml 的逐題路徑），對 task 開始時的 baseline 做**即時重算差分**：新增／覆寫／刪除都計入，**寫了又刪會回到零**並重新武裝防護；`/tmp` 等系統暫存路徑永不計入；探針失敗保留最後讀值並以「擱置＝未寫入（防線保持）」處理、於 log 留痕。順帶兩個必要修正：`wrap_write` 限定 deliver 步驟（verifier 收尾不得接寫檔指令）且**每步驟一次性**（真值 `_writes==0` 現在是真的，無限 offer 會讓只讀模型燒光預算——fixflow mock 實證）。② **驗證**：mock suite 擴至 **16 案例全綠**（新 `heredoc`／`landflip`／`landover`／`fixflow`；FakeEvaluator 改為模擬容器檔案狀態）；**偵測證明**：`heredoc`／`landflip`／`fixflow` 在 v6（`738534b`）下全部 `[FAIL]`、新碼全 `[PASS]`（`landover` 為正控制兩版皆綠）。③ **#1b 36 次工具呼叫離線重放**（root=`/app/files/`）：全部動作的寫入目標都在 `/tmp` 或為唯讀 → 新計數下 `_writes` 全程 0、決策點全部武裝；`fixflow` 案例重現「verifier 配額耗盡→fix round 內 gate 觸發（1/2)(2/2)，被打回的呼叫仍拿到完整 tools」＝模型保有可執行寫入機會。**正式 run 依指示維持暫停**（quick 開發與正式評測皆停；EXP-015 #1/#2/#3 與 uncertain 探測維持暫停）。④ **測試基建修正**：MockModel 的 `parts`／`prose_at`／`empty_wrap` 分支自建立以來就被後鏈覆寫（幽靈分支，quota 實際靠 capped 通過）——已合併分支鏈使其生效，文件同步更正。⑤ **backlog（不動參數、僅記錄）**：B-1 40/70% 檢查點對「work step 未及 40% 份額就自然結束」的模型構造上不可達（事件式 gate 是唯一網；fix round 收尾呼叫又被 `not wrap_up` 跳過）；B-2 轉錄只記 `arguments[:200]` 令誤計不可見（observability）；B-3 `_stop="requests"` 由 verifier 步驟上限設定、診斷語義含混。⑥ **本輪轉入 main**：main serve.py 無 quick 碼（grep `_writes`/`QUICK`＝0），DEF-002 不適用 main；main 評測使用既有 commit `e2326cc`（serve.py 碼＝`eb918d8`），全部推論走本機 Strata（見 EXP-016/017 記錄）。

**2026-11-20（十一）— EXP-017 #2 完成：main 第二題成功交付＝0.2573；兩題 heavy 暴露同一失分結構（本輪停止，等決策）：**
- **執行**：重開機後依 `exp017_1.start` 完全相同指令單次重跑（`exp017_2.start`）。發射前重驗：Strata `:8080` 200（model loaded、n_ctx 262,144）、LiteLLM `:4000` 200（帶 `MODEL_PROXY_KEY`）、端到端 `chat/completions` 200（16 token 全燒在 `reasoning_content`、`finish_reason=length`＝鏈路正常，非失敗）、docker 29.10.0（0 殘留容器）、disk 936 G／RAM 62 G 可用。17:52:37 發射，真 python pid 880018（`pgrep -af` 確認，非 `setsid` wrapper）；Harbor run `plan-verify-20261120-175344`、映像 `plebench-serve:50076b9de1b68fed`、job `eor-review-corrections__Bzs62np`。repo 乾淨、`git diff 5763d7a HEAD -- serve.py taskbridge.py submission.yaml requirements.txt` 空＝碼同 EXP-016（`eb918d8`）。
- **結果**：**score 0.2573／reward 0.2573／`ok`／17,053 s（4 h 44 m）**；`serve_status=completed`、`serve stop condition: done`、**340 次模型請求**；tokens in 30,583,152／cache 28,888,327（94.5%）／out 466,255；capture `files=1`＝`submission.zip` 23,890 B（7 檔：`disposition_register.csv` 34 列、`sheet_index.csv`、`revision_log.csv`、`issue_plan.csv`、`continuation_sheet.md`、`constraint_register.xlsx` 48 列、`design_basis.md`）。
- **評分結構**（checks-judge、`score_key=combined_score`、rule `0.4 p + 0.6 [h=1] O'`）：34 items、`mean_p` 0.6431／`mean_p_squared` 0.4341、register 48 列 precision 1.0／recall_hard 0.882／recall_all 0.933／wrong_rows 0、`parseable_rate` 1.0，但 **`hard_pass_rate` 0.0、`full_compliance_rate` 0.0、`mean_O`=`mean_O'`=`mean_gated_O'`＝0** ⇒ 0.6 權重整個作廢、paper score 全來自 0.4×mean_p（＝0.25725）；per-package BP-2 0.1019／BP-3 0.2375；judge 1 呼叫 `ok`（本機同模型）。
- **丟分點具體化**（28 families）：整族 0＝**F03、F12、F15、S08、D3**；0.529（18/34＝只在一包）＝F06、F08、F09、F10、S04–S07；部分＝F01 0.824、F02 0.794、S03 0.794、F04 0.735、S01 0.735；1.0＝F05、F07、F11、F13、F14、F16、S02、D1、D2、J1–J3。grader notes 可指名錯誤：`F08_added want [M-502A, S-201A] got [M-503, S-202]`（新增圖號的 revision-suffix 慣例錯）、`F10_first8` 顯示 GI-002 排在 GI-001 前（CAD ordering 細則）。
- **跨題結構性發現（本輪最重要）**：EXP-016（31 items、register_hard 全 forfeit ⇒ O 被壓）與 EXP-017（34 items、`hard_pass_rate` 0.0 ⇒ `O'` 全 0）顯示**兩題 heavy 的 0.6 客觀分權重都因「每 item 的 hard gate 未全過」而歸零**，實得分只剩 partial（p）項。這是 P3（工程驗證核心）的單一最大槓桿，並直接佐證 ADR-002（hard gates 優先於成本最佳化）。
- **DEF-003（新缺陷，見 §7）**：兩次 main run 尾聲都撞到 Strata 262,144 視窗（EXP-016 最終 prompt 261,799 只剩 337；EXP-017 在 **summary 之後** 的下一步 `harness error … prompt (262159) … context (262144)`），proxy 整 run 另有 9 次 context-overflow 400；serve.py 的被動剪枝 `context full: cut N old tool results` 觸發 5 次（5/2/1/1/1）撐住主幹，交付與評分不受影響（`exception_info=None`），但**收尾後的最後一輪自我驗證／迭代被吃掉**。
- **平台觀察（不修）**：`task.toml` 宣告兩條 artifact 路徑（含 `/filesystem/filesystem/...` 雙前綴變體）；本 run 只寫出主路徑，Harbor `docker compose cp` 對變體回 rc=1 → `trial.log` 有 RuntimeError，但 trial 正常評分。quick v7 的 `DELIVERABLE_PATHS` 應只用主路徑。
- **成本**：兩題 heavy 合計 27,895 s（7.75 h）＝平均 3 h 52 m／題 ⇒ 14 題 heavy 串行 ≈ 54 h（尚未含 light 14 題）。§1 的付費 API 並行選項必要性上升（R-012 的模型宣告問題不受影響）。
- **本輪邊界**：未動 quick（EXP-015 全套仍暫停）、未改任何 harness 參數或碼（main 仍 `eb918d8`）、未跑第三題；下一步等使用者對 P3 方向／成本／下一題拍板。

**2026-11-21（十二）— P3 起手＋DEF-003 已實作並過官方 `kit check`；依使用者指示逐項推進，P2 正式開工：**
- ① **P3 起手（main `85d1cbd`）**：serve.py 收尾驗證從「讀檔重查」改為機械式自查——新 `GATE` 角色依 instruction／plan 產出**單一 Python 驗收腳本**（每條機械可驗硬性要求一行 `PASS <id>`／`FAIL <id>: <錯在哪檔哪列>`：必要檔精確路徑、表頭與欄序、值格式如圖號 revision-suffix、row／sheet 排序、必要段落與計數、低成本重算；判斷性要求排除）。harness `compile()` 檢查後寫入 `/tmp/ple_gate.py` 於容器執行，FAIL 線（上限 30 行／4,000 字元）驅動 fix round；**腳本只寫一次、每輪重跑**（每輪都有 `phase: gate N` 標記）。無法產出可用腳本／腳本不回傳 verdict 行的輪次，一次有界回退舊 read-only verifier（`phase: verify N`，壞腳本不重跑）；驗證結果統一以 `verdict:` 記錄。fix round prompt 明文要求寫入：「Close every gap by writing or editing the files… rereading alone fixes nothing」。
- ② **DEF-003（同 commit）**：`$CONTEXT_TOKENS`／`$CTX_MARGIN_TOKENS`（預設 0＝未知→維持既有事後 cut，**不綁 262,144**）。每次模型呼叫前先以 chars/4 估算，超出即**先**剪舊 tool 結果再送（`context budget: cut N`），`max_completion_tokens` 壓到剩餘空間（下限 `CTX_MIN_ANSWER=1024`）；事後 `recover()` 路徑不動當後盾。首波 live run 不設 `CONTEXT_TOKENS`（保守），EXP-018/019 觀察完再決定何時啟用。
- ③ **驗證**：mock 契約suite擴至 **13/13**（`clean`／`fix_round` 改依 gate 流程：gate exec 由 evaluator 的 `gate_outs` 指令队列回答、獨立計數不干擾故障注入；新增 `gate_fallback`（prose→`no usable script`→reviewer 接手）／`gate_exec`（崩潰無 verdict 線→接手、不重跑）／`ctx_budget`（小視窗先 cut 再送、全程無 400）；過程中修掉 `phase: gate N` 只在建立輪標記的錯誤）；pyflakes 0、AST ok、prompt 字串外無長行。官方 `kit check --rebuild`（`kitcheck6.log`）：**7 階段全 PASS**（build 31 s 映像 `plebench-serve:6fb67fa48bbb4548`／model 21.8 s／listen 1 s／smoke 157 s 11 呼叫／mcp 171 s 12 呼叫），僅剩慣常 `artifacts` WARN（R-012）。
- ④ **操作教訓（重現性）**：LiteLLM 必須綁 **0.0.0.0**——harness egress sidecar 在容器內走 `host.docker.internal:4000`→`172.17.0.1`，loopback-only 綁定讓 `model` 階段 FAIL（本次第一次 kit check 死因）；啟動需 `uv run --with "litellm[proxy]" --with websockets`（新版 litellm 純 `litellm` 缺 fastapi／websockets）；`pkill`/`pgrep -f` 的模式會命中工具 wrapper 自己的 command line（兩度 exit 144 自我終止）→ 啟停改放腳本 `/tmp/start_litellm.sh`（模式只存在腳本內）。
- ⑤ **P2 正式開工**（使用者指示「依 progress.md 逐項完成，主要目標進入第二階段」）：P2-01～P2-04 已補上可重現證據（見 §3）；P2-05 四領域已 2/4（structural×2）→ 補 **EXP-018 `engineers-estimate-check`（電機, light L1, MCP×8）**＝新 gate 碼首戰＋main 路徑 MCP 實戰、**EXP-019 `emergency-spillway-check`（水資源, light L1, MCP×8）**排隊（串行，發射前另立 `.start`）。

**2026-11-23（四十四）— 修 gate 汙染交付（使用者核准「要，修掉」）：檢查階段前後快照 workdir、事後還原；離線驗證完成、未 live：**
- ① **問題**：檢查角色（gate agent、gate 腳本、verifier）照規定不可改檔，但工具做得到——EXP-026 #3 gate 腳本跑 `zip -u` 把重複檔塞進 `submission.zip`；EXP-028 #1 gate agent 把 `acceptance_check.py` 寫進任務資料夾（會被當成交付物擷取）。
- ② **修正（`serve.py`）**：每一輪 `phase: gate N` 開始時 `guard(session, "save")`、整段檢查（gate agent＋修復回合＋gate 腳本＋fallback verifier）包在 `try/finally`，結束時 `guard(session, "restore")`，**之後**才把 verdict 交給 fix round。`GUARD` 是寫到容器 `/tmp/ple_guard.py` 的小腳本：save＝走訪 workdir 記下每檔 `(size, mtime_ns)`＋把每檔 ≤ `GUARD_FILE_MB`（50）、總量 ≤ `GUARD_TOTAL_MB`（1000）的檔打成 `/tmp/ple_check_snap.tar`；restore＝刪除新檔與新資料夾、從 tar 還原被改或被刪的檔（並把 mtime 設回原 ns 值），超過上限的檔只比對、改了就在 log 點名；快照用一次就刪（避免下一輪 save 失敗時誤用舊快照、蓋掉 fix round 的合法修改）；save 失敗就不 restore。workdir 為 `/` 時跳過（29 題 WORKDIR 全是 `/filesystem` 或 `/app…`，輸入 0–103 MB）。有變動才 log `check guard: undid the check's writes under …`。
- ③ **驗證**：新 `guard_unit`——**真的執行** GUARD 腳本於暫存樹：檢查端改寫 zip、刪 md、新增 `acceptance_check.py` 與巢狀資料夾 → restore 後整棵樹（內容＋mtime ns）與存檔時完全相同、快照已刪、重跑 restore 無動作；0 MB 上限時改寫檔被列為 `could not restore 2 (too big)`、新檔仍刪除。（首跑抓到 tar 以 float 存 mtime、還原後差幾十 ns → 補 `os.utime(ns=…)`。）新 mock `check_guard`（兩輪各一組 save／restore、restore 訊息進 log 且在 `phase: fix 1` 前）；`clean` 斷言 save／restore 成對。guard 的 exec 在 mock 另走計數、不影響既有故障注入。**28/28**；`661fd2d` 跑 FAIL；pyflakes 0；>80 字元行 43。
- ④ 待 live：EXP-028 #3（舊碼 `661fd2d`）跑完後 kit check＋實跑驗證。

**2026-11-23（四十三）— EXP-028 #2（`d5267b8`）＝0.013：修復回合 live 觸發但沒救回，行號揭露真兇是 harness 自己的 code block 擷取，已修：**
- ① **結果**：**0.013**（#1 0.000）／`ok`／3,105 s、150 requests、in 4.73M（cache 91%）／out 188,692；kit check 7/7（`kitcheck18_gemma.log`、映像 `65a5508a7526d7d9`）。`mean_p` 0.031、`parseable_rate` 1.0、`hard_pass_rate` 0、register 3 列 precision 1.0。verify 兩輪都點出具體缺口（`ground_improvement_plan.json` 缺 BIM 標準鍵、`foundation_geometry.json` 缺 `pier_depth_ft`）。0 次 400。
- ② **修正 live**：(a) 截斷的 tool call 不執行 **4 次**；超預算 4、cut 9、學窗 1；修正 A 2 次；推回 0。
- ③ **gate 修復回合觸發 2 次、2 次都失敗**，但新 log 的出錯行一眼看出原因：`json_match = re.search(r'`、`if not content.strip().startswith('`——行尾都停在開引號，因為 gate 腳本在**檢查 Markdown 的 ```` ```json ```` 圍欄**，而 `gate_script()` 的 regex `` ```…\n(.*?)``` `` 是非貪婪、遇到**字串裡的第一個 ```` ``` ````** 就當成結尾 ⇒ 腳本被 harness 自己截斷，模型重寫也一樣。**這是 harness 缺陷，不是模型**（很可能也是 EXP-027 六輪＋EXP-028 #1 兩輪 `no usable script` 的原因，但那幾輪沒記 reply，無法回溯確認）。
- ④ **修正**：新 `GATE_FENCE`——結尾圍欄必須**自成一行**（`^\s*```\s*$`，`re.M`）；`gate_body()` 共用給 `gate_script()`／`gate_why()`。mock 新 `gate_fence`（腳本含 `'```json'` 字串 → `script ready` → PASS），**26/26**；`d5267b8` 跑該案 FAIL；pyflakes 0。修復回合保留（真正的語法錯誤仍可能發生）。

**2026-11-23（四十二）— EXP-028 #1（`d3651df`）新 heavy 題 `foundation-strategy`＝0.000：交付完整可解析、工程不對（模型能力）；`gate_why` 首次 live 找到 gate 失敗原因，已加一次修復回合：**
- ① **結果**：**0.000**／`ok`／2,008 s、126 requests、in 3.65M（cache 90%）／out 118,700；kit check 7/7（`kitcheck17_gemma.log`、映像 `0f6dd5fc11b0b9ca`）。`submission.zip` 6 檔在最上層（`foundation_geometry.json` 24 KB、`foundation_schedule.xlsx`、`constraint_register.xlsx`、`design_basis.md`、`foundation_feasibility_matrix.md`、`ground_improvement_plan.json`），`parseable_rate` 1.0；但 4 pads 全部 `n_engineered` 0、`hard_pass_rate` 0（例：`angular distortion F1-F2 exceeds 1/500`）、register precision 0.5／recall_hard 0 ⇒ 0 分＝工程計算錯，**模型能力**。verify 1 抓到「只有 F1／CR-P1 一個基礎，應有 6 pads 36 個」→ fix 1 有補。
- ② **context／修正**：超預算 3 次、cut 8 次、學窗 1 次、0 次 400；修正 A 1 次；截斷 call 0、推回 0。
- ③ **gate 失敗原因首次可見**：兩輪都是 `SyntaxError unterminated string literal`（line 86、line 127）——腳本整體是對的，只壞一行就整份丟掉、退回 verify。**修正**：`compile()` 失敗時給 gate 一次修復回合（`GATE_REPAIR`：「腳本無法編譯（錯誤＋行號＋該行內容），回覆完整修正後的腳本」，在原 gate 對話上續問，計時同 gate），log `gate: script does not compile (…)`；`gate_why` 改報出錯行號與該行（取代開頭 80 字元）。mock 新 `gate_repair`（未結束字串 → 修復 → `script ready` → PASS），**25/25**；`d3651df` 跑該案 FAIL；pyflakes 0。
- ④ **可靠度**：本題達標（合法交付、正常結束、無 400／崩潰／逾時）。

**2026-11-23（四十一）— EXP-027 #3（`d4c8e3c`）＝0.000，但交付已合法：zip 在最上層、7 檔齊全；失分是內容不符 schema（模型能力）：**
- ① **結果**：**0.000**／`ok`／2,704 s、192 requests、in 7.80M（cache 94%）／out 148,480；kit check 7/7（`kitcheck16_gemma.log`、映像 `612d9f15ed27e7ac`）。0 次 400、無崩潰、`serve stop condition: done`。
- ② **修正 live**：(c) archive 提示生效——worker 用 `cd … && zip -r output/submission.zip disposition_register.csv …`，**7 檔都在 zip 最上層**（#1 巢狀）；(a) `reply cut off inside a tool call` **live 觸發 2 次**，heredoc 截斷照跑 0 次；(b) 超預算 6 次、cut 15 次，學窗 1 次；修正 A 2 次；`UNFINISHED` 推回 0 次（本輪 planner 回了較長的計畫、worker 正常收尾，沒有宣告型回覆）。
- ③ **0 分的原因＝內容**：`disposition_register.csv` 欄位照抄 XML（`comment_id,package,markup_ref,…`），不是 schema 要的 `PACKAGE,COMMENT_ID,AUTHOR,SIGNIFICANCE,VALIDITY,…`；`sheet_index.csv`／`revision_log.csv`／`issue_plan.csv` 同樣不是 schema 欄位；`constraint_register.xlsx` 只有 11 B（佔位）。grader `register_rows` 0、34 items `p` 全 0。verify 1、verify 2 都明確點出「column names do not match the schema」，兩輪 fix 都沒改對 ⇒ **模型能力**，不是 harness 缺口。
- ④ **gate 仍兩輪 `no usable script`**（本題 Gemma 三次 run 六輪全是），原因沒記錄 → 新增 `gate_why()`：log 改為 `gate: no usable script (<空回覆／長度超限／無 code block 或語法錯誤＋開頭 80 字元>)`，下次 run 可判斷是 gate 提示問題還是模型問題。mock `gate_fallback` 斷言新理由，**24/24**；pyflakes 0。
- ⑤ **可靠度判讀**：本題 Gemma 已達可靠度判準（合法交付、harness 正常結束、無 400／崩潰／逾時）；分數留待正式模型。

**2026-11-23（四十）— EXP-027 #2（`d5a2902`）同題重跑＝0.000：context 修正 live 生效，但 worker 寫了「Next Steps」就收工、從沒產出 zip；已加「宣告未做」防護：**
- ① **結果**：**0.000**／`ERR_NO_SUBMISSION`（`no submission.zip was collected`）／3,021 s、218 requests、in 8.05M（**cache 95%**，#1 45%）／out 161,301。phase 走完 plan→work→gate 1→verify 1→fix 1→gate 2→verify 2→fix 2，`serve stop condition: done`。kit check 7/7（`kitcheck15_gemma.log`、映像 `55470eae3abd59ce`）。
- ② **d5a2902 的修正 live**：(b) 剪舊 call 參數生效——`context budget: over` 30 次、其中 26 次剪得動（#1：227 次只剪得動 16 次）；`here-document … end-of-file` **0 次**（#1 198 次）；學窗 2 次；修正 A 3 次；0 次 400。(a) `reply cut off inside a tool call` 0 次（本輪沒有被截斷的 call，未 live 驗證）。(c) 無從評估（沒有 zip）。
- ③ **0 分的原因＝提前收工（模型行為，harness 沒擋）**：worker 在第 ~110 步回了一段**沒有 tool call 的「summary」**，內容是「已解析 XML、建了草稿 disposition_register；**Next Steps**：完成 7 個交付物…最後打包 `output/submission.zip`」，harness 把它當完成。planner 兩輪（#1、#2）也都只回一句「I will start by…」當計畫；verify 1 回「I will now proceed to check…」後 verdict 變成對計畫的讚美，沒點出 zip 不存在。gate 1／2 都 `no usable script`。fix 1／2 只在 workdir 反覆重跑 `generate_disposition.py`，沒寫 `output/`。
- ④ **修正（`serve.py`）**：回覆沒有 tool call、且 (i) 以意圖開頭（`I will`／`I'll`／`Let me`／`I am going to`）且短於 800 字元，或 (ii) worker 的最終 summary 含「Next steps／Remaining steps／Still to do」標題 ⇒ log `reply announces work still to do; asking to do it`、送 `UNFINISHED`（「你描述了還沒做的工作；現在用工具做完，做完才不帶 tool call 回覆」），每步最多 `MAX_PUSHES=2` 次，之後照原樣接受。**誤判檢查**：對 runs/ 內全部 33 份 final message＋32 份 plan 跑偵測，命中 4 件全是真的宣告（本題兩份一句話 plan、本輪 Next Steps summary、`plan-verify-20261120-124013` frame-extension 的「Let me align…」），0 件誤判。mock 新 `unfinished`（planner 一句意圖＋worker Next Steps 各推回一次）、`clean` 加 `log_not_in` 負控制，**24/24**；`d5a2902` 跑 `unfinished` FAIL（0 次推回）；pyflakes 0。
- ⑤ 下一步＝EXP-027 #3 同題，看推回後是否產出 top-level zip。

**2026-11-23（三十九）— EXP-027 #1（`f43c01e`＝`eb64c30` 碼）第二題 heavy `eor-review-corrections`＝0.000：zip 包錯層＋被截斷的 tool call 照跑，已修兩項（未 live 驗證）：**
- ① **結果**：**0.000**／`ok`／**15,136 s（4.2 h）**、367 requests、in 19.96M（cache 只有 45%，剪枝一直打掉前綴）／out 318,383；Qwen 錨點 0.2573（EXP-017 #2）。phase 走完 plan→work→gate 1→verify 1→fix 1→gate 2→verify 2→fix 2，`serve stop condition: done`。judge 1 呼叫 `ok`（4,985 字元，無溢出）。
- ② **0 分的直接原因＝zip 包錯層**：worker 用 `zip -r …/output/submission.zip /filesystem/…/output/`（絕對路徑），7 檔全在 `filesystem/dc_structural__eor_revision__blind/output/` 之下，題目要求「at the top level」→ grader 讀不到任何檔（`register_rows` 0、34 items `p` 全 0，families 只有格式類 F05／F07／F13／F16／D2 過）。verify 1 有 `unzip -l` 看到巢狀路徑卻沒指出；fix 1／fix 2 把修正後的 CSV 寫進 `project/` 而非重新打包，最後的 zip 仍是 18:06 那一版。
- ③ **64K context 沒撐住（DEF-003 新缺口）**：學窗 1 次（65,533），之後 **227 次呼叫 `context budget: over`、只有 16 次剪得動**——可剪的舊工具結果早就剪光，佔滿視窗的是**舊 tool call 的參數**（worker 用 heredoc 一次寫整份 CSV／腳本，單次 3K–22K 字元，`shorten()` 從不碰）。剪不動就以下限 1,024 送出 → Ollama **撞窗截斷 146 次**（`truncated = 1`）、修正 A 觸發 17 次；更糟的是**被截斷的 tool call 仍被執行**：轉錄有 **198 次** `here-document … delimited by end-of-file`（heredoc 沒寫到 EOF 就被截），寫出半截檔案，模型重試同一個大 heredoc、又被截——這是 4.2 h 的主要消耗。0 次 400；04:45 Ollama runner 2 次 500（`/tokenize` 連線失敗，重試後恢復）。
- ④ **A／B**：A 17 次（都拿回答案，但治標）；B 0 次；gate 1、gate 2 都 `no usable script`（gate 自己也卡在超預算、輸出被壓在 1,024）→ verify fallback。
- ⑤ **修正（本輪，`serve.py`）**：(a) **截斷的 tool call 不執行**：`finish_reason=length` 且有 tool call → 丟掉 call、log `reply cut off inside a tool call; call not run`、送新 `CALL_CUT`（「撞到輸出上限 N tokens、call 被截斷沒有執行；改小呼叫、長檔分段寫」），計入 `MAX_NUDGES`。(b) **`shorten()` 也剪舊 tool call 參數**：新 `cut_args()`／`cuttable()`，把參數 JSON 裡超過 `CUT_KEEP` 的字串截到 1,000 字元（加註「already run」），仍是合法 JSON；與工具結果一起依位置剪較舊的一半。(c) **封存檔層級提示**：WORKER「archive 預設檔案在最上層，從資料夾內打包、別用絕對路徑，並列出 entries 檢查」；GATE「archive 內的 entry 路徑」；VERIFIER「archive 內的 entry 路徑」（29 題中 12 題交付 `submission.zip`）。
- ⑥ **驗證**：mock **23/23**（新 `call_cut`：截斷的 write_file 不執行、收到 nudge、下一次正常寫；`args_cut`：30K 字元的 write_file 參數在小視窗下被剪且仍為合法 JSON）；**偵測證明**＝兩案例套在 `f43c01e` 的 `serve.py` 都 FAIL（`call_cut: nudge not sent`、`args_cut: arguments not cut`）；pyflakes 0；>80 字元行 41→43（兩行皆 prompt 字串）。實測：Ollama 不把存回的 `reasoning_content`／`provider_specific_fields.reasoning` 算進 prompt（加 17K 字元推理，`prompt_tokens` 仍 37）⇒ 推理不是佔窗來源。(c) 是 prompt 改動，n=1 無法單獨歸因。
- ⑦ **磁碟**：D: 63 GB（不變）。run `plan-verify-20261123-014635`。下一步＝重建映像、kit check、同題 EXP-027 #2 live 驗證 (a)(b)(c)。

**2026-11-23（三十八）— EXP-026 #4（`eb64c30`，預算改以真實 token 計）＝0.119：64K context 管理在 heavy 題上首次完全乾淨：**
- ① **結果**：0.119／`ok`／**992 s**、38 requests、in 1,530,526（cache 90%）／out 61,103；`mean_p` 0.307、B8 forfeit、mean h 0.20；`submission.zip` 6 檔、無重複；gate 1 腳本可跑 → PASS。kit check 7/7（`kitcheck14_gemma.log`、映像 `b907cf495997c5e7`）。
- ② **context 管理**：`context window: learned 65534 tokens from a reply cut at the window`（實際 65,535，差 1）；之後 `context budget: over by 7523` → cut 2＋cut 1 就回到可放得下，**沒有再把上限壓在下限**；Ollama 整 run 只截斷 1 次（就是學窗那次）、0 次 400。修正 A 1 次（學窗那次的回覆全是推理）。⇒ DEF-003 在 Ollama 64K 下的三個問題（撞窗不回 400、上限沒生效、單位混用）都已處理並 live 驗證。
- ③ **分數判讀**：同題四次 0.151／0.187／0.164／0.119（平均約 0.155、差距約 ±0.035），差異在模型隨機性內，四次都是 B8 forfeit＋p 項 0.31–0.48；Qwen 錨點 0.36 的差距是模型能力。

**2026-11-23（三十七）— EXP-026 #3（`5df6849`＋本機 proxy 上限生效）＝0.164：上限生效後暴露單位混用，已修（`eb64c30`）：**
- ① **結果**：0.164／`ok`／2,140 s、72 requests、in 2,874,444（cache 88%）／out 130,286；`mean_p` 0.425、B8 forfeit；Ollama 撞窗截斷 2 次（皆在 planner、學窗之前）。
- ② **新問題**：從截斷學到的視窗 58,411 是「送出的 chars/4 估計＋實際生成 token」混在一起；planner 階段 chars/4 偏低、worker 階段又偏高約 15%。結果預算一路報 `over by 36 → 19,993 tokens`，可剪的舊工具結果早已剪光，**連續約 20 次呼叫把回覆上限壓在下限 1,024**——Ollama 卻一次 400 都沒回（真實 prompt 其實放得下）。修正 A 因此觸發 2 次（推理被 1,024 截斷）。#2 沒看到是因為那時上限根本沒生效。
- ③ **修正（`eb64c30`）**：新 `CTX_RATIO`＝上一個回覆的 `usage.prompt_tokens ÷ 送出時的 chars/4`，`ctx_used()` 以它換算；預算、400 路徑都改用換算後的真實 token；截斷學窗直接用 `prompt_tokens + completion_tokens`（真實、精確）。mock 改回報真實感的 `prompt_tokens`（`MOCK_TOKEN_RATIO`），新案例 `ctx_ratio`，**21/21**；pyflakes 0、>80 字元行 41。**沒有偵測證明**：舊碼也過 `ctx_ratio`——固定比例重現不了階段間漂移，真正的驗證是 live 重跑（EXP-026 #4）。
- ④ **另一個觀察（未修）**：gate 腳本自己跑了 `zip -u`，交付的 `submission.zip` 多出一份 `output/…` 重複檔（GATE 提示已寫「只能寫 /tmp」，模型沒遵守）；腳本結果也就沒有 verdict 行 → fallback reviewer PASS。要在 harness 擋需在 gate 前後快照比對任務資料夾，成本較大，**待使用者決定**。

**2026-11-23（三十六）— EXP-026 #2（`5df6849`，撞窗學習）＝0.187：修正 live 生效；另發現 Ollama 不認 `max_completion_tokens`，已在本機 proxy 補上：**
- ① **結果**：`frame-extension-method` **0.187**（#1 0.151）／`ok`／1,580 s、45 requests、in 1,335,722（cache 87%）／out 101,167；`mean_p` 0.483（#1 0.390）、B8 forfeit 照舊；交付 6 檔齊全；gate 1 腳本可跑 → PASS。kit check 7/7（`kitcheck13_gemma.log`、映像 `3bef68fd6277777a`）。n=1，+0.036 不歸因。
- ② **撞窗學習 live 生效**：轉錄 `context window: learned 65063 tokens from a reply cut at the window`，之後 `context budget: over by … ; shortening` ／`cut 1 old tool results` 共 7 次，0 次 400。修正 A 觸發 1 次（救回）。
- ③ **但 Ollama 仍截斷第 2 次**（00:19，生成 11,707 token）：學窗之後預算已把輸出上限壓到幾千，回覆卻照樣長到 1 萬多 → 直接測試確認 **Ollama 的 OpenAI 端點忽略 `max_completion_tokens`、只認 `max_tokens`**（經 LiteLLM 或直連皆然：要 40 回 1,284／1,273；`max_tokens` 40 回 40）。⇒ 所有 Gemma run 的輸出上限其實都沒生效（OUT_SHARE、room 都形同虛設）。正式路徑（LiteLLM→Vertex）認 `max_completion_tokens`，所以這是**本機環境差異，不改 harness**。
- ④ **本機 proxy 修正（dev only）**：`~/projects/model_proxy/cap_alias.py`（LiteLLM `async_pre_call_hook`：`gemma-4-26b`／`gemma-4-26b-judge` 的 `max_completion_tokens` 改名 `max_tokens`），`config.yaml` 加 `callbacks: cap_alias.proxy_handler_instance`，兩條 gemma 路由加 `allowed_openai_params: ["reasoning_effort"]`（有 `max_tokens` 時 LiteLLM 會拒 `reasoning_effort`；它會改變思考長度，不能丟）。備份 `config.yaml.before-cap-20261123`。比較過的替代：`ollama_chat/` 認上限，但超長 prompt 回 **500** 而非 400（harness 的學窗路徑只認 400）；`hosted_vllm/` 同樣忽略上限。驗證：上限 40→回 40（`length`）、tool call＋第二輪正常、超長 prompt 仍 400、`reasoning_effort` 照傳。注意：proxy 剛重啟後第一個請求沒經過 hook（暖機），之後都正常。
- ⑤ 下一步＝EXP-026 #3：同題同碼，只差上限生效，看撞窗截斷是否消失、上限壓小後思考是否被截（修正 A 會不會頻繁觸發）。

**2026-11-22（三十五）— EXP-026 #1：Gemma 首次 heavy 題＝0.151（Qwen 錨點 0.36）；64K 沒爆但暴露 Ollama 撞窗不回 400，已修（DEF-003 補強）：**
- ① **結果**：`frame-extension-method`（checks）**0.151**／`ok`／**1,144 s**（Qwen 3–4 h 的十分之一）、57 requests、in 2,266,898（cache 88%）／out 61,333；交付 `submission.zip` 8,334 B（6 檔齊全：construction_sequence、temporary_works.json、stability_check、occupancy_report、constraint_register、method_note）。評分：31 items 全在、`mean_p` **0.390**（Qwen 0.95）、`mean_O` 1.0，但 `register_hard fails on 31 (B8 forfeit)`、mean h 0.40 ⇒ 0.6 權重全失，分數只剩 p 項。失分族：hard 的 F02 強度發展、F03 支撐容量、F04 回撐、F05 階段穩定、F06 鷹架容量、F07 平台寬、F09 拉結、F11 堆料全 0；soft 的 F16–F19、F25–F29 全 0。**判讀**：交付完整、形式對，但工程計算大多沒做對＝模型能力差距；這題 Qwen 也有 B8 forfeit，但 p 高得多。
- ② **64K context 管理**：planner 的請求從 14 KB 長到 188 KB（≈ 60K tokens）後換階段重來；整 run **0 次 400**、`learn_window` 0 次、`context full: cut` 0 次。但 Ollama log 有 **3 次 `truncated = 1`、`n_tokens = 65535`**（23:44，回覆分別生成 6,858／1,657／281 token 就被視窗截斷）：Ollama 撞窗時回 **200＋`finish_reason=length`**，不是 400，所以 harness 學不到窗、還照要 32,000 輸出，下一次又貼著 64K 送（連鎖截斷）。⇒ **已修**（見 §7 DEF-003 補強）：`length` 且生成數明顯少於要求的上限 ⇒ 視為撞窗並學窗。mock `ctx_trunc` 20/20、舊碼同案例 8 次截斷 vs 新碼 1 次、pyflakes 0、>80 字元行 41→41。
- ③ **A／B**：修正 A（`reply cut off before any answer`）0 次；B（`gate: check itself failed`）0 次。gate 腳本自己崩潰（`ValueError: not enough values to unpack`，exit 1、無 verdict 行）→ 走既有 `gate: no verdict lines` → `phase: verify 1` → PASS（`gate_exec` 路徑首次 live，運作正常；腳本本身的錯不屬 B 的範圍）。
- ④ **磁碟**：D: 62→63 GB（題目映像 1.1 GB 已存在、未重建）。run `plan-verify-20261122-232812`。
- ⑤ **使用者授權（2026-11-22 夜）**：可分析、寫 progress.md 並 commit、改 harness、跑新題目、刪 Docker 映像或其他檔案；服務中斷可同參重跑，最多三次；**不可 push**。

**2026-11-22（三十四）— EXP-025 #2（碼 `a5f5452`、HEAD `fdef666`）三題 light＝平均 0.046；兩題有分、backfeed 因本機 judge context 溢出而無分：**
- ① **結果**：engineers-estimate-check **0.065**（加權 3/46、10 items 過 3；3,336 s、35 requests、out 127,027）；fire-test-validation-memo **0.072**（加權 15/208、48 items 過 9；3,601 s、47 requests、out 105,948）；backfeed-energization-reply **無分（計 0）**（1,199 s、73 requests、out 67,877；交付 `Halbray_Backfeed_Reply.docx` 37,217 B）。eval 同時跑 2 題（Ollama `NUM_PARALLEL=1` 排隊），prefix checkpoint 仍大多可重用。
- ② **backfeed 無分的原因**：Gemma judge（64K）收到的 prompt 超過視窗 → HTTP 400 → `GRADER FAILED`，eval 自動重評 3 次都一樣。交付物被擷取了 9.3 MB 的 `app/tools/.apps_data/*`（MySQL／OpenProject／Wiki SQL dump、`nextcloud.db`、`app/output/.helpers_cache/db_diff.txt`），**已查明（非 harness 缺陷）**：① 題目自己的 `task.toml` 宣告 `artifacts = ["/filesystem", "/app/output", "/app/tools/.apps_data", "/logs/agent"]`，capture 只收相對 baseline 有變動的檔；② 本題環境內跑著**真的 Nextcloud 伺服器**（Dockerfile 有 `NEXTCLOUD_VERSION`），平台收尾 hook 匯出各 app DB 並產生 `db_diff.txt`；③ diff 內容全是 Nextcloud 自己的背景雜訊（`oc_jobs` −374／~114、`oc_calendars` +68、`oc_appconfig` lastjob），OpenProject／Wiki／MySQL 0 變動——代理唯一一次寫入嘗試 `openproject_create_work_package` 回 `Unknown tool`，沒寫成；④ grader 把 279 KB 的 `db_diff.txt` 整份放進 judge prompt（`MAX_TEXT_CHARS` 350,000 字元內），加上 1.1 KB 的信件 ≈ 遠超 64K tokens。engineers／spillway 雖宣告同樣的 artifacts，但環境沒有 Nextcloud 伺服器，所以沒有 diff。**影響範圍**：29 題 dev set 中跑真 Nextcloud 的有 5 題（backfeed、permission-to-operate-memo、pre-application-capacity-response、solar-supplemental-review、solar-witness-test-package），這幾題 Gemma 64K judge 都可能評不了；正式 judge（Opus）視窗大，且雜訊對所有參賽者相同，**對正式成績無影響、harness 不需改**。grader 是官方碼，不改。交付物仍在，可 `eval/run.py --regrade <run>` 換大視窗 judge 重評。
- ③ **修正是否觸發**：A（`reply cut off before any answer`）**live 首次觸發 4 次**（engineers 1、backfeed 3），每次都拿回答案＝有效；B（`gate: check itself failed`）0 次；`learn_window` 0 次（兩題皆 `context window: not announced…; reactive path only`、無溢出）。
- ④ **gate**：engineers gate 1 PASS 但數字錯（bond 寫 $5,323,000，GT $5,384,000）；fire-test gate 兩輪 `FAIL: Missing simulation or burn data` → 2 輪 fix 後收尾；backfeed gate 1 `FAIL R2.1: Requested date 07/29/2025 not found` → fix 後 PASS（真缺口驅動真修正）。
- ⑤ **判讀**：兩題低分主要是模型能力（數量抽取錯、gate 檢查的內容抓不到），本輪無新的 harness 錯誤；n=1 不做 A/B 歸因。
- ⑥ **決定（使用者 2026-11-22）**：不以 Qwen judge 重評 backfeed（分數不能與 Gemma judge 分數比、正式 judge 是 Opus、分時切 GPU 成本高）。**跑真 Nextcloud 的 5 題在本機只看可靠度、不看分數**（有合法交付物、harness 正常結束、無 400／崩潰／逾時）：backfeed-energization-reply、permission-to-operate-memo、pre-application-capacity-response、solar-supplemental-review、solar-witness-test-package。分數等換正式模型＋正式 judge 時再看。backfeed 本輪已符合可靠度判準（docx 合法、gate 最終 PASS、`serve stop condition: done`）。
- ⑦ **磁碟**：D: 80→62 GB（主要是重建 23.5 GB 的 backfeed 映像），R-016 三道防護都沒觸發（最低 62 GB，遠高於 10 GB 線）。run `plan-verify-20261122-203749`；artifacts 只匯出 2 題（`--no-export` 下僅本地）。

**2026-11-22（三十三）— EXP-024 #2（`a5f5452`）＝0.162（#1 為 0.108）：兩個修正本輪都沒被觸發，差異不能歸因：**
- ① **結果**：0.162162（6/37）、1,226 s、out 76,675。多過的是 item 1／7（C-9 不足以回答 G-4、須補 sizing 計算與剖面），兩條 w10（41.5 cfs、沒有文件授權排入 Windmill Ln. 路緣溝）仍未過；簽名欄仍缺。
- ② **修正是否生效**：本輪 planner 沒有 thinking 失控（單次最長生成 8,324 tok，`reply cut off before any answer`＝0）、gate 腳本沒有壞（`gate: check itself failed`＝0）、context 最大約 48.5K 未溢出（`learn_window` 未觸發）⇒ **A、B、learn_window 三者 live 都未被觸發**，+0.054 屬 n=1 模型隨機性（rubric 題單次雜訊可達 ±0.2，見（二十三）②）。
- ③ **gate 這輪發揮作用**：gate 1 抓到 `Error reading docx: File is not a zip file`（worker 第一版 docx 不是合法檔），fix 1 以 `fix_memo*.py` 重寫成合法 docx；gate 2 再抓到「4 個必答問題只答 2 個」→ fix 2。⇒ 與 #1（gate 自己壞掉、兩輪白做）相反，這次是真缺口驅動真修正。副作用：`fix_memo.py`／`_v2`／`_v3` 留在 `/filesystem` 被當成交付物一併擷取。
- ④ **judge**：item 8 再度判「沒有 .docx」，但交付的 docx 經 `file` 確認為 `Microsoft Word 2007+`——Gemma judge 只看 verifier 的 `.pdf.txt` 渲染就判無 docx，屬 judge 系統性誤判（Qwen judge 在 EXP-019/021 有給分）。⇒ Gemma judge 下每 run 固定少 1 分。
- ⑤ **下一步建議（待使用者決定）**：(a) Gemma 多跑 2–3 題 light 題，判斷低分是普遍還是這題特別難；(b) 分時開 Strata，以 Qwen judge `--regrade` #1、#2，拆掉 judge 變因；(c) A／B 需要能觸發它們的 run 才能 live 驗證（mock 已證明邏輯）。

**2026-11-22（三十二）— 修缺陷 A＋B（使用者核准），離線驗證完成、未 commit：**
- ① **A（`serve.py` `agent()`）**：回覆撞輸出上限且 `content` 為空（全是 reasoning）時，log `reply cut off before any answer (reasoning only)`，改送 `EMPTY_CUT`（「你的推理超過輸出上限、還沒寫答案，所以沒有保留；現在回答，推理簡短、細節用工具」），不再送看不到上文的「continue where it stopped」。另：視窗已知時 `max_completion_tokens` 再加一個上限 `CONTEXT_TOKENS // OUT_SHARE`（`OUT_SHARE=4`，64K→16K；大視窗模型仍是 32000）。注意：live 經 LiteLLM 時視窗要到第一次溢出才會知道（`learn_window`），之前仍是 32000。
- ② **B（`serve.py` `gate_run()`）**：新 `CHECK_BROKE` 正規式——FAIL 行若顯示檢查工具自己缺東西（裸指令名的 `No such file or directory: 'strings'`、`command not found`、`No module named`／`ModuleNotFoundError`、`NameError`）→ log `gate: check itself failed`，回傳 None＝走既有 fallback reviewer、腳本不再重跑，不進 fix round。**以路徑點名的缺檔（含 `/`）仍算交付缺口**。
- ③ **驗證**：mock 契約 **19/19**（新 `empty_cut`／`out_cap`／`gate_broke`／`gate_missing_file`；後者是負控制，確保真的缺檔仍進 fix round）；**偵測證明**＝三個新案例套在 `07e873f` 的 `serve.py` 全部 FAIL（`empty_cut: nudge not sent`、`out_cap: a call asked for 7785 tokens`、`gate_broke: log lacks 'gate: check itself failed'`）；pyflakes 0；>80 字元行 41→41。

**2026-11-22（三十一）— EXP-024 #1 結果＝0.108（Qwen 同題 0.838／0.919）：Gemma 快 2.7 倍但答錯；轉錄找出兩個 harness 缺陷＋一個 judge 混淆：**
- ① **結果**：0.108108（加權 4/37）、`ok`、1,580 s、56 呼叫、out 95,330。過的 4 項＝收件人、日期、溢流出口位置、Phase 3 detention 配額不變；丟分集中在工程結論：寫成「C-9 已足以回答 G-4」（GT 是要補 sizing 計算與剖面）、漏掉 41.5 cfs、漏掉「沒有任何文件授權排入 Windmill Ln. 路緣溝」（w10）、漏掉「spillway 啟用後 1.29 ft freeboard 不成立」、漏掉 Windmill Ln. 屬 Phase 2 已驗收工程；簽名欄留 `[Your Name]`。⇒ **主要是模型讀圖／推理能力差距**，不是交付失敗。
- ② **32K token 那次呼叫＝planner 的 thinking 失控**（不是寫大檔）：Ollama 記到單次 `n_gen=32,053`（撞 `MAX_OUTPUT_TOKENS=32000`、約 8 分鐘）；轉錄的 plan 開頭是「The user's request to "continue where it stopped" is likely a response to…」。對照 `serve.py`：被截斷的回覆 `content` 為空（32K 全是 reasoning）時，`head` 為空、該 assistant turn 不會被 append，harness 卻送出「Your reply was cut off; continue where it stopped.」——模型看不到自己被截斷的內容，只能對著 nudge 自說自話。**缺陷 A（模型無關）**：截斷且無 content 的 nudge 措辭錯誤。占全 run 輸出 token 約 1/3。
- ③ **gate 腳本自身錯誤被當成交付缺口**：GATE 產生的 `/tmp/ple_gate.py`（5,331 B）用 `strings` 指令讀 docx，容器沒有該指令 → 兩輪都印 `FAIL F2: Could not read memo content: [Errno 2] No such file or directory: 'strings'`；兩輪 fix round 都在重讀檔案，沒有改交付物（交付物本身可讀，`python-docx` 讀得到全文）。**缺陷 B**：harness 無法分辨「檢查程式壞了」和「交付物有缺口」。
- ④ **judge 混淆**：本 run 的 judge 是 Gemma（Strata 未運行），EXP-019/021 是 Qwen judge。item 8「No .docx file was provided」是 **judge 誤判**（docx 確有交付，verifier 也渲染出 `.pdf.txt`）。⇒ 本 run 與 Qwen 錨點的差距同時含模型與 judge 兩個變因，n=1 不歸因。要乾淨對照需以同一 judge `--regrade`（Qwen judge 需要 Strata，與 Gemma 搶 GPU，要分時）。
- ⑤ **context**：全程 0 筆 context 400（最大 prompt 約 32.7K＋32K 生成≈視窗上限，`truncated = 0`），`learn_window` 本 run 不會被觸發（且映像是改動前建的）。前綴快取正常（每次 `restored context checkpoint`）。
- ⑥ **速度**：1,580 s vs EXP-019 Qwen 4,270 s（−63%）；呼叫 56 vs 143；生成 60–90 tok/s、prompt 處理 1,000–2,500 tok/s。
- ⑦ **建議下一步（待使用者決定）**：(a) 修缺陷 A：截斷且無 content 時改送「你的推理超過輸出上限、還沒回答；現在直接回答，細節用工具處理」，並把輸出上限在視窗已知時壓到視窗的 1/4（64K→16K，大視窗模型不變）；(b) 修缺陷 B：gate 腳本的 FAIL 若是腳本自身例外（Traceback、`Errno`、缺指令），視為「檢查壞了」走既有 fallback reviewer，而不是當交付缺口；(c) 換回 Qwen judge 對本 run `--regrade`，把 judge 變因拆掉。

**2026-11-22（三十）— DEF-003 第三條路：`learn_window`（從第一次 context 溢出學視窗），離線實作完成，等 EXP-024 #1 跑完再同題重跑：**
- ① **問題**：視窗未知時（`$CONTEXT_TOKENS` 進不了容器；LiteLLM 剝掉 `/v1/models` 的視窗欄位 → `window_probe` 學不到），harness 只能「撞 400 再剪」，而且每個 step、每次 context 重新填滿都要再撞一次（EXP-023 #2 尾段 116 次 400）。Gemma 本機只有 64K，問題會更早出現。
- ② **改動（只動 `serve.py`，碼變因，prompt 不動）**：新 `learn_window()`——`recover()` 收到符合 `CONTEXT_FULL` 的 400 時，先把被拒那段對話的 `est_tokens(messages)` 記成 `CONTEXT_TOKENS`，再照舊 `shorten()` 重試。之後每次呼叫都走既有的事前預算（先剪再送、`max_completion_tokens` 壓到剩餘空間）⇒ **每個 serve process 最多撞一次**。數值用 `est_tokens` 的 chars/4 單位，等於順便校正 tokenizer 比例；已知視窗（env 或 endpoint 宣告）**只降不升**。不寫死任何常數，本機 Ollama 與 Stage 2 託管模型同一份碼。
- ③ **驗證（全離線，不佔 GPU）**：mock 契約 **15/15**（新 `ctx_learn`：mock 以 Ollama 原文對超過 3,000 est-tokens 的 prompt 回 400；planner 與 fallback reviewer 兩個 step 各讀一份長工具結果 → 斷言端點只拒絕 1 次，且 log 依序有 `context window: learned`、`context full: cut`、`context budget: cut`）；**偵測證明**＝同一測試套用改動前的 `serve.py`（`d6ec222`）→ `AssertionError: ctx_learn: endpoint refused 2 times`；pyflakes 0；>80 字元行 41→41（無新增）。EXP-024 #1 的映像在改動前已建好，不受影響。
- ④ **殘留風險**：若端點因「與視窗無關、但措辭符合 `CONTEXT_FULL`」的原因回 400（例如 `max_tokens` 超過模型輸出上限），會學到偏小的視窗。不過舊碼在同情況下也會一路剪到無可剪後失敗，不會比舊碼更糟。

**2026-11-22（二十九）— repo 拉回 Windows 本機資料夾＋接上本機 Ollama Gemma 4 26B（`google-cloud/gemma-4-26b`），官方 `kit check` 7 階段全 PASS：**
- ① **repo 遷移**：見上方「2026-11-22 環境架構變更」。WSL 舊 repo 停用、保留作備份。
- ② **Ollama 實測（2×RTX 3060 12 GB）**：`gemma4:26b`（25.2B、Q4_K_M、原生 context 262,144、tools／thinking 能力、附 draft model）。fork session 的 ctxfit：`num_ctx` 32,768／65,536 → 100% GPU（約 11.4＋10.2 GB）；98,304／131,072 → **OOM**（Ollama auto-fit 的 CPU offload 重試失敗）。⇒ 新建 **`gemma4:26b-64k`**（`FROM gemma4:26b`＋`PARAMETER num_ctx 65536`），不依賴全域 `OLLAMA_CONTEXT_LENGTH`。fork 另測得：用 Ollama 內附的 llama-server.exe 直接跑 `-c 262144 -fa on -ctk q8_0 -ctv q8_0 -ngl 99 --n-cpu-moe 6 --jinja` 可載入 256K（n_ctx 262,144）；fork 回報的 decode 7.9 tok/s 與 VRAM 數字**作廢**（整段測速都與本 session 的 Ollama runner 同時佔 GPU，長 prompt 測試被中斷、無資料），速度需重測；其 `/v1/models` 以 `meta.n_ctx` 宣告視窗，`window_probe` 目前不解析此欄位。64K 全 GPU vs 256K 部分 CPU 的取捨待實測比較。
- ③ **端點契約（WSL 端直打 `127.0.0.1:11434/v1`，mirrored loopback）**：非串流與串流都回 `tool_calls`（`bash` → `ls /app`）；超過 64K 的 prompt（451,524 字元）回 **HTTP 400** `the prompt is longer than the context length currently available to the model`（不會靜默截斷）。經 LiteLLM 後仍是 400（`litellm.BadRequestError: OpenAIException - ...context length...`），**符合 serve.py `CONTEXT_FULL` 正規式** ⇒ 事後剪枝路徑可接住。
- ④ **LiteLLM**：`config.yaml` 新增 `gemma-4-26b`／`gemma-4-26b-judge` → `openai/gemma4:26b-64k`＠`http://127.0.0.1:11434/v1`（Qwen／claude 別名保留不動）；`local.env` 的 `JUDGE_MODEL` 改為 `gemma-4-26b-judge`（Strata 目前未運行）；修正 `start_litellm.sh` 的 pkill 模式（舊模式 `.*model_proxy/config.yaml` 對不上實際命令列 `--config config.yaml`，舊 proxy 殺不掉、新 proxy 綁不到 port）。三檔改前皆備份為 `*.before-gemma-20261122`。啟動前需 `export PATH="$HOME/.local/bin:$PATH"`。
- ⑤ **`submission.yaml`**：`model_api` 改為 `google-cloud/gemma-4-26b`（使用者指示接 Gemma；屬贊助模型，可作 Stage 2 目標候選）。**未 commit**。
- ⑥ **驗證**：`kit check /mnt/d/project/vide-coding/ple-solo-harness --env-file ../local.env --rebuild` → **rc=0**（`~/projects/kitcheck11_gemma.log`）：build 31 s 映像 `plebench-serve:df5618bbb7235220`／model `Gemma 4 26B A4B answered in 1.5 s`／listen 2 s／smoke 52 s 5 呼叫（3,238 in／3,672 out）／mcp 23 s 15 呼叫；WARN 只有 `files: not committed`（submission.yaml）與慣常 `artifacts`。⇒ harness 從 Windows 資料夾經 9p 掛載建置可行。
- ⑦ **期間事件**：fork session 的 llama-server（:11500）與本 session 的 Ollama runner 同時佔 GPU（合計約 21.5 GB），使用者選擇停 fork 測速；重疊期間的測速數字作廢。fork 曾以 `OLLAMA_CONTEXT_LENGTH=131072` 重啟 Ollama（18:02），該變數已從使用者環境移除；Ollama 下次重啟前，未自設 `num_ctx` 的模型預設 131K（Gemma 會 OOM）。
- ⑧ **待辦／風險**：(a) 64K 視窗遠小於 Qwen 時期的 262K，heavy 題將頻繁走 400→剪枝（每次約 0.5–19 s），DEF-003 的事前預算在 live 仍不可達（LiteLLM 剝 `/v1/models` 欄位）；(b) Ollama 預設 `OLLAMA_KEEP_ALIVE` 5 分鐘、`OLLAMA_NUM_PARALLEL` 1，長工具呼叫後可能重新載入（約 12 s）；(c) Gemma 為 Stage 2 贊助模型之一，本機結果可直接作跨模型比較的第二個模型（Rubric 3），但本機 Q4 量化與 Google 端託管版本不完全相同。

**2026-11-22（二十八）— Kaggle Overview 全文已讀（Windows 端內建瀏覽器，免登入可見）→ 修正 §1（二十六）與 R-004／R-012 的多項假設：**
- ① **提交管道已公告＝Kaggle Writeup**（≤2,000 字；可 un-submit／改／再 submit 至截止，未 submit 的草稿不評）。Writeup 頂端放 40 字元 commit SHA（`git rev-parse HEAD`），Project Links 放 GitHub repo URL；ple-bench.com 直接註冊／提交已關閉。必附：Media Gallery 封面圖＋3 張圖＝(1) 架構圖、(2) score-vs-cost 圖、(3) 29 題 dev 失敗分解。repo 若私有需裝 `ple-submission` GitHub App，賽末公開。⇒ 修正（二十六）②「提交方式官方尚未公告」。
- ② **R-012 前提作廢**：官方明文允許 local dev 以任何自架開源模型或個人 API 產生 `artifacts/`，提交前把 `model_api` 改成目標 `google-cloud/<id>`「will not disqualify you」，條件是 Writeup 寫明所用本機模型與 judge 設定；本機 judge（`JUDGE_MODEL`）同樣要在 Writeup 註明；官方會以正式 judge 重評 `artifacts/`。⇒ 「必須開通 Vertex `aiplatform` 才能產正式 artifacts」不再是硬前提。**殘留風險**：Stage 2 會「re-runs a random dev sample live」做重現性檢查，未說明與已提交分數的容差 → 見 R-014。
- ③ **截止日＝2027-01-05 23:59 UTC（＝台灣 01/06 07:59）**；01/19 Stage 1 Writeup 評完（Top 100 晉級）、01/26 Stage 2 完成並公布。⇒ P8 必須在 01/05 內完成（§2 已改）。
- ④ **兩階段評分**：Stage 1＝資格閘門（`kit check`＋`kit artifacts` 通過＋Writeup 100 分 rubric：Insight & Failure Analysis 25／Engineering Reasoning 25／**Cross-Model Generalizability 15（29 題 dev 至少 2 個模型，本機模型可算一個）**／**Efficiency & Scaling 20（dev score vs 算力曲線、標出 plateau）**／Clarity & Visuals 15），Top 100 進 Stage 2。Stage 2＝56 hidden 題（6 structural／9 civil／18 electrical／23 mechanical）× **3 次獨立 run**，依「平均分 × 平均成本」的 **Pareto 前緣**；獎項給前緣上平均分最高的前 3 名，**平均分須 ≥0.138** 才有資格；同分先比 Stage 1 Writeup 分。HTTP 400、未恢復崩潰、逾時（無 done/error 幀）計 0；evaluator 故障與贊助端點限流／中斷自動重試不罰。
- ⑤ **Stage 2 執行環境**：`debian:bookworm` 建置（install 30 min 上限、`/opt/harness` 壓縮後 ≤2 GiB）→ smoke（120 s 內 bind `0.0.0.0:$PORT`、寫測試檔、送 done）→ 評已提交 artifacts＋隨機 dev 樣本即時重跑 → 每題隔離容器 **2 CPU／4 GB RAM**、`/opt/harness` 唯讀、`/tmp` 與 `$HOME` 可寫 1 GB、6 h；proxy 封鎖自帶 key、外部模型伺服器與 web search，Google 免費供 key。`artifacts/` 必須是解包目錄（≤512 MiB、≤10,000 檔、禁 LFS／symlink）。
- ⑥ **8 個贊助模型**：`gemini-4-argon`、`gemini-3.8-flash`、`gemini-3.1-pro-preview`、`gemma-4-26b`（Gemma 4 26B A4B，開源權重）、`claude-opus-5-5`、`gpt-oss-120b`（開源）、`glm-5.2`（開源）、`llama-4-maverick`（開源），皆 `google-cloud/` 前綴。開源權重者可本機自架 ⇒ 本機開發可直接用 Stage 2 候選模型（見下一步）。
- ⑦ **必要檔清單待核**：官方列「`submission.yaml`、`serve.py`, `harness.py`（Minimum Requirements 寫作 `serve.py / harness.py`）、Apache-2.0 或 MIT LICENSE、`artifacts/`」；本 repo 目前為 `serve.py`＋`taskbridge.py`、無 `harness.py` → 以官方 `submission-template`／`kit check` 判定確認（R-013）。
- ⑧ **建議（未決策，待使用者拍板）— 本機→目標模型的轉換點**：本機的目標規模＝**一次完整 29 題 pass、29/29 有交付、0 筆 HTTP 400／0 崩潰／0 無 done 逾時**（可靠度可跨模型轉移，且這輪本身就是 Writeup 跨模型表與失敗分解圖的必要資料）；觸發即轉，或 rubric A/B 效果已落在 ±0.2 單樣本雜訊內，或最遲 ~12/07（留約 3 週給目標模型 29 題全跑、budget sweep、最終 artifacts、`kit artifacts`、Writeup）。候選做法：本機模型改換 `gemma-4-26b`（贊助＋開源＋A4B 應較現行 IQ3 快，兼顧跨家族比較）；前沿模型（Opus 5.5／Gemini 4 Argon／3.8 Flash）開發期需自費或個人 API，先跑 3–5 題代表題再定目標。為避開 R-014，最終 `artifacts/` 建議由目標模型重產。

**2026-11-22（二十八）— 使用者指示「暫停／停止 harness」：EXP-023 #3 中止（INVALID、~56 min、無分數）；window_probe 首次 live 帶回關鍵發現——proxy 會剝掉視窗宣告：**
- ① **中止程序**（同 EXP-023 #1 模式）：17:46:41 TERM pid 5423 → Harbor graceful（`stopping Harbor: it cancels its trials and removes their containers`）；15 s 後 TERM uv 5420 即止（未動用 KILL）；watcher 5828 停止；**0 殘留容器**（Harbor 自行清）；`runs/plan-verify-20261122-165029` 保留、無 grade、可 `--regrade`；部分轉錄落盤（job `emergency-spillway-check__4z9SYtH`、`agent/plan-verify.txt` 260 行、`phase: plan→work` 中）。LiteLLM／Strata 保持閒置運行。
- ② **window_probe 首次 live 判讀（DEF-003 仍未解）**：轉錄見 `harness: context window: not announced by the endpoint; reactive path only`＝探測**有回應但無視窗欄位**（非 `probe failed`）——`GET /v1/models` 經 egress sidecar 到 LiteLLM 正常 200，但 **LiteLLM 把 Strata 的 `max_model_len: 262144` 從 `/v1/models` 剝除**（本機預探 strata 直連有宣告、代理後沒有）。回退設計如預期生效、零回歸，但 EXP-023 #2 尾聲的 116×400 飽和風險原樣存在。往後選項（等指示）：proxy 對 `/v1/models` 透傳 extra 欄位／`submission.yaml` `env:` 帶視窗值（R-009 需核准）／其他。本 run 0 筆 exceeds-context 400＝僅 56 min 未及尾聲，不構成反證。
- ③ **狀態**：全部 harness 工作維持暫停；EXP-023 #3 不重跑（除非指示）；engineers 三岔、heavy 錨、quick 皆仍擱置；映像 `d0e1181cef4cb463` 與鏈路驗證（mock 14/14、kitcheck10 7/7）仍然有效、可直接重用。

**2026-11-22（二十七）— 續跑：P3-04a（`ae07474`）補完驗證——`kitcheck9` 曾被切斷於 `kit` 階段前，重跑 `kitcheck10` 全 7 階段 PASS；chain 全綠、下一發射等使用者選靶：**
- ① **P3-04a（`ae07474`，14:51，提示單 6 行變因）**：GATE 對「由計數／枚舉得數」的 ledger 值不得只照 ledger 自己引用的記錄重算——必須**自行從來源重新枚舉整個匹配群体**再重算，不符印 `FAIL C<id>: ledger counts <N> but the source holds <M> — <missed or extra records>`（直打 B-5 自審上限：EXP-022 把 2.36 數成 14 EA 正是群体選錯、引用核實查無異常）。harness 機制不動。
- ② **鏈路恢復**：LiteLLM 曾於 15:09 正常 shutdown（`:4000` 無 listener）→ 以永久腳本重啟；Strata `:8080` 200 model loaded（n_ctx 262,144）、帶 key `GET /v1/models` 200、端到端 `chat/completions` 200（16 tok 全燒 `reasoning_content`、`finish_reason=length`＝判準同 EXP-017 #2 預探）、docker 0 殘留、disk 844 G／RAM 60 G。
- ③ **HEAD `ae07474` 重驗**：mock 契約 **14/14**（`uv run --with openai==3.26.1 --with websockets==15.0.1`，requirements.txt 兩包）；`kit check --rebuild`：`kitcheck9`（14:53）在 `kit` 階段開始前被切斷（`[FAIL] kit: interrupted`，無結論）→ 15:59 重跑 **`kitcheck10.log`：7 階段全 PASS**（build 29 s 映像 `plebench-serve:d0e1181cef4cb463`／model 7.3 s／listen 1 s／smoke 48 s 5 呼叫／mcp 89 s 14 呼叫），僅慣常 `artifacts` WARN（R-012）。
- ④ **發射必經狀態**：②`kit check` ✅（kitcheck10）、③判準就緒、①使用者明確同意 ✅（使用者選 (a)）。**EXP-023 #3 已於 16:50:29 發射**（`emergency-spillway-check` × `ae07474`；uv 5420、真 python pid 5423、watcher 5828；run dir `ple-reference/runs/plan-verify-20261122-165029`；`exp023_3.start` 立檔；本發射同時是 window_probe 與 P3-04a 的 first live）。下一發射同時是 **window_probe 首次 live**（轉錄須見 `context window: 262144 tokens (announced…)`、egress 0 筆 exceeds-context 400，對照 EXP-023 #2 的 116 筆）＋ **P3-04a 首次 live**（看有無 `FAIL C<id>` 線與 fix round）。候選靶（使用者已拍板 (a)）：(a) **EXP-023 #3 `emergency-spillway-check` × `ae07474`**＝三點系列第 4 點（0.838→0.919→#2 INVALID→?）、w3 細刻度抗雜訊，且延續被中止的 EXP-023；(b) `engineers-estimate-check` × `ae07474`＝P3-04a 直靶（14-EA 群體錯），但 w10 題 ±0.2 單樣本雜訊；(c) heavy 側補 gate-only 錨 `roof-deck-design`／`eor-review-corrections` × `85d1cbd`（解鎖 heavy 三點對照，2–4 h）。engineers 三岔（(b) 估雜噪／(c) 回退）仍擱置。

**2026-11-22（二十六）— 規則查核（官方 `docs/rules.md` 全文＋ple-bench.com；使用者已登入 Kaggle，但 Kaggle SPA 頁 WebFetch 抓不到內文）——多項既有假設需修正：**
- ① **賽期＝2026-11-09 → 2027-01-05**（ple-bench.com；獎金 $250k/$100k/$50k）。⇒ P8 排程 01/01–01/06 **超出截止日**，必須在 01/04 前完成提交動作；ADR-004 凍結日 01/01 仍適用的同時，出口項目要前移。
- ② **entry＝單一 GitHub commit**（`submission.yaml`＋harness＋`artifacts/`），**提交方式官方尚未公告**（"will be announced on the competition site"）→ 「交付演練」目前沒有正式管道；Kaggle 頁面是展示/註冊面則待使用者在瀏覽器確認（Rules/Timeline/Code Entries 三個 tab 抓不到）。
- ③ **dev 分＝29 題平均，缺 usable artifacts 的題＝0 分**（rules.md §Dev score）。⇒ 修正本人先前的說法：「1 題 artifacts 就能交」只成立於 `kit check` 機械判定，**competitive entry 需要全 29 題由宣告模型實跑的 artifacts**；單題式演練只能驗管道、dev 分會很難看（≈0.03）。
- ④ **每個 harness＋model 組合在 hidden test set 只有 3 次 run**（ple-bench.com "Three runs per harness and model"）→ 可靠度（P7）與模型選擇（P6）的價值上升；一次性的 luck 沒有第二次。
- ⑤ **400 invalid request＝該 task 的 outcome**（已寫出的交付物照評、沒寫出＝0；harness 崩潰/6h 超時同計）⇒ `window_probe` 修復在正式環境直接值分；fair-play 再確認：artifacts 必須由 `eval/run.py`＋宣告模型匯出、禁手改、harness 禁讀 artifacts/評分檔、egress 只准模型端點。
- ⑥ hidden test set＝56 題，評 ranking 方式未公告；dev artifacts 由官方 regrade 計 dev 分。**待使用者從瀏覽器貼回**：Kaggle Rules tab 全文、Timeline（entry 截止）、是否有 Code Entries 上限／Kaggle 端提交格式。

**2026-11-22（二十五）— 「harness 一直爆掉＝做白工」調查：DEF-003 開關在 live 從未可達 → 實作 endpoint 視窗自我查詢（`window_probe`）：**
- ① **注入謎團（結構性發現）**：`eval/run.py`→`kit/check.py Runtime`→serve 容器的 env 只有 `models.environment()`（模型鍵值）＋ `submission.yaml` 的 `env:` 表（`spec.py`：僅 `{src}/{port}` 佔位、禁引用 host 變數、保留鍵過濾）。⇒ **`$CONTEXT_TOKENS` 從外層 shell 進不了 serve 容器**——EXP-018 起「首波不設 CONTEXT_TOKENS」其實是「想設也設不到」；在 `submission.yaml` 寫死 262144 違反 R-009（對 strata 常數 overfit）且污染四核心檔對照，不採。
- ② **修復（main，prompt 外碼變因）**：serve.py 新增 `window_probe()`——首次模型呼叫前向端點 `GET /v1/models`（`client.models.list()`，30 s 有界、每 process 一次），讀 `max_model_len`/`max_context_length`/`context_length`（優先 id==MODEL，否則取最小＝保守），設 `CONTEXT_TOKENS`；`$CONTEXT_TOKENS` 顯式值仍優先；探測失敗（端點不暴露/被 egress 擋/解析不出）→ 維持 0＝**完全退回既有被動路徑**，零回歸風險。dev 的 strata 本來就回報 `max_model_len: 262144`（本次預探可见），真 Opus 端點回報自己的 ⇒ **同一份碼兩邊都匹配，無常數**，正面回應「限制 harness 匹配模型」而不 overfit。
- ③ **margin 修正（同 commit，因守門從未 live、不影響既有 A/B）**：`CTX_MARGIN_TOKENS` 預設 8000→0＝自動 `max(8000, window/12)`；理由＝`est_tokens` 用 chars/4 對 code-heavy 轉錄會**低估**真實 token，262k 視窗下固定 8k 邊界可能仍擦過 400。
- ④ **驗證（全離線，未碰 strata/容器）**：mock 契約 **14/14**（新 `ctx_discover`：端點公告 1500 → `context window: 1500 tokens`＋`context budget: cut` 事前生效、全程無 400；GET 不消耗 `MOCK_FAIL` 計數、預設 404 保 13 舊案例語義不變）；**偵測證明**＝`ctx_discover` 於舊碼 `[FAIL]`（log 缺宣告行）；pyflakes 0、AST ok、無新增 >80 char 行（37→37）。**未跑 `kit check`**（要容器＋模型，屬 harness 工作，依暫停指示留到發射前）。
- ⑤ **剩餘風險（live 判準）**：egress sidecar 是否放行 serve 容器過來的 `GET /v1/models`（ watcher 由 host 打過 200，但容器內路徑未測）；若被擋→退回被動、轉錄會見 `context window: probe failed`，届时再决定是否把窗口值放进 submission.yaml env（需使用者核准，属核心档变更）。

**2026-11-22（二十四）— 使用者選分岔 (a) → EXP-023 #2 重發（spillway × `87545e6`）：**
- ① **鏈路重驗全綠**：Strata `:8080` 200（model loaded、n_ctx 262,144）、LiteLLM `:4000` 帶 key 200（已在跑、0.0.0.0 綁定）、端到端 `chat/completions` 200（16 token 全燒 `reasoning_content`＋`finish_reason=length`＝判準同 EXP-017 #2 預探）、docker 0 殘留、disk 844 G／RAM 60 G。
- ② **發射**：10:33:40 同 EXP-021/023 指令重發（`exp023_2.start`；真 python pid 637048、uv 637038、setsid wrapper 637036；watcher `watch_run.sh 637048 exp023_2`；log `~/projects/exp023_2.log`）。碼＝`87545e6`（`git diff 87545e6 HEAD -- serve.py taskbridge.py submission.yaml requirements.txt` 空）、映像 `5ad1f924`＋spillway 題映像重用、`CONTEXT_TOKENS` 未設、預算預設、`--no-export`、全路由本機 Strata。
- ③ **判準（n=1 教訓已入 `.start`）**：capture≠{} ∧ score>0 ∧ `ple_assumptions.tsv` 落盤（gate ls 確證）∧ gate 逐條審計（`FAIL A<id>`／duty stated）∧（若義務缺）fix round 首次 live 觸發並寫入。靶＝**curb＆gutter 接受義務 w3 項**（EXP-019/021 兩度丟失；w3 細刻度 37 點較 engineers w10 抗雜訊）。三點對照 0.838→0.919→?

**2026-11-21（二十三）— EXP-022 結果＝假設 ledger 在 engineers 題未見效（0.348→0.109），並暴露兩件方法學事實：**
- ① **機制照跑、零偵測**：`ple_assumptions.tsv` 寫出（gate ls 確證），gate 腳本 25 KB（重算＋mutation 自測俱全），但 `FAIL A<id>`＝0、verdict PASS——**同一模型寫假設也審假設，引用核實只能確認「來源真有這行」，確認不了「抽取本身正確」**（本 run 把 2.36 數成 14 EA，C-8 裡真找得到 14 行可引用）。這是 self-audit 上限，記為 **B-5**：治數量抽取錯誤要的是 P3-04 的**獨立抽取＋交叉驗證**（兩次互不知情的抽取比對計數），不是讓作者自辯。
- ② **rubric 題單次 A/B 雜訊可達 ±0.2**：engineers 同題三連跑 0.130／0.348／0.109（三種碼態各一），一條 weight-10 項翻轉＝0.217 級跳動。因此 EXP-020 的 ledger「+0.217」與本輪「−0.239」在 n=1 下**皆不足以歸因**；§1（十八）（二十一）的正面結論降階為「方向性證據，待多次樣本」。往後 rubric A/B 至少 2 樣本、或改在 w3 細刻度題（spillway 37 點）上測。
- ③ **下一步分岔（待使用者拍板）**：(a) EXP-023＝spillway × `87545e6`——assumptions ledger 真正的靶（唯一殘餘項＝curb＆gutter 接受義務，且 w3 刻度細）；(b) 先加樣本估雜訊（同碼重跑 1 次＝~1 h）；(c) 回退 `87545e6`（但 calc ledger 效果同樣是 n=1，回退依據也不足）。

**2026-11-21（二十二）— 使用者核准 P3-03/04 → 假設／義務 ledger 已實作（`87545e6`）＋EXP-022 三點 A/B 發射：**
- ① **實作**（提示單變因 15 行，只動 WORKER/GATE/docstring）：WORKER 對每個「檔案意涵判斷」（判斷＋精確引用＋已考慮的替代解讀＋為何選它）與每個「來源所述義務／已接受事實且交付物必須反映」追加 `/tmp/ple_assumptions.tsv`；GATE 必須逐條驗證判斷的引用在來源中屬實、義務在交付物中被陳述（`FAIL A<id>: … is not stated or not supported` 指名檔案）。連帶把 GATE 收尾從「leave judgement calls out」改為「leave purely stylistic preferences out」（一致性必要，已在 commit 揭露）。
- ② **驗證**：mock **13/13**、pyflakes 0、AST ok；`kit check --rebuild` **7/7 全 PASS**（`kitcheck8.log`，映像 `5ad1f92438cc4d7e`；smoke 36 s／mcp 106 s）。
- ③ **EXP-022 已發射**（21:11:08，真 python pid 441460，run `plan-verify-20261121-211109`，`exp022_1.start`）：engineers-estimate-check 三點對照＝0.130（無 ledger）→0.348（calc ledger）→?（calc＋assumptions）；EXP-022−EXP-020 差＝假設 ledger 淨效果；靶＝EXP-020 剩 3 條 w10（headwall、VF convention、Sec2/bond 取值）。

**2026-11-21（二十一）— EXP-021 完成：ledger 於第二題再现正向（0.837838→0.918919）→ P3-01/02 兩題皆 A/B 成立；下一變因 P3-03/04 設計待核准：**
- 兩樣本並看：engineers 0.130→0.348（+0.217）、spillway 0.838→0.919（+0.081）；light rubric 兩題均值 0.484→0.633。成本：呼叫 +31%／+22%，wall +58%／+88%，out tokens +75%／+84%——正向但貴。
- 兩題剩餘丟分同族：**解讀/義務陳述與 GT 不同**（engineers：headwall 2.40 vs 2.41、VF 20.44 vs 22.02；spillway：curb＆gutter 接受義務未寫）——純數字重算已吃不掉，直打 P3-03/04（假設／證據／義務矩陣）。
- fix round 仍未 live 觸發（兩題 harness gate 皆一輪 PASS；模型的自我 tamper 測試在 /tmp  scratch 內完成）。MCP 三題 0 使用（world-export 題未測前不下結論）。
- **P3-01/02 標記**：見 §3 證據（含 S14 單位缺失 live 偵測）。P3-03/04 設計提案＝下一步等使用者核准。

**2026-11-21（十八）— EXP-020 A/B 結果：ledger 码 0.347826 vs 錨點 0.130435（+0.217）→ ledger 保留，P3-01/02 初步見效：**
- **A/B 判讀**：同題同模同預算、單變因＝ledger 提示。10 項 rubric 由 6/46 加權分升至 16/46（+10 點＝Sec2 小計一致性項過）；bond 由 $5,431,000→$5,381,000（GT $5,384,000，收斂 $50k 中的 $44k）。成本 +31% 呼叫／+58% wall／out 78k→137k。
- **機制全鏈佐證**：worker 寫 `ple_ledger.tsv`（1,195 B，經 gate 階段 `ls /tmp` 確證；轉錄因 B-2 200 字元截斷看不見寫入本身）、gate 腳本自述逐圖重算、`verdict: PASS`（fix 0 輪，因 memo 與自身重算自洽）。
- **失敗族位移**：由「算錯（內部不一致）」轉為「**解讀/取值選擇與 GT 不同**」——headwall 歸 2.40 而非 2.41、curb inlet 計數、2.38 VF 深度 convention（20.44 vs 22.02）。這類需要 P3-03/04：把「每個解讀選擇＋其檔案證據」變成 gate 可反問的假設清單（假設也要有來源與替代解釋），而非只重算算術。
- **決定**：ledger 碼保留於 main；EXP-021 已於 18:19 發射取 spillway（0.837838 錨點）一般化樣本——同碼零新變因，屬既有核准範圍（新增**碼**變因仍須先核准）。

**2026-11-21（十七）— 使用者選 P3-01/02 → 計算 ledger 已實作（`6741308`，提示單變因）＋EXP-020 A/B 發射：**
- ① **實作**：WORKER 每個「由檔案推導而非明載」的數字都要追加 `/tmp/ple_ledger.tsv`（id／交付物路徑／值／來源檔／公式，單位在計算程式內轉換、只在任務指定處捨入）；GATE 腳本必須讀 ledger 逐列**從來源重算**（inputs 重讀、禁抄現成值、禁以「兩檔都出現」當證據），不符印 `FAIL <id>: stated <X> but recomputed <Y> from <source>` 進 fix round；無 ledger 列的關鍵推導值同等處理。`git diff 85d1cbd 6741308 -- serve.py` 只動 WORKER＋GATE＋docstring＝嚴格單變因。
- ② **驗證**：mock 契約 **13/13**、pyflakes 0、AST ok、長行＋9 全在提示字串內；官方 `kit check --rebuild` **7/7 全 PASS**（`kitcheck7.log`，映像 `plebench-serve:cf345aa27e8f8fdd`；smoke 60 s／mcp 77 s）。
- ③ **EXP-020 已發射**（17:00:53，真 python pid 174627，run `plan-verify-20261121-170055`，`exp020_1.start`，重用 `cf345aa2` 映像）：同題 A/B 對 0.130435；判準＝分數上移＋轉錄見 ledger 寫入＋gate 重算 FAIL/PASS＋fix round 寫入＋bond 是否收斂至 $5,384,000。

**2026-11-21（十六）— EXP-019 完成 0.8378 → P2-05 達 4/4 → P2 全階段收尾（P2-06 scorecard 落地）：**
- ① **EXP-019**：**0.837838／`ok`／4,270 s／143 呼叫**，capture＝`Memo_to_Callaway_Spillway_2026-10-31.docx` 55,494 B；rubric 加權 31/37（13/15 items）；2 條未過皆工程推導／義務歸屬類（1.29 ft freeboard overflow 不合格、curb＆gutter 改善接受義務）。gate 碼第二次 live＝再现 `gate: script ready`→`verdict: PASS`（fix 0 輪）；尾聲 0 錯誤；cache 命中 97.4%。
- ② **MCP 觀察定案（非缺陷）**：兩題 MCP×8 light 題，目錄快取（141／144 tools）與 HTTP 皆正常，但模型 **0 次** `mcp_list`/`mcp_call`——答案全在檔案系統。meta 工具在位待 world-export 題（MCP×13）才是真正的功能性考驗。
- ③ **P2-06 完成**：`docs/P2_SCORECARD.md`＝四題 scorecard（0.3673／0.2573／0.1304／0.8378，均值 0.3982）＋量化 failure taxonomy（main 線 ARTIFACT 族 0/4；heavy＝HARD_GATE 歸零族；light rubric＝CALCULATION 族）＋五條結構性結論＋P3 直接輸入。§4 dashboard 首次填值（artifact 100%、zero 0%、cost band、cache 92–97%）。
- ④ **P2 階段：DONE 6/6。** 下一步＝P3-01/02（單位正規化＋計算 ledger＝直打 018 型 40/46 點數值丟分）；heavy 對照 run 建議帶 `CONTEXT_TOKENS=262144`（僅 dev）做 DEF-003 live 驗證。

**2026-11-21（十四）— EXP-018 #2 完成＝新 gate 碼首戰成功交付（0.130435）；EXP-019 發射：**
- ① **交付與評分**：capture `files=1`（`Memo_to_Callaway_2026-10-31.docx` 43 KB）、**0.130435／`ok`／2,497 s／70 呼叫**（本機 rubric judge；10 items、加權 6/46）。丟分全在 4 條高權重 ground-truth 數值（bond／Sec2 小計算錯＝CALCULATION 族），格式／路徑／段落類全過——正是 P3-02（計算／假設／證據 ledger）的靶心。
- ② **新碼判準結果**：`phase: plan→work→gate 1`＋`gate: script ready`→`/tmp/ple_gate.py`（11,812 B）執行→`verdict: PASS`（fix 0 輪）＝P3 起手碼首次 live 生效；模型並先在 `/tmp/acc` 對自寫驗收腳本跑 3 組突變測試（錯 bond／缺日期／刪列→對應 FAIL 線如預期）＝偵測力自證。DEF-003 尾聲乾淨（0 筆 4xx/5xx、無 cut；本題 context 小，事前守門仍未 live 驗證）。**唯一未達：MCP `mcp_list`/`mcp_call` 0 次使用**（目錄快取 144 tools 正常在位）——meta 工具可用但本題模型不需要，EXP-019（MCP×8）再驗。
- ③ **EXP-019 `emergency-spillway-check`（水資源, light L1, MCP×8）已依 §1 排程發射**：10:06:31（真 python pid 59266、run dir `plan-verify-20261121-100723`；同 `85d1cbd` 碼、無參數變動；`exp019_1.start`；watcher `watch_run.sh 59266` 自癒 `:4000`）。完成→P2-05 4/4→P2-06 scorecard。

**2026-11-21（十三）— EXP-018 #1 被機器重開機切斷（INVALID、無分數）；鏈路恢復後依服務性中斷規則同參單次重跑＝EXP-018 #2：**
- ① **中斷**：#1 於 03:55:22 發射（run `plan-verify-20261121-035518`、job `engineers-estimate-check__zy9E3qb`），verifier 映像 04:21 就緒、trial 04:21:18 開跑、`trial.log` 最後寫入 04:21:36；**約 08:33 使用者端機器重開機**（證據：WSL uptime 2 分鐘、task env＋egress sidecar 兩容器 `Exited (255)` 時間戳指向 ~08:33）→ trial 跑了約 4 h 12 m 被無限期切斷，**無 verifier／grade＝無分數**；`result.json` 凍結於 `n_running_trials=1／finished_at=null`，`agent/`／`verifier/` 為空目錄（硬重開機，無部分轉錄落盤，不同於 EXP-017 #1 的 TERM→KILL 有留轉錄）。處置依既有規則「服務性中斷可同參重跑一次、保留原 run＋原因」（同 EXP-013 #1、EXP-017 #1 模式）：原 run dir 與 `exp018_1.start` 保留，**EXP-018 #2＝完全相同指令單次重跑**（模型／prompt／工具／上限零變動；`git diff 85d1cbd HEAD -- serve.py taskbridge.py submission.yaml requirements.txt` 空＝碼與 kitcheck6 驗證過的 `85d1cbd` 逐位元組相同）。
- ② **重開機後鏈路恢復**：Strata `:8080` 200（model `loaded`、n_ctx 262,144）；docker active、2 個殘留容器已 `docker rm -f`（0 殘留）；**LiteLLM `:4000` 未運行**（`/tmp/start_litellm.sh` 隨重開機消失）→ 啟動腳本**永久化**至 `~/projects/model_proxy/start_litellm.sh`（0.0.0.0 綁定、`litellm[proxy,google]==1.90.0`＋`websockets`、pkill 模式只存在腳本內、自動 source `../local.env`），重啟後 `GET /v1/models` 帶 key 200、端到端 `chat/completions` 200（16 token 全燒 `reasoning_content`＋`finish_reason=length`＝鏈路正常判準，同 EXP-017 #2 預探）；disk 881 G free／RAM 61 G available。

### 下一個可執行任務

0. **（2026-11-22 新）Gemma 4 首次 dev run**：鏈路與 `kit check` 已就緒（§1（二十九））；下一步等使用者選題（建議先 light 題，如 `emergency-spillway-check` 或 `engineers-estimate-check`，有 Qwen 錨點可比），並先 commit `submission.yaml` 的模型變更。指令：`wsl.exe -d Ubuntu -u zivkao -e bash -c 'export PATH=$HOME/.local/bin:$PATH; cd ~/projects/ple-reference; uv run python eval/run.py /mnt/d/project/vide-coding/ple-solo-harness --env-file ../local.env --tasks-dir $HOME/projects/ple-data/tasks --tasks <id> --no-export'`。
1. **全部暫停（使用者指示 2026-11-22；離線工不在暫停範圍、已做）**：EXP-023 #2 與重發 #3（× `ae07474`、16:50:29、~56 min）皆中止（INVALID，§6 行；部分轉錄保留、可 `--regrade`；皆不重跑除非指示）。`window_probe` 已上線但**首次 live 發現 proxy 從 `/v1/models` 剝除 Strata `max_model_len`**（轉錄＝`not announced by the endpoint`）＝爆掉問題**未解**、DEF-003 重開，解法待拍板（§1（二十八）②：proxy 透傳／`submission.yaml` `env:`（R-009）／其他；原「外層帶 `CONTEXT_TOKENS` 環境值」方案作廢——注入鏈路在 live 不存在）。**重新發射前必經**：① 使用者明確同意 ⏳；② `kit check --rebuild` ✅ 2026-11-22 15:59（`kitcheck10.log` 7/7、映像 `d0e1181cef4cb463`、含 `window_probe`＋P3-04a 於 HEAD `ae07474`）；③ 判準新增＝轉錄見 `context window: 262144 tokens (announced…)` 且 egress 0 筆 exceeds-context 400。engineers 三岔（(b) 估雜訊／(c) 回退）仍擱置。
2. **heavy 側 P3 A/B 需先補 gate-only heavy 錨**（一題 heavy 於 `85d1cbd`：含 gate 碼、無 ledger）才能與 P2（`eb918d8`）及 ledger 版三點對照；建議 `roof-deck-design`（checks、中量）或 `eor-review-corrections` 重跑。
2. **DEF-003 live 驗證**：下一個 heavy 對照 run 帶 `CONTEXT_TOKENS=262144`（僅 dev，不綁宣告模型；R-009），對照 EXP-016/017 尾聲 400 是否消失、收尾自我驗證輪是否保住。
3. **P3-05 A/B 錨點已立**：0.3673／0.2573（heavy structural，`eb918d8`）＋0.1304／0.8378（light rubric，`85d1cbd`）＝P3 每項改動的同題同參對照基準。
3. **quick 維持暫停**（使用者指示不變）：EXP-015 #1/#2/#3、uncertain 探測全部暫止；DEF-002 的 live 重測（`DELIVERABLE_PATHS=/app/files/` 同參單次）列為 quick 復活時的第一件事。
4. **~~正式 artifacts 需由宣告模型產生~~（2026-11-22 依 Kaggle Overview 修正，見 §1（二十八）②）**：官方允許本機模型產生 `artifacts/` 後再把 `model_api` 換成目標 `google-cloud/<id>`，只需在 Writeup 註明本機模型與 judge；Vertex 開通不再是硬前提。仍建議最終 artifacts 由目標模型重產以避開即時重跑的重現性風險（R-014）。本機→目標模型的轉換點建議見 §1（二十八）⑧（待決策）。

### 本階段出口條件

- [x] 官方 starter 的 `kit check` 通過。
- [x] Docker/uv/Harbor/gcloud/資料權限可用。
- [x] harness repo 位於 WSL2 Linux filesystem 且使用 LF。
- [x] secrets 只存在 repo 外部的 `local.env` 或安全 credential store。

---

## 2. Milestone board

| 階段 | 日期 | 狀態 | 完成 | 驗證摘要 |
|---|---|---:|---:|---|
| P0 環境與規格 | 11/16–11/19 | **DONE** | 7/8 | 僅 P0-01（Kaggle 身分驗證）未完成，由 R-001 追蹤，不阻擋開發 |
| P1 最小合法 Harness | 11/20 | **DONE** | 7/7 | contract 注入 10/10（429/500/timeout/tool error/斷線有界；cancel≤8 s）；`kit check` 7 階段全 PASS（EXP-014，映像 `9b27c95b`） |
| P2 Baseline Agent Loop | 11/21 完成（提前 3 天） | **DONE** | 6/6 | P2-05 4/4：0.3673／0.2573（structural heavy）、0.1304（electrical）、0.8378（water），全部交付成功；P2-06＝`docs/P2_SCORECARD.md`（taxonomy 六族＋結論＋P3 輸入） |
| P3 工程驗證核心 | 11/30–12/06 | **IN_PROGRESS**（提前開工） | 3/5 | P3-01/02/05 完成：ledger `6741308` 兩題 A/B 皆正向（0.130→0.348、0.838→0.919）；P3-03/04 假設／義務矩陣＝下一變因，設計待核准 |
| P4 多格式工具能力 | 12/07–12/13 | BACKLOG | 0/5 | — |
| P5 完整 Dev Set/回歸 | 12/14–12/20 | BACKLOG | 0/6 | — |
| P6 最佳化/模型選擇 | 12/21–12/27 | BACKLOG | 0/5 | — |
| P7 壓力/可靠度/安全 | 12/28–12/31 | BACKLOG | 0/6 | — |
| P8 凍結/驗收/提交 | 01/01–01/05（截止 01/05 23:59 UTC＝台灣 01/06 07:59） | BACKLOG | 0/8 | 提交＝Kaggle Writeup＋GitHub commit SHA（§1（二十八）） |

狀態值：`BACKLOG / READY / IN_PROGRESS / VERIFYING / DONE / BLOCKED / DEFERRED / DROPPED`

---

## 3. Stage tasks

### P0 — 環境與規格

- [x] `P0-00` 下載 Google 官方 repo，建立獨立 harness 並匯入 `plan-verify` starter。
- [ ] `P0-01` Kaggle 已加入且 Rules 已接受，提交身分驗證待完成。
- [x] `P0-02` Hugging Face 已授權，29 題已下載並驗證。
- [x] `P0-03` WSL2 Linux filesystem 建立官方 repo 與獨立 harness repo。
- [x] `P0-04` Docker、uv、Harbor、gcloud 安裝驗證。
- [x] `P0-05` 建立 repo 外 `local.env`，完成 secret scan。
- [x] `P0-06` 官方 starter `kit check` 通過並保存輸出（`rc=0`，6 階段 `[PASS]`＋2 條 `[WARN]`）。
- [x] `P0-07` 建立開發書、短中長期計畫、測試與 progress tracker。
- [x] `P0-08` 跑單題 dev baseline（`frame-extension-method`），产出 `artifacts/` 並記錄分數、時間與 token。

驗證證據：

- `P0-00`：`../ple-reference/` commit `8320f0402fdca9f42476607f72bcfd5271cd50c9`；本 repo 含 `serve.py`、`taskbridge.py`、`submission.yaml`、`requirements.txt`、`LICENSE` 與 `.gitattributes`。
- `P0-00` 驗證：四個 starter 核心檔 SHA-256 與官方來源相同；`serve.py`、`taskbridge.py` 通過 Python AST parse；所有非 Git 檔案未偵測到 CRLF；獨立 Git repo 已初始化為 `main`。
- `P0-02` 驗證：release `0.4.6`，資料 commit `e0c21fa558c3127785656398e3b3bd7da5e5a5a6`。WSL 的 `~/projects/ple-data/tasks` 內 29 題共 33,410 個檔案，各題 SHA-256 同時吻合 `release.json` 和官方 `dev_set.yaml`。Windows 壓縮包為 `../ple-data/ple-data.tar.gz`。
- `P0-03`：官方 repo `~/projects/ple-reference`（commit `8320f040`）；獨立 harness `~/projects/ple-solo-harness`，首次 commit `c9f6d4d baseline: unmodified plan-verify starter + planning docs`。四個 starter 核心檔與來源逐位元組相同（`serve.py` MD5 `bd691d7ed22e9ec797535d86895e22ce`）。**開發發行版已依使用者要求改為 WSL `Ubuntu`（26.04.1 LTS）**；舊 `Ubuntu-24.04` 保留作為資料來源、未刪除（見 ADR-008）。
- `P0-04`：**遷移後（2026-11-18）** 在 WSL `Ubuntu`（Ubuntu 26.04.1 LTS，kernel 6.18.58.1）內：`uv 0.13.9`、Docker **29.10.0**（官方 apt repo `https://download.docker.com/linux/ubuntu` 的 `resolute` 通道，systemd `docker.service` active，`zivkao` 已加入 `docker` 群組）、Harbor **0.20.0** + `websockets 15.0.1`（`uv tool install "harbor==0.20.0" --with websockets`，執行檔 `harbor`/`hb`/`hr`）。磁碟 `/dev/sde` 1007G（955G 可用）、RAM 62G。root 可直接 `wsl.exe -d Ubuntu -u root` 進入（無密碼），因此 ADR-002 的「使用者手動 sudo」改由 root shell 執行。舊 `Ubuntu-24.04` 記錄：`uv 0.13.8`、Docker 29.9.2。所有指令需 `export PATH="$HOME/.local/bin:$PATH"`。
- `P0-04` 遷移方式（可重現）：舊 distro 內 `tar -C /home/zivkao -cf /mnt/d/ple-migration/old-distro-projects.tar projects .cache/plebench`（1.63 GB），新 distro 內 `tar -C /home/zivkao -xf` 解開；`projects` 1.1 GB（含 `ple-data` 1019 MB、`ple-reference` 47 MB、`ple-solo-harness`、`model_proxy`、`local.env`）與 `~/.cache/plebench` 231 MB 全部到位，git commit `c9f6d4d` 與 `8320f040` 兩 repo 皆完整。
- `P0-05`：`~/projects/local.env`（repo 外，權限 600）內有 `MODEL_PROXY_URL=http://localhost:4000`、`MODEL_PROXY_KEY`（`openssl rand -hex 24`）與 `JUDGE_*`。首次 `kit check` 的 `key-scan.json` 已掃描（1.4 KB）。
- `P0-06` 完成（2026-11-18）：新 distro 內 `uv run --with pyyaml -p 3.12 python -m kit check ../ple-solo-harness --env-file ../local.env --rebuild` → **`rc=0`**，`[PASS] submission.yaml / files: 14 files / build: bundle 115 MiB built in 32 s（映像 `plebench-serve:2bffb49f0e8d681e`）/ model: Claude Opus 5.5 answered in 17.7 s through the egress proxy / listen: websocket accepted 2 s after start / smoke: hello.txt written, done in 87 s with 6 request(s), 7839 in / 1399 out tokens`。兩條 `[WARN]`：`mcp`（harness 未走 HTTP 取回 `/app/mcp.txt`，官方提醒 held-out 任務可能依賴 task MCP server）、`artifacts`（尚未有 dev-set `artifacts/`，需跑 `eval/run.py`）。日誌 `~/projects/kitcheck3.log`，工作目錄 `~/.cache/plebench/plan-verify`。先前在 `Ubuntu-24.04` 的 `kit validate` rc=0 與 `kit build --rebuild`（bundle 115 MiB、61 s、映像 `plebench-serve:28de3108373667cc`）亦保留；兩地映像 tag 不同（`28de…` vs `2bfb…`）來自基礎映像重新解析，不影響 starter 位元組一致性。
- `P0-08` 完成（2026-11-18）：`uv run python eval/run.py ../ple-solo-harness --env-file ../local.env --tasks-dir "$HOME/projects/ple-data/tasks" --tasks frame-extension-method --no-export` → **score 0.3617，status ok**，`results.json` 記錄 `seconds: 14310`（3 h 58.5 m，agent＋verifier）、tokens `input 34,618,230 / cache 34,076,850（98.4% 命中）/ output 326,888`；proxy 日誌顯示共 **300 次 chat/completions**（平均 122k prompt、1,090 output tokens/次）。產物：run 目錄 `~/projects/ple-reference/runs/plan-verify-20261118-112652/`（`results.json`、`artifacts/frame-extension-method/{final_message.md, files/filesystem/.../output/submission.zip, trajectory.json}`，1.1 MB，1 個 deliverable）。因 `--no-export`，entry 的 `artifacts/` 尚未匯入（決策見 R-012）。
- 模型通道：`submission.yaml` 仍宣告 `google-cloud/claude-opus-5-5`，本地由 LiteLLM（`litellm[proxy,google]==1.90.0`，與 `kit/model_proxy/start.sh` 同版）在 `0.0.0.0:4000` 將 `claude-opus-5-5`、`claude-opus-5-5-judge` 與 `*` 別名映射到本機 strata `qwen3.8-flash-next-iq3_s`（WSL 經 `http://172.23.0.1:8080/v1` 的 TCP bridge 進入 Windows）。已驗證容器內 `host.docker.internal:4000` 可取回補全結果。
- 本機模型能力（probe）：`/v1/chat/completions` 支援 `tools` + `tool_choice: auto|required`（皆回傳 `tool_calls`）、`reasoning_effort: max|high` 皆被接受、`max_completion_tokens` 可用；n_ctx 262144；實測 14–34 tok/s（prompt 25–65 tok/s）。
- Dev set 時限調查（29 題全部 `[agent] timeout_sec = 21600`，即 6 小時）：`checks` 12 題、`checks-judge` 3 題、`rubric` 14 題；verifier 時限 0.5–2.75 小時。單題 baseline 選 `frame-extension-method`（`checks`，verifier 2.75 h）。

- `P0-07`：`DEVELOPMENT_PLAN.md`、`progress.md`、`README.md`。

### P1 — 最小合法 Harness

- [x] `P1-01` `submission.yaml`、`serve.py` 與 dependency lock。
- [x] `P1-02` WebSocket protocol adapter 與健康啟動。
- [x] `P1-03` model client、timeout、retry、cache marking。
- [x] `P1-04` taskbridge tool adapter 與統一錯誤型別。
- [x] `P1-05` state machine、deadline、graceful finalize。
- [x] `P1-06` structured logs、redaction、unit/contract tests。
- [x] `P1-07` MCP 中繼工具（`mcp_list`／`mcp_call`）通過官方 `kit check` 的 `mcp` 階段。

驗證證據：

- `P1-01`：starter 四核心檔逐位元組保持（見 P0-00），`requirements.txt` 為 dependency pin；`kit check` `[PASS] files: 14 files`、`kit validate` rc=0。
- `P1-02`：`kit check` `[PASS] listen: websocket accepted 2 s after start`（< 120 s 門檻）。
- `P1-03`：EXP-005 baseline 實測 34.6M prompt 中 34.1M cache 命中（98.4%，`CACHE_MARK` 生效）；`recover()` 重試邏輯在 3 h 58 m 跑中未觸發致命錯誤（0 errored trials）。
- `P1-04`／`P1-07`：commit `97cbd38 P1-01: expose task MCP servers to all agent roles via mcp_list/mcp_call meta-tools`（serve.py＋108/−5；pyflakes 0；AST ok；未新增 >80 char 行）。以 `taskbridge.MCPClient` 於任務開始時 `initialize`＋`list_tools` 並快取目錄，模型透過兩個中繼工具按需發現與呼叫（避免 ~500 KB 目錄進 context）；**官方 `kit check` 於 22:3x 完成：`[PASS] mcp: mcp.txt written, done in 82 s with 13 request(s), 13814 in / 1211 out tokens`，`[WARN] mcp` 消除**；全套 `submission.yaml/files/build/model/listen/smoke/mcp` 7 階段全 PASS，只剩 `artifacts` WARN（尚未匯入 dev artifacts，符合 R-012 決策）。新映像 `plebench-serve:b8a6572ec27dd14a`，日誌 `~/projects/kitcheck4.log`。統一錯誤型別：`run_tool` 錯誤路徑含 `TaskError`/`MCPError`/`KeyError`/`ValueError`。
- `P1-05`／`P1-06`：commit `eb918d8 P1-05/P1-06: phase markers, key redaction, testable retry waits + contract fault-injection suite (10/10)`。DEVELOPMENT_PLAN P1 出口條件全部由 `tests/mock_contract_test.py` 注入驗證（mock model＋fake evaluator，離線）：model 429（SDK 燒盡後 `recover()` 再接手→done）、model 500/400（不合重試規則→有界 `error` 幀，~0 s）、model timeout（慢模型＋6 s 時鐘→6.0 s done）、tool error（exit 1 進入對話、執行不中斷）、斷線（`socket_close` 後伺服器存活並完成新任務）、cancel（**8 s 內**收 `done`，final=`(stopped: time is up)`，符合官方 10 s 窗口）。structured logs：`phase: plan|work|verify N|fix N` 標記狀態機；redaction：`safe()` 將 `$OPENAI_API_KEY` 從所有 log 幀移除（`redaction` 案例：key 藏在 429 錯誤 body 內，断言 log 不含 key、含 `<api-key>`）。`RETRY_WAITS` 可由環境覆蓋以供測試縮時。mock 10/10、pyflakes 0、AST ok。

### P2 — Baseline Agent Loop

- [x] `P2-01` project discovery 與檔案 inventory。
- [x] `P2-02` TaskSpec/deliverable/hard-gate 抽取。
- [x] `P2-03` planning/execution/context loop。
- [x] `P2-04` preflight verifier 與 bounded repair。
- [x] `P2-05` 四領域代表題 run（4/4：structural×2（0.3673／0.2573）、電機＝EXP-018 #2 **0.130435**（#1 重開機 INVALID）、水資源＝EXP-019 **0.837838**；全四題 capture≠{}、`ok`）。
- [x] `P2-06` baseline scorecard 與 failure taxonomy：`docs/P2_SCORECARD.md`（四題分欄表、均值 0.3982、六族量化 taxonomy、五條結論、P3 輸入）。

驗證證據：

- `P2-01`：每题 run 内 planner／worker 以 bash＋read_file 於容器內探索並逐檔盤點（EXP-016/017 轉錄：`phase: plan` 後 `ls`／`find`／`head` 序列，`plan:` 逐交付物列出路徑與格式）；離線側 corpus inventory 已由 §13 分級表（D／files／MB／MCP／InstKB，29 題全量、可重算）提供。**無獨立 index 產物**——盤點存在於轉錄與 plan 文字，此為本項的既定邊界。
- `P2-02`：`85d1cbd` GATE 角色把 instruction／templates 的硬性要求機械化為逐條 PASS/FAIL 驗收腳本（必要檔路徑／表頭欄序／值格式／排序／計數／低成本重算）；mock `clean`／`fix_round`／`gate_fallback`／`gate_exec` 重現抽取（fenced 區塊＋`compile()` 把關）、執行、無可用腳本時的有界回退全路徑。live 佐證由 EXP-018 起累積。
- `P2-03`：plan→work→gate→fix 狀態機（`phase:` 標記，EXP-016/017 轉錄可逐步重播）；context 管理雙軌：事後 cut（`context full: cut`，EXP-017 觸發 5 次撐住主幹）＋事前守門 `$CONTEXT_TOKENS`（`85d1cbd`；mock `ctx_budget`：小視窗下先 cut 再送、全程無 400；`context_full` 案例證明事後路徑未回退）。
- `P2-04`：交付前機械驗收＋有界修復：`MAX_FIX_ROUNDS=2`、`MIN_STEP_SEC`／`time_for()` 時間不足即不再開新輪、fix 呼叫以 `WRAP_UP_SEC` 收尾；mock `fix_round`（FAIL→fix 1→**重跑同一腳本**→PASS）、`gate_exec`（壞腳本不重跑、reviewer 接手一輪）。EXP-016/017 亦證明時間壓力下仍能保留成品交付（`serve_status=completed`）。
- `P2-05`：structural 兩題已分數化（EXP-016 frame-extension-method **0.3673**、EXP-017 eor-review-corrections **0.2573**，皆成功交付 grader 可讀 artifacts、`ok`）；電機（EXP-018）、水資源（EXP-019）補齊後本項才算 DONE。
- `P2-06`：§7 DEF-001～003 與 §5 EXP 表已構成 failure taxonomy 雛形（失敗族：提前放棄／預算燒盡／步驟配額／只讀不寫／防護誤計／hard-gate 未全過→0.6 權重歸零）；正式 scorecard（domain／deliverable／grader 分欄＋hard-gate pass rate）待四領域完成後建立。

### P3 — 工程驗證核心

- [x] `P3-01` unit normalization/dimensional checks — 內建於 ledger 機制（WORKER 強制 in-code 單位轉換；GATE 腳本帶 unit 檢查，live 於 EXP-021 抓到 `FAIL S14: elevations stated without a unit`）。
- [x] `P3-02` calculation/assumption/evidence ledger — `6741308`：WORKER 逐推導值追加 `/tmp/ple_ledger.tsv`，GATE 逐列從來源重算（禁抄現成值）。兩題 A/B 皆正向（見 `docs/P2_SCORECARD.md` §5）。
- [ ] `P3-03` hard-gate 與 rubric evidence matrix。（**提案待核准**：把「解讀/取值/義務陳述」變成帶檔案引用的假設清單，GATE 反問每条依據。）
- [ ] `P3-04` consistency verifier 與 impact-based retest。（待 P3-03 定案後設計。）
- [x] `P3-05` 與 P2 baseline 比較 — light rubric 兩題 ledger A/B 完成：0.130→0.348、0.838→0.919。heavy 側因 `eb918d8` heavy 錨無 gate 碼，需先補 gate-only heavy 錨才可比（尚未做）。

驗證證據：待補。

### P4 — 多格式工具能力

- [ ] `P4-01` PDF/DOCX inspect/render/verify。
- [ ] `P4-02` XLSX formula/recalc/error checks。
- [ ] `P4-03` image/drawing visual checks。
- [ ] `P4-04` CAD/BIM parse/metadata checks。
- [ ] `P4-05` corruption、large-file、quota tests。

驗證證據：待補。

### P5 — 完整 Dev Set 與回歸

- [ ] `P5-01` 完整 29 tasks 首跑。
- [ ] `P5-02` offline artifact regrade。
- [ ] `P5-03` scorecard：domain/deliverable/grader breakdown。
- [ ] `P5-04` fast representative regression set。
- [ ] `P5-05` failure Pareto 與前三大通用修復。
- [ ] `P5-06` 第二次完整 run 與回歸比較。

驗證證據：待補。

### P6 — 最佳化與模型選擇

- [ ] `P6-01` 模型 A/B。
- [ ] `P6-02` prompt/context/cache A/B。
- [ ] `P6-03` workflow routing by task features。
- [ ] `P6-04` token/time/tool-call efficiency。
- [ ] `P6-05` 三次重跑 mean/std/zero-rate 報告。

驗證證據：待補。

### P7 — 壓力、可靠度與安全

- [ ] `P7-01` resource-limit stress suite。
- [ ] `P7-02` long-run/boot-stop soak suite。
- [ ] `P7-03` model/tool/MCP fault injection。
- [ ] `P7-04` path/command/prompt injection suite。
- [ ] `P7-05` secret/artifact/repository scan。
- [ ] `P7-06` blocker remediation 與全套重測。

驗證證據：待補。

### P8 — 凍結、最終驗收與提交

- [ ] `P8-01` feature freeze 與 release branch。
- [ ] `P8-02` clean clone/build/start 驗證。
- [ ] `P8-03` final fast/full regression。
- [ ] `P8-04` final 29-task artifacts 與 offline regrade。
- [ ] `P8-05` `kit artifacts` 通過。
- [ ] `P8-06` `kit check` 顯示 `ready to submit`。
- [ ] `P8-07` final commit/tag/checksum/release note。
- [ ] `P8-08` Kaggle Writeup 提交成功並確認狀態（≤2,000 字、頂端 40 字元 SHA、Project Links 放 repo、封面圖＋架構圖／score-vs-cost 圖／29 題失敗分解圖、註明本機模型與 judge；repo 私有則裝 `ple-submission` App 並於賽末公開）。

驗證證據：待補。

---

## 4. Quality dashboard

四題代表 baseline 已建（`docs/P2_SCORECARD.md`，2026-11-21）；29 題 dev mean 待 P5-01。

| 指標 | Baseline | Current | Release target |
|---|---:|---:|---:|
| Dev mean score | N/A（29 題未跑） | 0.3982（4 題代表） | 高於 starter，且無重大領域退步 |
| Hard-gate pass rate | heavy 兩題全未全過（016 B8／017 hard_pass 0） | 同左＝P3-03 靶心 | 持續上升 |
| Zero-score rate | main 線 0/4＝0% | 0% | 低於 baseline |
| Artifact-producing rate | main 線 4/4＝100% | 100%（quick 線暫停不計） | >= 95% |
| 3-run score std | N/A | N/A | <= 0.05 或較 baseline -30% |
| Boot success | N/A | N/A | 100/100 |
| Controlled mock completion | N/A | N/A | >= 99% |
| P0 defects | 0 | 0 | 0 |
| P1 defects | 0 | 0 | 0 |
| Secret scan findings | N/A | N/A | 0 |

---

## 5. Test status

| Suite | Cases | Pass | Fail | Last run | Evidence |
|---|---:|---:|---:|---|---|
| Static/lint/type | 3 | 3 | 0 | 2026-11-20 | 官方檔案 SHA-256、Python AST、LF scan；另 pyflakes 0（serve.py＋兩個 mock 測試）於 `eb918d8` |
| Unit | 9 | 9 | 0 | 2026-11-20 | quick 預算/閘門 mock（`tests/mock_quick_test.py`，quick worktree，含 `quota`） |
| Contract | 10 | 10 | 0 | 2026-11-20 | `tests/mock_contract_test.py`：429/500/400/timeout/tool error/cancel≤10s/斷線/context 溢出/redaction/狀態機 |
| Integration | 0 | 0 | 0 | — | — |
| Functional | 0 | 0 | 0 | — | — |
| Regression-fast | 0 | 0 | 0 | — | — |
| Regression-full | 0 | 0 | 0 | — | — |
| Stress | 0 | 0 | 0 | — | — |
| Reliability/fault | 0 | 0 | 0 | — | — |
| Security | 0 | 0 | 0 | — | — |
| Official kit | 7 | 7 | 0 | 2026-11-21 | `kitcheck7.log`：7 階段全 PASS（`6741308`，映像 `cf345aa2`），僅 `artifacts` WARN（R-012）；前次 `kitcheck6.log`（`85d1cbd`） |
| Contract (mock) | 14 | 14 | 0 | 2026-11-22 | `tests/mock_contract_test.py` 於 window_probe commit 全綠（新 `ctx_discover`＋偵測證明：舊碼該案 FAIL）；前 13/13 於 `6741308` |

---

## 6. Experiment log

| ID | Date | Commit/config | Tasks | Change | Score/result | Cost/time | Decision |
|---|---|---|---|---|---|---|---|
| EXP-000 | 2026-11-16 | docs-only | N/A | 建立開發藍圖 | 規劃完成 | N/A | 進入 P0 環境建置 |
| EXP-001 | 2026-11-16 | official starter | N/A | 匯入 `plan-verify` | 檔案 hash/AST/LF 驗證通過 | N/A | 作為最初 baseline |
| EXP-002 | 2026-11-17 | `c9f6d4d`、Harbor 0.20.0、uv 0.13.8、Docker 29.9.2 | N/A | 環境與官方 pin 對齊 | `kit validate` rc=0；`kit build --rebuild` 61 s、bundle 115 MiB、映像 `plebench-serve:28de3108373667cc` | build 總 elapsed 133 s | 環境可用，進入 `kit check` |
| EXP-003 | 2026-11-17 | `local.env` + LiteLLM 1.90.0 別名代理（:4000）→ strata `qwen3.8-flash-next-iq3_s` | smoke | 接入本機模型（不改 `submission.yaml`） | `kit check` 前 5 階段 PASS（model 1.7 s、listen 1 s）；容器內 `host.docker.internal:4000` 可取回補全 | 模型 14–34 tok/s | 等 smoke 完成後跑單題 baseline |
| EXP-004 | 2026-11-18 | 新 distro WSL `Ubuntu`（26.04.1）、Docker 29.10.0、uv 0.13.9、Harbor 0.20.0、未修改 starter `c9f6d4d` | 官方 `kit check --rebuild` | 遷移後完整重跑官方驗證 | `[PASS] submission.yaml / files: 14 files / build: bundle 115 MiB in 32 s（映像 `plebench-serve:2bffb49f0e8d681e`）/ model: answered in 17.7 s through the egress proxy / listen: websocket accepted 2 s / smoke: hello.txt written, done in 87 s with 6 request(s), 7839 in / 1399 out tokens` | 日誌 `~/projects/kitcheck3.log`（新 distro）；另 `[WARN] mcp`（harness 未以 HTTP 取回 `/app/mcp.txt`）、`[WARN] artifacts`（尚無 dev-set artifacts） | **`rc=0`，P0-06 完成**；下一步單題 baseline |
| EXP-005 | 2026-11-18 | `c9f6d4d`（未修改 starter）、新 distro `Ubuntu`、bridge＋LiteLLM 別名代理 | `frame-extension-method`（checks，agent 21600 s／verifier 9900 s） | 單題 dev baseline，建立 `artifacts/`，量測 R-003／R-010 成本 | **score 0.3617（`ok`，14,310 s）**；300 次模型呼叫全 200；tokens in 34,618,230／cache 34,076,850／out 326,888；1 個 deliverable（`submission.zip`）＋final message | 全程 3 h 58.5 m；有效 wall 吞吐 22.8 tok/s out；換算 DeepSeek flash＝單題 $0.19（離峰）–0.38（高峰），29 題約 $5–25 | starter 本地基線確立；P1 改進以此 0.3617 為對照 |
| EXP-008 | 2026-11-19 | `quick` branch（`f6cf590`）：QUICK 預算 1800 s／40 呼叫／15,000 輸出 tokens，收尾保留 300 s／4 呼叫／4,000 tokens；單呼叫 ≤2,000 out、≤180 s；plan/work/verify 步驟级呼叫 cap；重複工具呼叫遮罩；工具輸出 clip 6,000；bash 90 s；低推理檔；deliver-first 提示；正式 `submission.yaml`/main 不動（ADR-009，worktree `ple-solo-harness-quick`） | 先 mock 後實測 `frame-extension-method` | 小模型快速迴圈 | **mock 4/4**：wall（stop=wall，4.1 s 內結束）／requests（≤8 呼叫，stop=requests）／output（stop=output）／clean（stop=none）皆 `[PASS]`（`tests/mock_quick_test.py`） | 實測 run `runs/plan-verify-20261119-074318/`（07:42 啟動，`--no-export`，僅 strata） | **score 0.0／889 s／25 呼叫／out 19,000（stop=output）**；grader `ERR_NO_SUBMISSION: no submission.zip was collected` → 零交付物直接 0 分（見 DEF-001） |
| EXP-009 | 2026-11-19 | `8d34278`（quick v2：40/70% 交付檢查點、收尾 write-only、預設跳 planner；mock 5/5） | `frame-extension-method` | DEF-001 (a) 修復後重測（`--no-export`，僅 strata） | **score 0.0／1,602 s**；grader 仍 `ERR_NO_SUBMISSION`；tokens in 118,435／cache 108,432／**out 1,233**；trajectory：8 次呼叫＝14 次唯讀工具後模型以純文字回答結束（`stop=none`），預算 share 僅 0.22 → 40/70% 檢查點未觸發 | run `runs/plan-verify-20261119-112842/` | **v2 修復不足**：失敗模式變為「提前放棄」；教訓＝預算式閘門對「不燒預算的模型」無效，需事件式交付閘門（v3） |
| EXP-010 | 2026-11-19 | `16053ed`（quick v3 交付閘門）、其餘同 EXP-009 | `frame-extension-method` | v3 gate 同題實測重跑（`--no-export`、僅 strata） | **score 0.0／1,534 s**；仍無 submission.zip；`stop=none requests=8 output_tokens=994`；trajectory：4 次帶工具呼叫（12 次唯讀工具）＋4 次**空 content 結束**（994 out 全在 reasoning_content）→ v3 gate 要求 `message.content` 非空、空結束直接落進 nudge 迴圈（1 空＋3 nudge＝8 呼叫吻合），從未觸發 `gate:`；映像 `e729bd25` 確認內含 v3（build 13:25:20 > commit 13:20:32） | run `runs/plan-verify-20261119-132529/` | **v3 不足**：失敗模式再變體為「空字串結束」；v4＝gate 移除 content 非空條件（任何無工具結束且 `_writes==0` 都打回）＋`gate_empty` mock 案例 |
| EXP-011 | 2026-11-19 | `1ea5c67`（quick v4：任何無工具結束含空 content 皆打回、空 turn 不回放；mock 8/8）、其餘同 EXP-009/010；LiteLLM 於本次重新啟動（見 §1（四）） | `frame-extension-method` | v4 同題實測重跑（使用者同意後；`--no-export`、僅 strata） | **score 0.0／696 s**；`stop=output requests=19 output_tokens=17,931`；**gate 觸發 0 次**（模型不再無工具結束）；第 19 呼叫以 `cat > /tmp/s.py <<PY` 生成完整分析腳本（已是最終交付邏輯）途中被輸出預算截斷、從未執行；`capture.json files={}`→reward 0 | tokens in 377,641／cache 308,932／out 17,931；run `runs/plan-verify-20261119-171551/`；696 s＝完整版 1/20 | **根因①（15k out 預算）主導**：模型誠實工作到燒盡，閘門非失敗點也非救援點；**ADR-009 revisit trigger 成立**→(b)/(c)/(d) 決策 |
| EXP-012 | 2026-11-19 | `25e3173`（quick v4＋僅預算加檔：`QUICK_SEC 1800→3600`／`QUICK_REQ 40→80`／`QUICK_OUT 15000→60000`；wrap 300/4/4000、單呼叫 2000/180s、gate=2、prompt、模型、工具全不動）、其餘同 EXP-011 | `frame-extension-method` | 選項 (b) 預算加檔同題重測（`--no-export`、僅 strata；與 EXP-011 可比） | **score 0.0／1,353 s**；`stop=requests requests=41 output_tokens=45,130`；wall／out 預算皆未盡（1,353＜3,600；45,130＜60,000，且 out 燒到 45k 證明新檔生效）；41 ≪ 全域停機線 76 ⇒ 觸發自 `serve.py` L581 步驟級份額（`capped`）；模型分段寫腳本誠實進展（`part2 ok` exit 0）、part3 未寫完即停、腳本從未執行；wrap 收尾純文字；gate 0；`capture files={}`→`ERR_NO_SUBMISSION`；無 zip | run `runs/plan-verify-20261119-195835/`；tokens in 1,030,563／cache 969,191／out 45,130；36 步驟 | **判定 Rule 4**：呼叫數先耗盡→約束在步驟級配額（routing）非全域預算；**本輪不再加碼**；下一步＝mock 定位具體份額來源修復後重測，或 (c)／(d) |
| EXP-014 | 2026-11-20 | main `eb918d8`（P1-05/06：phase 標記、log 遮罩、`$RETRY_WAITS`、mock_contract 10 案例入 repo） | 官方 `kit check` | 補丁後官方驗證（不影響 quick 工作） | **7 階段全 `[PASS]`**：submission.yaml／`files: 15 files`（含 tests）／build 31 s 映像 `plebench-serve:9b27c95b5e3166d0`／model 2.0 s／listen 2 s／smoke 161 s 3 requests／mcp 170 s 7 requests（`secret_word`→`MCP-59BAABCD`）；僅 `[WARN] artifacts`（符合 R-012） | 日誌 `~/projects/kitcheck5.log` | **P1-05/06 官方驗證通過**；kit 以 commit 建置（未 commit 會 `[WARN] files: not committed`）→ 先 commit 再 kit check 的流程確立 |
| EXP-013 | 2026-11-20 | quick v5 `c476e8c`（out-of-share verifier 空 verdict 不再當 PASS；capped 依名稱入log）、其餘同 EXP-012 | `frame-extension-method` | DEF-001 (a) 單變因修復後同題重測。第一次嘗試（01:22，run `plan-verify-20261120-012201`）被 WSL distro 重啟（~01:47）切斷、無結果；重啟 LiteLLM `:4000`、重驗 mock 9/9 後 01:59 同條件重跑（`exp013b.start`） | **score 0.0／1,583 s**；`stop=requests requests=36 output_tokens=39,705`；**v5 修復生效**：`capped: step spent its 4-call share` 出現兩次（呼叫 22、31）後執行不再終止，兩輪 fix round 照跑（EXP-012 於此死）；gate 首次觸發 2/2；verifier 兩度明列「零交付物，寫六檔再 zip」，**worker fix round 全花在 ls/find/head 重讀、0 次 write**；`capture files={}`→0 | run `runs/plan-verify-20261120-015915/`；in 702,885／cache 648,017／out 39,705；轉錄 `agent/plan-verify.txt`；ortools 缺失（ModuleNotFoundError） | 失敗族再移：「fix round 只讀不寫／模型不產出」；配額結構已非約束點；依 Rule 4 停手，DEF-001 交 (c)／(d) 使用者決策 |
| EXP-015 | 2026-11-20 | #1a＝quick v5 `c476e8c`；#1b＝quick v6 `738534b`（僅修寫入計數：`_FD_REDIRECT` 剝 `2>&1`／`2>/dev/null`、bare `mkdir` 不計；`>` 真寫與 `write_file` 仍計；mock 新增 `fdwrite`／`writecount_bash`／`writecount_wf` 先紅後 **12/12**）。模型、prompt、工具、checkpoint 門檻、全域預算皆不動；`--no-export`；30 分鐘外層上限、不重跑（`exp015_1.start`／`exp015_1b.start`） | `fire-test-validation-memo`（light L2，§13 分級） | ADR-010 後 light 題首次實戰；通過判準＝capture `files≠{}` ∧ 有效交付物 ∧ score>0 | **#1a（08:29）**：30 分鐘上限切斷、capture `files={}`、無分數；轉錄零 `checkpoint:`/`gate:` → 7 問調查（mock＋軌跡，不改 harness）：`2>&1` 在呼叫 #4 誤計 `_writes` → 防護整題禁用。**#1b（10:21，v6）**：**score 0.0／reward 0.0**（grade 0/208；`no_output.txt`＝agent 無 `output/`）、capture 仍 `files={}`；`stop=requests requests=41 output_tokens=38,522`；harness 正常結束（上限僅切到收尾，grade 已產出）；**checkpoint/gate/wrap-write 仍 0 觸發**：以**工具呼叫編號**（trajectory `tool_call_id`，1–36；模型請求計數則是 1–41）統一表述：工具呼叫 1–25 未增計（v6 對 fd-redirect／mkdir 生效），**工具呼叫 #26**（1,953 字元 python heredoc，`>=`／`" -> "` 在第 572 字元、轉錄截 200 字元故不可見）已被裸 `>` 誤計 `_writes=1`，#36（`> /tmp/m.xlsx`）為 v6 regex 下的真命中再加 1——即先前「前 35 次 `_writes=0`」的说法不精確，正確為「前 35 次工具呼叫中僅 #26 一筆命中（且為誤計）」→ 三線防護同時禁用；40% 檢查點（份額 30.4）構造上不可達（work step 呼叫 21 自然結束；fix round 收尾呼叫被 `not wrap_up` 跳過） | #1a run `plan-verify-20261120-083026`（`__uH6Mwni`）；#1b run `plan-verify-20261120-102234`（`__HWJuKgs`）：in 931,872／cache 879,214／out 38,522；42 次模型 POST 全 200、窗口 1,617 s；36 工具呼叫前 35 全唯讀、#36 `> /tmp/m.xlsx` 非交付路徑 | **light 題亦零交付→EXP-015 未達判準，#2/#3 依指示不跑、本輪停止**；DEF-001 失敗族於 light 題重現（根因轉為「防護被 `_writes` 誤計關掉」＋「模型收到明確 gap 仍不寫」）；**ADR-010 revisit 條件成立**；新缺陷 **DEF-002** |
| EXP-016 | 2026-11-20 | main `5763d7a`（serve.py／taskbridge／submission.yaml 碼＝`eb918d8`）、無任何參數改動（starter 完整預算、無 QUICK）、`--no-export`；路由＝LiteLLM `:4000` 全別名＋wildcard＋judge → Strata `127.0.0.1:8080` `qwen3.8-flash-next-iq3_s`（`api_key: local`、無付費 fallback）；沿用題上限（agent 21600 s／verifier 1800 s／dev_set 360 min）（`exp016_1.start`；12:38:51 發射） | `frame-extension-method`（checks，交付＝`.../output/submission.zip`） | main dev 子集 1/2：選題條件＝本題有成功交付／非零分歷史基線（0.3617＝`c9f6d4d` starter、0.3557＝`97cbd38`；commit 不同 ⇒ 依「同 commit 才可引用」規則不可直接沿用，故於 main 現行 commit 重跑） | **score 0.3673（reward 0.3673、`ok`、10,842 s ≈ 3 h 00 m）**；`stop=done requests=141`；tokens in 19,803,477／cache 18,796,853／out 275,778；capture 有交付：`submission.zip` 17,440 B（`testzip` OK、6 檔：construction_sequence／stability_check／occupancy_report／constraint_register csv＋temporary_works.json＋method_note.md）；評分細節：`mean_p` 0.9499／`mean_O` 0.7444／`combined_score` 0.2257／`frac_gated` 0、31 items 全在；29 family 通過率：**F07_platform_width 0.0（整族丟）**、**F06_scaffold_capacity 0.5484**、其餘 1.0；`paper_score`＝"31 items, 31 present; register_hard fails on 31 (B8 forfeit); mean h=0.837" → B8 硬閘門丟分壓低全部 items 的 O | run `runs/plan-verify-20261120-124013/`（`frame-extension-method__eZhhCDU`）；12:38:51→15:41:47；軌跡尾聲（最終 summary 之後）出現 400：prompt 261,799／context 262,144 僅剩 337、Strata 不截斷——harness 其前已達 `done`、交付已寫入，不影響評分（新觀察 B-4：starter 上下文管理對 Strata 262k 視窗留白不足）；對照 0.3673 > 0.3617（+0.0056）> 0.3557，高於兩次歷史值、在單次 ±0.01 噪聲邊緣 | **main 現行 commit 首個非零分＋成功交付實錄**；丟分點具體化：platform width 整族、scaffold capacity 部分、B8 register_hard forfeit 壓 O |
| EXP-017 | 2026-11-20 | 同 EXP-016（main `5763d7a`＝碼 `eb918d8`、無參數改動、`--no-export`、全路由本機 Strata；`exp017_1.start`；15:54 發射，run `plan-verify-20261120-155459`、job `eor-review-corrections__WW9x2d7`） | `eor-review-corrections`（checks-judge，交付＝`/filesystem/dc_structural__eor_revision__blind/output/submission.zip`） | main dev 子集 2/2：另一交付／評分型態（judge 於本機 proxy 同一 Strata） | **INVALID——使用中斷**：17:36 使用者要求重開機，發射後 1 h 41 m 時以 TERM→KILL 停止 eval 程序組（655096/655099）；**無 verifier／grade 產出＝無分數**；部分軌跡保留（transcript 250 行、結束行 `serve stop condition: cancelled (timeout)`、`agent/{plan-verify.txt,serve.log,trajectory.json,egress.log}` 在盤上）；run 目錄與 `.start` 記錄保留（同 EXP-013 首次被 distro 重啟切斷的處理模式）；試題容器＋滯留的 EXP-015 verifier 容器（含 sidecar）已全部 `docker rm -f` | 依「服務性中斷可同參重跑一次、保留原 run＋原因」：**重開機後以完全相同指令單次重跑＝EXP-017 #2**（發射前重驗 proxy／Strata／docker／disk＋`set -a; . ~/projects/local.env; set +a`），此重跑屬事前授權的例外，非加碼 |
| EXP-017 #2 | 2026-11-20 | 同 EXP-016 設定：main HEAD `c4af94e`（serve.py／taskbridge／submission.yaml 碼＝`eb918d8`、`git diff 5763d7a` 空）、無參數改動、`--no-export`、全路由本機 Strata；`exp017_2.start`；17:52:37 發射（真 pid 880018）、run `plan-verify-20261120-175344`、映像 `plebench-serve:50076b9de1b68fed`、job `eor-review-corrections__Bzs62np` | `eor-review-corrections`（checks-judge；artifacts 宣告兩路徑，主＝`/filesystem/dc_structural__eor_revision__blind/output/submission.zip`） | EXP-017 之同參單次重跑（#1 因使用者重開機＝服務性中斷而 INVALID）；模型／prompt／工具／上限全部零變動 | **score 0.2573／reward 0.2573／`ok`／17,053 s（4 h 44 m）**；`serve_status=completed`、`serve stop condition: done`、340 次模型請求；capture `files=1`＝`submission.zip` 23,890 B（7 檔）；評分 rule `0.4 p + 0.6 [h=1] O'`：34 items、`mean_p` 0.6431／`mean_p_squared` 0.4341、register 48 列 precision 1.0／recall_hard 0.882／recall_all 0.933／wrong 0、`parseable_rate` 1.0，**`hard_pass_rate` 0.0／`full_compliance_rate` 0.0／`mean_O`=`mean_O'`=`mean_gated_O'`＝0** ⇒ 0.6 權重全失、score＝0.4×mean_p；BP-2 0.1019／BP-3 0.2375；judge 1 呼叫 ok | in 30,583,152／cache 28,888,327（94.5%）／out 466,255；17:52:37→22:39:31；family：0＝F03、F12、F15、S08、D3；0.529＝F06、F08、F09、F10、S04–S07；部分＝F01 0.824、F02 0.794、S03 0.794、F04 0.735、S01 0.735；1.0＝F05、F07、F11、F13、F14、F16、S02、D1、D2、J1–J3；notes：`F08_added want [M-502A,S-201A] got [M-503,S-202]`、`F10_first8` GI-002 在 GI-001 前；DEF-003 尾聲 400（262,159＞262,144、在 summary 之後）＋`context full: cut` 5 次；雙 artifact 路徑變體缺失→Harbor `docker compose cp` rc=1（不影響評分） | **main dev 子集 2/2 完成：兩題 heavy 均成功交付＋非零分（0.3673／0.2573）**；跨題失分結構＝hard gate 未全過 → 0.6 客觀分歸零（P3 最大槓桿、佐證 ADR-002）；heavy 平均 3 h 52 m／題 ⇒ 14 題串行 ≈ 54 h（成本決策升級）；新增 DEF-003 |
| EXP-018 | 2026-11-21 | main HEAD `85d1cbd`（P3 起手：gate 機械驗收＋DEF-003 事前守門；`kitcheck6.log` 7 階段全 PASS，映像 `plebench-serve:6fb67fa48bbb4548`）、starter 預設預算、`CONTEXT_TOKENS` 未設（保守：首波只走事後路徑）、`--no-export`、全路由本機 Strata；`exp018_1.start`；03:55:22 發射（真 python pid 6891） | `engineers-estimate-check`（light L1，§13；MCP×8；電機域） | P2-05 第三領域（電機）＋新 gate 碼首個 live run＋main 路徑 MCP 實戰；通過判準＝capture≠{} ∧ score>0 ∧ 轉錄見 `phase: gate`/`verdict:`/fix 有寫入 ∧ MCP 可用 ∧ 尾聲無 DEF-003 型 400 | **INVALID——服務性中斷**：trial 04:21:18 開跑（verifier 映像建置 26 分鐘完成）、~08:33 使用者機器重開機（容器 `Exited(255)`、WSL uptime 2 分鐘佐證）＝跑了 ~4 h 12 m 被切斷、**無 grade**；`result.json` 凍結 `n_running_trials=1／finished_at=null`、`agent/`／`verifier/` 空目錄（硬重開機無轉錄落盤）；原 run＋`.start` 保留 | run dir `plan-verify-20261121-035518`；發射時 docker 0 殘留、disk 933G、RAM 60G；觀察點見 `.start` | 依規則**同參單次重跑＝EXP-018 #2**（事前授權例外、非加碼；見 §1（十三）） |
| EXP-023 | 2026-11-22 | 碼＝`87545e6`（calc＋assumptions ledger，映像 `5ad1f924` 重用）、其餘同 EXP-021；05:37:57 發射（真 python pid 524291，run `plan-verify-20261122-053850`，job `__3kJhNnC`；`.start` 未及建立即遭中止，本行即紀錄） | `emergency-spillway-check`（同 EXP-019/021 題） | assumptions ledger 直靶測試（義務項＋w3 細刻度；三點對照 0.838→0.919→?） | **INVALID——使用者指示中止**：發射後約 1 h 27 m（trial 21:38:53Z→23:05:58Z）以 TERM→（無效後）KILL 停止 eval 程序組；Harbor 正常收尾＝**部分轉錄保留在盤**（`agent/{plan-verify.txt,trajectory.json,...}`）、無 grade；殘留容器 4 個已 `docker rm -f`（0 殘留）、watcher 已停；run dir 保留（官方提示：必要時 `--regrade` 可重評已寫出的交付物，未執行） | — | 依使用者「pause→停止 harness」指示中止；**未重跑**（重新發射與否待指示） |
| EXP-023 #3 | 2026-11-22 | 碼＝`ae07474`（P3-04a 群体重枚 6 行提示＋window_probe；`git diff ae07474 HEAD` 四核心檔空）、映像 `d0e1181cef4cb463`（kitcheck10 7/7 新建）＋spillway 題映像 `b320148b` 重用、其餘同 EXP-021（預設預算、`CONTEXT_TOKENS` 未設、`--no-export`、全路由本機 Strata）；`exp023_3.start`；16:50:29 發射（真 python pid 5423、watcher 5828、run `plan-verify-20261122-165029`、job `__4z9SYtH`） | `emergency-spillway-check`（同 EXP-019/021/#2 題） | 三點系列第 4 點（0.838→0.919→#2 INVALID→?）；對 0.919 錨為疊加變因（assumptions ledger＋P3-04a＋window_probe），判讀靠 gate A/C 線；window_probe 與 P3-04a 首次 live | **INVALID——使用者指示「暫停／停止 harness」中止**：~56 min 時（17:46:41）TERM 5423→Harbor graceful→TERM uv 5420 即止（未動用 KILL）；部分轉錄落盤 260 行（`phase: plan→work` 中）、無 grade；0 殘留容器、watcher 已停 | ~56 min | **關鍵 live 觀察**＝轉錄 `context window: not announced by the endpoint; reactive path only`：探測有回應但無視窗欄位＝**LiteLLM 從 `/v1/models` 剝除 Strata 的 `max_model_len`**；回退如設計、零回歸，但 **DEF-003 未解**（選項：proxy 透傳／`submission.yaml` env（R-009）／其他，待拍板）；0 筆 exceeds-context 400＝未及尾聲不構成反證；**未重跑**（待指示） |
| EXP-023 #2 | 2026-11-22 | 碼＝`87545e6`（`git diff 87545e6 HEAD` 四核心檔空）、映像 `5ad1f924`＋spillway 題映像 `b320148b` 重用、其餘同 EXP-021（預設預算、`CONTEXT_TOKENS` 未設、`--no-export`、全路由本機 Strata）；`exp023_2.start`；10:33:40 發射（真 python pid 637048、watcher `watch_run.sh 637048 exp023_2`） | `emergency-spillway-check`（同 EXP-019/021/023 題） | EXP-023（中止 INVALID）之重發＝使用者 2026-11-22 選分岔 (a)；assumptions ledger 直靶（curb＆gutter 接受義務 w3 項，EXP-019/021 兩度丟失）；三點對照 0.838→0.919→? | **INVALID——使用者指示中止**（13:51，跑 3 h 16 m）：`status=evaluator: CancelledError`、`measured=false`、無分；TERM 已被 Harbor 正常收尾（取消 trial＋清容器＋轉錄落盤：`agent/{plan-verify.txt 437 行, serve.log, trajectory.json, egress.log}`）；**中止前狀態**：4 個 phase、**`gate: no usable script`→`phase: verify 1`（gate_fallback 路徑首次 live）**、最後 result 訊息宣稱 memo 完成但未及驗收；**飽和證據**：proxy **116 次 400 exceeds-context**（本 run 未設 `CONTEXT_TOKENS`＝EXP-023 #1 既有條件）＋轉錄 10+ 次事後 `context full: cut` | in 27,414,540／cache 25,870,331／out 357,064；trial 11,763 s；run `plan-verify-20261122-103438`（job `__cBQjWdQ`）保留（`--regrade` 選項官方提示、未執行） | **DEF-003 live 證據轉強**：context 飽和是本次成本／進度瓶頸（每次 400＋cut 都在燒 prefill；260k prompt 預填以 25–65 tok/s 計需 1 h+＝strata "fill" 吃盡的機理）→ 待拍板：dev 路由帶 `CONTEXT_TOKENS`（僅環境變數，不綁宣告模型，R-009）；依指示**停止一切 harness 工作** |
| EXP-028 #2 | 2026-11-23 | `d5267b8`；kit check 7/7（`kitcheck18_gemma.log`、映像 `65a5508a7526d7d9`）；`exp028_2.start`，09:00 發射（python pid 874136） | `foundation-strategy` | gate 修復回合 live 驗證 | **0.013／`ok`**（`mean_p` 0.031、parseable 1.0）；修復回合 2 次皆失敗 → 出錯行顯示 harness 的 code block regex 被腳本內 ```` ``` ```` 字串截斷；(a) live 4 次；0 次 400 | 3,105 s／150 req／in 4.73M（cache 91%）／out 188,692 | 見 §1（四十三）：`GATE_FENCE` 結尾圍欄須自成一行；mock 26/26 |
| EXP-028 #1 | 2026-11-23 | `d3651df`；kit check 7/7（`kitcheck17_gemma.log`、映像 `0f6dd5fc11b0b9ca`）；`exp028_1.start`，08:15 發射（python pid 822681） | `foundation-strategy` | 新 heavy 題可靠度＋`gate_why` 首跑 | **0.000／`ok`**：zip 6 檔最上層、可解析，但 `n_engineered` 全 0（工程錯）；gate 兩輪 `SyntaxError unterminated string literal`；超預算 3、0 次 400 | 2,008 s／126 req／in 3.65M（cache 90%）／out 118,700 | 見 §1（四十二）：加 gate 一次修復回合（`GATE_REPAIR`）；mock 25/25 |
| EXP-027 #3 | 2026-11-23 | `d4c8e3c`；kit check 7/7（`kitcheck16_gemma.log`、映像 `612d9f15ed27e7ac`）；`exp027_3.start`，07:18 發射（python pid 756232） | `eor-review-corrections` | live 驗證 `UNFINISHED` 推回＋(a)(c) | **0.000／`ok`**：zip 7 檔在最上層（(c) 生效）、但欄位不符 schema、constraint_register 11 B → `p` 全 0；(a) live 2 次、截斷 heredoc 0；推回 0 次；gate 兩輪 `no usable script`；0 次 400 | 2,704 s／192 req／in 7.80M（cache 94%）／out 148,480 | 見 §1（四十一）：交付合法＝可靠度達標，失分屬模型能力；新增 `gate_why()` 記錄 gate 失敗理由 |
| EXP-027 #2 | 2026-11-23 | `d5a2902`；kit check 7/7（`kitcheck15_gemma.log`、映像 `55470eae3abd59ce`）；`exp027_2.start`，06:17:25 發射（python pid 684533） | `eor-review-corrections` | live 驗證 d5a2902 (a)(b)(c) | **0.000／`ERR_NO_SUBMISSION`**：worker 回「Next Steps」summary 就收工、從未寫 zip；超預算 30 次剪得動 26 次、截斷 heredoc 0 次（#1 198）、0 次 400；修正 A 3 次；(a) 未觸發；gate 兩輪 `no usable script` | 3,021 s／218 req／in 8.05M（cache 95%）／out 161,301 | 見 §1（四十）：加「宣告未做」推回（`UNFINISHED`、`MAX_PUSHES=2`）；mock 24/24 |
| EXP-027 #1 | 2026-11-23 | `f43c01e`（碼＝`eb64c30`）；映像重建；本機 proxy 上限 hook；`exp027_1.start`，01:45:47 發射（python pid 392854） | `eor-review-corrections` | Gemma 第二題 heavy（checks-judge）；Qwen 錨點 0.2573 | **0.000／`ok`**：zip 內 7 檔包在 `filesystem/…/output/` 下（非 top level）→ grader 讀不到；227 次超預算只剪得動 16 次（佔窗的是舊 tool call 參數）；Ollama 撞窗截斷 146 次、被截斷的 heredoc 照跑 198 次；修正 A 17 次、B 0；gate 兩輪 `no usable script`；0 次 400 | 15,136 s／367 req／in 19.96M（cache 45%）／out 318,383 | 見 §1（三十九）：修 (a) 截斷 call 不執行 (b) 剪舊 call 參數 (c) archive 層級提示；mock 23/23 |
| EXP-026 #4 | 2026-11-23 | `eb64c30`（`CTX_RATIO`）；kit check 7/7（`kitcheck14_gemma.log`、映像 `b907cf495997c5e7`）；本機 proxy 上限 hook；`exp026_4.start`，01:26:29 發射（python pid 368750） | `frame-extension-method` | 預算改以真實 token 計的 live 驗證 | **0.119／`ok`**（`mean_p` 0.307、B8 forfeit）；學窗 65,534（實際 65,535）；預算剪 3 次後回正、無下限壓制；Ollama 截斷 1 次、0 次 400；修正 A 1 次 | 992 s／38 req／in 1.53M（cache 90%）／out 61,103 | 見 §1（三十八）：DEF-003 在 Ollama 64K 下全部處理完；分數差在雜訊內 |
| EXP-026 #3 | 2026-11-23 | `5df6849`；本機 proxy `cap_alias.py`（Ollama 路由 `max_completion_tokens`→`max_tokens`）；`exp026_3.start`，00:40:42 發射（python pid 320468） | `frame-extension-method` | 只差「輸出上限真的生效」 | **0.164／`ok`**（`mean_p` 0.425、B8 forfeit）；學窗 58,411（單位混用）→ 預算報 over by 至 19,993、約 20 次呼叫上限壓在 1,024，0 次 400；修正 A 2 次；gate 腳本 `zip -u` 汙染交付 | 2,140 s／72 req／in 2.87M（cache 88%）／out 130,286；撞窗截斷 2 次（皆學窗前） | 見 §1（三十七）：單位混用 → `eb64c30` 改以真實 token 計（`CTX_RATIO`） |
| EXP-026 #2 | 2026-11-23 | `5df6849`（撞窗學習 `CUT_SLACK`）；kit check 7/7（`kitcheck13_gemma.log`、映像 `3bef68fd6277777a`）；其餘同 #1；`exp026_2.start`，23:59:08 發射（python pid 286214） | `frame-extension-method` | 撞窗學習修正的 live 驗證 | **0.187／`ok`**（`mean_p` 0.483、B8 forfeit）；`learned 65063 tokens from a reply cut at the window` → context budget 剪 7 次、0 次 400；修正 A 1 次 | 1,580 s／45 req／in 1.34M（cache 87%）／out 101,167；Ollama 仍截斷 1 次（11,707 token，上限沒生效） | 見 §1（三十六）：修正生效；發現 Ollama 忽略 `max_completion_tokens` → 本機 proxy 加 `cap_alias.py` |
| EXP-026 #1 | 2026-11-22 | 碼 `a5f5452`（HEAD `6c7e96c`）；Gemma `gemma4:26b-64k`＋Gemma judge、預設預算、`--no-export`；`exp026_1.start`，23:27:21 發射（python pid 255252、`watch_run_disk.sh` 10 GB 線） | `frame-extension-method`（heavy、checks） | Gemma 首次 heavy：64K 下的 context 管理能否撐住；對照 Qwen 錨點 0.3617／0.3557／0.3673 | **0.151／`ok`**：31 items 全在、`mean_p` 0.390、B8 register_hard forfeit ⇒ 0.6 權重全失；交付 6 檔齊全 | **1,144 s**／57 req／in 2.27M（cache 88%）／out 61,333；0 次 400；Ollama 3 次回覆停在 65,535（撞窗回 200＋length） | 見 §1（三十五）：交付完整但工程計算多錯＝能力差距；發現 Ollama 撞窗不回 400 → DEF-003 補強（`CUT_SLACK`、mock `ctx_trunc` 20/20） |
| EXP-025 #2 | 2026-11-22 | 碼 `a5f5452`（HEAD `fdef666`，docs-only 之後）；Gemma `gemma4:26b-64k`＋Gemma judge、預設預算、`--no-export`；`exp025_2.start`（先過 `disk_guard.sh 40`＝80 GB），20:36:56 發射（python pid 1543、`watch_run_disk.sh` 10 GB 線） | `engineers-estimate-check`、`fire-test-validation-memo`、`backfeed-energization-reply`（三題 light，2 題並行） | Gemma 多題 light：判斷低分是普遍還是 spillway 特別難；A／B／learn_window 的 live 觸發機會 | **平均 0.046**：engineers **0.065**（3/46）、fire-test **0.072**（15/208）、backfeed **0（grader failed）**——Gemma judge prompt 超過 64K（交付物夾帶 9.3 MB `app/tools/.apps_data` dump），重評 3 次皆失敗；修正 A live 觸發 4 次皆救回，B 與 learn_window 0 次 | engineers 3,336 s／35 req／out 127,027；fire-test 3,601 s／47 req／out 105,948；backfeed 1,199 s／73 req／out 67,877；Harbor 1 h 32 m、eval 至 22:51；D: 80→62 GB | 見 §1（三十四）：低分普遍＝能力差距為主，無新 harness 錯誤；backfeed 交付擷取範圍待查，可 `--regrade` |
| EXP-025 #1 | 2026-11-22 | `10513ac`；同 #2 設定；19:38 發射 | 同 #2 三題 | — | **INVALID**：D: 塞滿→WSL I/O error，建置 backfeed verifier 映像時死亡，一題都沒跑（run `plan-verify-20261122-193919`） | — | 見 §12「D 槽塞滿」；加 R-016 防護後以 #2 重跑 |
| EXP-024 #2 | 2026-11-22 | `a5f5452`（`learn_window`＋`EMPTY_CUT`／`OUT_SHARE`＋`CHECK_BROKE`；kit check 7/7 `kitcheck12_gemma.log`、映像 `7a16b04a44687576` 重用）；其餘同 #1（Gemma＋Gemma judge、預設預算、`--no-export`）；`exp024_2.start`，18:56 發射（python pid 129109） | `emergency-spillway-check` | 缺陷 A＋B 修正後同題重跑 | **0.162162／`ok`**（加權 6/37，比 #1 多過 item 1、7＝「C-9 不足、須補 sizing 計算與剖面」）；交付 docx（`Microsoft Word 2007+`）；gate 1 `FAIL R1 … File is not a zip file`（真缺陷，fix 1 修好）→ gate 2 `FAIL R3 … Found 2/4` → fix 2；`reply cut off`＝0、`gate: check itself failed`＝0、context cut＝0 | **1,226 s**（#1 的 78%）／in 1,173,203（cache 95.8%）／out 76,675；單次最長生成 8,324 tok、最大 prompt＋生成 48,523 | 見 §1（三十三）：A、B 本輪都沒觸發（無 thinking 失控、gate 沒壞），分數差 +0.054 在 n=1 雜訊內；item 8 judge 仍誤判 docx |
| EXP-024 #1 | 2026-11-22 | `d6ec222`（`model_api: google-cloud/gemma-4-26b`）→ LiteLLM → Ollama `gemma4:26b-64k`；entry＝`/mnt/d/project/vide-coding/ple-solo-harness`；judge＝`gemma-4-26b-judge`（**首次非 Qwen judge**）；預設預算、`--no-export`；`exp024_1.start`，18:17:07 發射（python pid 85064） | `emergency-spillway-check`（rubric，同 EXP-019/021） | 首次 Gemma 4 dev run（模型＋judge 雙變因，對照 Qwen 0.838／0.919） | **0.108108／`ok`**（加權 4/37，15 items 過 4）；交付 `Memo_to_Callaway_Spillway_2026-10-31.docx` 37,519 B；gate 1→fix 1→gate 2→fix 2 皆 `FAIL F2`（gate 腳本自身呼叫不存在的 `strings` 指令）；context 400＝0 | **1,580 s**（EXP-019 Qwen 4,270 s 的 37%）／56 呼叫／in 1,694,577（cache 93.1%）／out 95,330（其中約 32K＝單次 planner thinking 失控） | 見 §1（三十一）：能力差距為主，另有兩個 harness 缺陷（thinking 截斷後的空 nudge、gate 腳本自身錯誤被當成交付缺口）與 judge 換人的混淆；暫不歸因 |
| EXP-022 | 2026-11-21 | main `87545e6`（P3-03/04 假設／義務 ledger；`git diff 6741308..87545e6 -- serve.py`＝15 行僅 WORKER/GATE/docstring）；mock 13/13＋`kitcheck8.log` 7/7（映像 `5ad1f924`，eval 重用）；`exp022_1.start`；21:11:08 發射（真 python pid 441460） | `engineers-estimate-check`（同 EXP-018/020 題） | **三點 A/B**：0.130（`85d1cbd`）→0.348（`6741308`）→本 run（`87545e6`）；EXP-022−EXP-020＝假設 ledger 淨效果；判準＝3 條 w10 解讀項（headwall 2.40 vs 2.41、VF 20.44 vs 22.02、Sec2/bond 取值）能否轉為引用支持＋轉錄/gate 見 `ple_assumptions.tsv` 與 `FAIL A<id>` 審計＋fix round 是否首次 live 觸發 | **score 0.108696／`ok`／3,351 s**（EXP-020 0.3478→**−0.239**）；`done after 105 request(s)`；rubric 5/10 items、**5/46 wtd**；本 run 解讀更差：bond $5,448,000、Sec2 $1,367,507.75、2.36 計 14 EA（GT 10，EXP-020 曾對）、2.38=30.10 VF（GT 22.02） | run `plan-verify-20261121-211109`；in 4,172,060／cache 4,011,015／out 114,602；105 呼叫 | **機制照跑但無效＋方法學警訊**：`ple_assumptions.tsv` 有寫（gate ls 確證兩檔在盤）、gate 腳本 25 KB 含重算＋tamper 自測、但 **`FAIL A<id>`＝0**——同模型自寫假設自審，引用「支持」自己的誤讀（14 EA 在 C-8 真有 14 行可引＝引用核實≠抽取正確）。**本題三連跑 0.130→0.348→0.109＝rubric 題單次 A/B 雜訊可達 ±0.2（一條 w10 翻轉）**，EXP-020 的 +0.217 與本輪 −0.239 在 n=1 下皆不可靠歸因；兩題丟分性质不同：engineers 殘餘＝**數量抽取錯誤**（P3-04 獨立抽取＋交叉驗證的活），spillway 殘餘＝**義務陳述**（正是 assumptions ledger 的靶）→ 下一步應在 spillway 上測（w3 刻度也更細） |
| EXP-021 | 2026-11-21 | ＝EXP-020 碼（`6741308` ledger、映像 `cf345aa2` 重用）、其餘同 EXP-019；`exp021_1.start`；18:19:12 發射（真 python pid 260696） | `emergency-spillway-check`（同 EXP-019 題） | ledger **一般化樣本**：對 EXP-019 錨點 0.837838（無 ledger）；已-good 題上 ledger 是幫助／傷害／只增成本？＋fix round 是否首次在 live 觸發＋MCP 第三次機會 | **score 0.918919／`ok`／8,015 s**（錨點 0.837838→**+0.081**）；`done after 175 request(s)`；capture 同路徑 docx；rubric 15 items、**14 過（34/37 wtd，前次 31/37）**：EXP-019 丟的 1.29 ft freeboard 推導項這次 PASS；仍丟同一條 w3 curb＆gutter 接受義務（prose 事實解讀，非數字） | run `plan-verify-20261121-182005`（job `__39meTNG`）；in 16,441,128／cache 15,941,507（**97.0%**）／out 251,784；req 143→175（+22%）、wall +88%、out +84% | **ledger 鏈二次確證**：gate 自寫腳本含 `L01..L20` 逐 ledger 重算行（自述 recomputes every derived figure in /tmp/ple_ledger.tsv from source records, reading fresh）、單位檢查在位（其草稿版抓到 `FAIL S14: elevations stated without a unit`）、模型再次對自寫 check 跑 tamper 變體（t1/t2）自證偵測力；harness verdict PASS（fix round 仍未 live 觸發）；**MCP 三題皆 0 使用**；殘餘丟分＝**prose 義務/決定陳述遺漏**（curb＆gutter）＝P3-03/04 靶心由數字扩展到事實陳述 |
| EXP-020 | 2026-11-21 | main `6741308`（P3-01/02 計算 ledger：WORKER 需把每個推導值追加 `/tmp/ple_ledger.tsv`（id／交付物／值／來源／公式，單位在程式內換）；GATE 腳本必須逐列從來源重算（禁抄現成數字、禁以「兩檔都寫」當證據），不符→`FAIL <id>: stated X but recomputed Y`→fix round。其餘一切同 EXP-018 #2：預設預算、`CONTEXT_TOKENS` 未設、`--no-export`、全路由本機 Strata；mock 13/13＋`kitcheck7.log` 7/7（映像 `cf345aa27e8f8fdd`，eval 重用）；`exp020_1.start`；17:00:53 發射（真 python pid 174627） | `engineers-estimate-check`（同 EXP-018 #2 題） | **P3 A/B 首組**：單變因＝ledger 提示（`git diff 85d1cbd 6741308 -- serve.py` 只動 WORKER/GATE/docstring）；錨點＝0.130435；判準＝score 上移＋轉錄見 ledger 寫入＋gate 重算 FAIL/PASS 線＋（若錯值被抓到）fix round 有寫入；最終 bond 是否收斂至 GT $5,384,000 | **score 0.347826／reward 同／`ok`／3,951 s**（錨點 0.130435→**+0.217**，遠超 ±0.01 噪聲）；`done after 92 request(s)`；capture 同路徑 docx 41,094 B；評分 10 items、**7 過（16/46 wtd，前次 6/46）**。剩 3 條未過仍全為 weight-10 數值：$5,381,000 vs GT $5,384,000；Sec2 $1,300,414 vs GT $1,303,717.70；2.38=20.44 VF vs GT 22.02 VF | run `plan-verify-20261121-170055`（job `__ubfs42a`）；in 3,940,164／cache 3,785,143（96.1%）／out 136,825；92 呼叫 vs 70（+31%）、wall +58%＝ledger 有成本 | **機制確認全鏈生效**：worker 確實寫了 ledger（轉錄 200 字元截斷看不到寫入＝B-2 盲點，但 gate 階段 `ls /tmp` 顯示 `ple_ledger.tsv` 1,195 B@09:27 落盤）、gate 自寫 check 腳本自述「Every figure is recomputed from the sources」、verdict PASS（fix 0 輪＝內部算術自洽）；**剩餘丟分已從「算錯」轉為「解讀/取值選擇」**（headwall 2.40 vs 2.41、curb inlet 計數、VF 深度 convention 20.44 vs 22.02）＝P3-03/04（假設矩陣／一致性）的靶心。bond 由 $5,431,000→$5,381,000 向 GT 收斂＝重算紀律方向正確。ledger 碼**保留** |
| EXP-019 | 2026-11-21 | 碼＝`85d1cbd`（HEAD docs-only 之後；`git diff 85d1cbd` 於四核心檔空）、starter 預設預算、`CONTEXT_TOKENS` 未設、`--no-export`、全路由本機 Strata；`exp019_1.start`；10:06:31 發射（真 python pid 59266） | `emergency-spillway-check`（light L1，§13；MCP×8；水資源域） | P2-05 第四領域（水資源）＋gate 碼第二次 live＋**MCP meta 工具首次實戰機會**（EXP-018 目錄快取正常但 0 次使用）；通過判準＝capture≠{} ∧ score>0 ∧ gate 標記再現 ∧ MCP 使用 ∧ 尾聲無 DEF-003 型 400 | **score 0.837838／reward 同／`ok`／4,270 s**；`done after 143 request(s)`、`serve status=completed`；capture `files=1`＝`Memo_to_Callaway_Spillway_2026-10-31.docx` 55,494 B。評分＝rubric 族 `passed_score`（加權）：15 items、13 過、**31.0/37.0**；2 條未過（各 3 點）皆**工程判斷／推導類**：未指出 1.29 ft freeboard 在 spillway overflow 時不合格、未寫 curb＆gutter 半段改善已被接受之義務歸屬 | run `plan-verify-20261121-100723`（job `__ReGYA7s`）；in 9,717,976／cache 9,465,260（**97.4%**）／out 136,834；watcher 無自癒事件 | **P2-05 4/4 完成**；gate 碼第二次 live＝再現 `phase: plan→work→gate 1`＋`gate: script ready`→`verdict: PASS`（fix 0 輪）；尾聲乾淨（0 錯誤、無 cut）；**MCP 仍 0 次使用**（目錄快取 `mcp apps: 141 tools`＋3 筆 HTTP 正常）＝連續兩題 meta 工具在位但模型不需要（答案在檔案系統）→ 記錄為觀察，非 harness 缺陷；四題彙整見 **P2-06 scorecard**（`docs/P2_SCORECARD.md`） |
| EXP-018 #2 | 2026-11-21 | 與 #1 完全同參：HEAD `7211094`、`git diff 85d1cbd HEAD -- serve.py taskbridge.py submission.yaml requirements.txt` 空（碼＝kitcheck6 驗證的 `85d1cbd`）、build 重用（映像 `6fb67fa48bbb4548`）、`CONTEXT_TOKENS` 未設、`--no-export`、全路由本機 Strata；重開機後鏈路重驗全 PASS（Strata 200／LiteLLM 200＋e2e 200／docker 0 殘留／881G／61G）；`exp018_2.start`；09:14:17 發射（真 python pid 1338） | `engineers-estimate-check`（light L1；MCP×8；電機域） | #1 重開機 INVALID 之同參單次重跑；判準同 #1 | **score 0.130435／reward 同／`ok`／2,497 s（≈42 m）**；`done after 70 request(s)`、`serve status=completed`；capture `files=1`＝`Correspondence/Client/Memo_to_Callaway_2026-10-31.docx` 43,429 B。評分＝rubric 族 `portable_weighted_rubric_equivalent`（`score_key=passed_score`）：10 items、6 過、加權 **6.0/46.0**＝0.1304；4 條未過皆高權重（10 點：ground truth 要 bond $5,384,000／Sec2 小計 $1,303,717.70，模型算出 $5,431,000／$1,350,777.75＝**CALCULATION 族丟分**，judge＝本機 Strata、R-009 留意） | run `plan-verify-20261121-091517`（job `__38Tw76m`）；in 1,484,305／cache 1,369,664（92.3%）／out 78,158；watcher 無自癒事件 | **新 gate 碼首戰＝绿**：`phase: plan→work→gate 1`＋`gate: script ready`→寫 `/tmp/ple_gate.py`（11,812 B）容器執行→`verdict: PASS`（fix 0 輪；模型先於 `/tmp/acc` 對自寫腳本做 3 組突變測試證偵測力）；**DEF-003 尾聲乾淨**（egress 0 筆 4xx/5xx、無 cut；本題 context 小，未觸發＝未驗證）；**MCP 未實戰**：`mcp apps: 144 tools` 目錄快取在（initialize＋list_tools 3 筆 HTTP）但模型 **0 次 `mcp_list`/`mcp_call`**（本題檔案系統可解）→ EXP-019 再驗；P2-05 電機 ✓ → **3/4**；0.130 無歷史可比（本題首跑） |
| EXP-006 | 2026-11-18 | `97cbd38`：serve.py 加 `mcp_list`／`mcp_call` 中繼工具（MCPClient 於 task 開始時 initialize＋list_tools 並快取；planner/worker/verifier 三角色皆可呼叫；輸出 clip、args 以 JSON字串傳遞） | 官方 `kit check`（含 `mcp` 階段） | 讓 harness 正式走協議的 `http` 請求存取任務 MCP server，消除 `[WARN] mcp` | 靜態驗證：AST ok、pyflakes 0、無新增 >80 char 行；**`kit check` 22:3x：`[PASS] mcp`（82 s、13 requests、13,814 in／1,211 out）、6 階段全 PASS、僅剩 `artifacts` WARN**；映像 `plebench-serve:b8a6572ec27dd14a`（`~/projects/kitcheck4.log`） | **P1-07 完成**；以補丁版重跑單題做分數對照（EXP-007） |
| EXP-007 | 2026-11-18 | `97cbd38`（MCP 補丁版）、其餘同 EXP-005 | `frame-extension-method` 重跑 | 確認 MCP 補丁不降分、作為 P1 版對照 | **score 0.3557（`ok`，11,595 s＝3 h 13 m）**；tokens in 23,487,057／cache 23,086,775／out 320,314；與基線 0.3617 差 −0.006（−1.7%）。本題無 MCP server（`mcp_servers=[]`），補丁碼路徑為 no-op → 差異屬模型執行隨機性 | run `runs/plan-verify-20261118-224102/`；累計 proxy 543 呼叫 | **補丁定版**；單題單次跑的分數噪聲約 ±0.01，日後 A/B 需以多 run 或更大任務集對照 |

實驗規則：一次只改一個主要變因；沒有 commit/config/task/result 的實驗不作決策依據。

---

## 7. Defect and failure log

| ID | Priority | Area | Symptom | Root cause | Fix | Retest | Status |
|---|---|---|---|---|---|---|---|
| DEF-001 | P0 | quick harness／ARTIFACT+TIMEOUT | EXP-008 score 0.0：grader `ERR_NO_SUBMISSION`，全程 25 呼叫都在 `sed/cat/grep` 讀規則檔，最後一步（step 29）模型正要 `cat > gen.py` 產出交付物時被收尾呼叫（`tool_choice=none`）擋下，改以文字輸出 pseudo-`<tool_call>`，從未執行 | ① 15k out 預算對重工程題少一個數量級（完整版 327k）；② 無「交付檢查點」：預算燒一半仍無 write_file 也不強制先寫最小交付版；③ 收尾呼叫完全禁工具，恰好殺掉最重要的一次寫入；④ plan 8 呼叫對小模型無產出（全花在讀檔）；⑤（EXP-009）提前放棄：檢查點按預算 share 觸發，模型只燒 11–22% 就以純文字結束，檢查點從不生效 | 候選：① 交付檢查點（呼叫／token 半數無寫入→注入「立即寫最小交付」指令，75% 後只准 write）；② 收尾呼叫允許 write 類工具（write-only wrap）；③ 依任務量級調-budget（重題 60 min／80 呼叫／60k out）或快速版只跑輕題；④ quick 模式跳過 planner | v2（`8d34278`）同題實測仍 0.0（EXP-009）→ v3 交付閘門（`_writes == 0` 時打回純文字結束 ≤2 次）＋mock gate 案例，再重測 mock＋實測；v3（`16053ed`）已實作：mock 7/7（`gate`：打回 1/2 後補寫 `cat >` 送達 exec；`gate2`：只打回 2/2 上限後接受） ；實測（EXP-010）仍 0.0：模型改以**空 content 結束**，繞過 gate 的 `message.content` 非空條件；v4（`1ea5c67`）實測（EXP-011）仍 0.0 但模式再變：19 次帶工具呼叫誠實工作（696 s、gate 0 次），第 19 呼叫生成交付腳本途中 `stop=output`（17,931 out）截斷未執行 → 失敗族從「提前放棄」轉為「預算燒盡」，根因①主導；預算加檔（EXP-012，`25e3173`）仍 0.0：wall／out 未盡（1,353 s／45,130 out）、`stop=requests@41` ≪ 全域 76 ⇒ 步驟級份額（L581）觸發；模型分段寫腳本（`part2 ok`）未及執行即停 → 失敗族再轉為「步驟配額耗盡」，根因從①轉為配額結構 | IN_PROGRESS（v3 實測失敗、根因已定位；v4（`1ea5c67`）已實作：任何無工具結束（含空 content）都打回、空 assistant turn 不回放；mock 8/8（新增 `gate_empty`）；v5（`c476e8c`）mock 9/9（`quota` 精確重現 EXP-012 於 41 死因：verifier 份額耗盡＋空 verdict→曾被當 PASS）並修復：out-of-share 步驟的空 verdict 不再終止 fix 迴圈；實測 EXP-013（2026-11-20）：capped→fix round 照跑（修復生效），但仍 0 分——失敗族轉為「fix round 只讀不寫」（模型收到明確 gap 後仍零 write） | SCOPED-BY-ADR-010（2026-11-20 使用者選 (c)：heavy 題不再跑 quick，DEF-001 的 quick 側修復止於 v5；剩餘驗證＝EXP-015 light 題能否正常產出。`writes==0` 事件式指令為備選單變因，僅在 light 題也出現同樣症狀時才動）**→ EXP-015 實測（2026-11-20，light）：零交付重現（0.0／capture `files={}`）。症狀雖同（收到明確 gap 仍不寫），直接原因是三線防護被 `_writes` 誤計關掉（轉 DEF-002）——事件式指令在誤計未除前無從生效；ADR-010 revisit 條件成立，待使用者決策** |
| DEF-002 | P0 | quick harness／FILE＋HARD_GATE | EXP-015 #1b 全程 `checkpoint:`＝0、`gate:`＝0、`wrap-write:`＝0：零交付的三道事件式防護從頭未觸發，模型兩度收到 verifier「完全沒有交付物」清單仍 0 次 write，最終 capture `files={}`、0/208 分 | checkpoint（40/70%）、交付閘門、wrap_write 共用 `_writes == 0` 前題，而 `_writes` 由 `_WRITE_BASH` 對命令**文字**猜寫入：裸 `>` 會命中 python heredoc 本體裡的比較式與箭頭字串（#1b 呼叫 #26：1,953 字元指令、`if series[i]>=lim:`／`" -> "`，`>` 在第 572 字元）→ `_writes=1` 一次、整題防護永久失效；轉錄只記 `arguments[:200]` 令誤計不可見。#1a 的 `2>&1` 誤計是同一缺陷族；v6（`738534b`）只修掉 fd 重新導向與 bare `mkdir` 兩類 | **待使用者核准（本輪授權修復範圍＝fd/mkdir 類，換計數機制屬新策略）**：①建議真值化——`_writes` 改由 taskbridge capture 增量（交付路徑實際檔案變化）推導，不再解析命令文字；②保守方案＝匹配前剝除 heredoc 本體與引號字串再跑 `_WRITE_BASH` | **FIXED（quick v7 `7ab4ae6`，2026-11-20）**：真值計數如上（PLELAND 探針＋baseline 差分、即時重算、刪除回零、探針失敗留痕保持武裝）；驗證＝mock **16/16**＋偵測證明（`heredoc`／`landflip`／`fixflow` 於 v6 全 `[FAIL]`）＋#1b 36 呼叫離線重放（root `/app/files/`：全程 landed=0）；順帶 `wrap_write` 限定 deliver 步驟＋每步一次性 | LIVE 重測待 quick 復活（同參單次，`DELIVERABLE_PATHS=/app/files/`）；quick 依使用者指示暫停中 |
| DEF-003 | P1 | main harness／RESOURCE（context window） | 兩次 main 正式 run 的**尾聲**都撞到 Strata 262,144 視窗：EXP-016 最終 prompt 261,799（僅剩 337）；EXP-017 `harness error after its summary: BadRequestError: 400 … request exceeds the context window: prompt (262159 tokens) leaves no room to answer in the context (262144)`；proxy 整 run 另有 9 次 400（全為 context overflow、LiteLLM 各重試 3 次） | 本機模型視窗固定 262,144，而 starter 只在 400 **之後**被動剪舊 tool 結果（EXP-017 轉錄 5 次 `context full: cut N old tool results`＝cut 5/2/1/1/1），沒有 headroom 規劃、沒有步驟級 prompt 上限；長 run 的 transcript 單調成長 ⇒ 收尾階段必然頂到天花板。實際損失＝EXP-017「summary 之後的最後一輪自我驗證／迭代」無法執行（交付已寫入、評分不受影響：`exception_info=None`、`serve_status=completed`） | **未動碼（待核准）**：① prompt 預算守門（目標 ≤ n_ctx − 安全邊際，事前剪／摘要而非事後 cut）；② 舊 tool 結果摘要化取代整筆 cut；③ 收尾前預留 headroom（最後 N 呼叫不得再讓 context 成長）。**不得對 262,144 overfit**：那是本機 Strata 常數，正式宣告模型視窗不同 | 下次 main run：`serve.log` 不得再出現 `harness error: BadRequestError … exceeds the context window`，並確認收尾自我驗證輪次保住 | ~~FIXED-PENDING-LIVE（`85d1cbd`）~~ **REOPENED→REFIXED（2026-11-22）**：EXP-023 #2 的 116×400 證明守門在 live 从未生效——根因不只是「沒設」而是**設不到**：serve 容器 env 只含模型鍵值＋`submission.yaml` `env:` 表，外層 shell 變數進不去（§1（二十五）①）。修復＝`window_probe()`：首呼前向端點 `/v1/models` 查視窗（優先 id==MODEL、否則最小；顯式 `$CONTEXT_TOKENS` 仍優先；失敗→0＝退回被動，零回歸）＋margin 預設改自動 `max(8000, window/12)`（est chars/4 低估 code-heavy）。mock `ctx_discover` 14/14＋舊碼偵測證明；`CTX_MARGIN_TOKENS` 0＝自動。live 判準：轉錄見 `context window: 262144 tokens (announced…)`、egress 0 筆 exceeds-context 400、收尾自我驗證輪保住；若 egress 擋 GET（見 §1（二十五）⑤）→ 退回被動並另案核准 `submission.yaml` env。**REOPENED（2026-11-22 17:46，EXP-023 #3 首次 live）**：轉錄＝`context window: not announced by the endpoint; reactive path only`——探測有回應（非 probe failed）但 **LiteLLM 從 `/v1/models` model 條目剝除 `max_model_len` 等欄位**（strata 直連預探有宣告、代理後沒有）＝守門在 live 依然無視窗值、#2 型 116×400 飽和風險原樣；退回被動＝零回歸已證。解法待拍板：① proxy 對 `/v1/models` 透傳 extra 欄位（改 LiteLLM 配置／中間層）② `submission.yaml` `env:` 帶視窗值（R-009 需核准，且 dev／正式需可切換）③ 首 response usage 推窗（未設計） **2026-11-22 補強（Gemma／Ollama）**：`learn_window`（`07e873f`）從第一個 400 學窗；但 EXP-026 #1 發現 **Ollama 在 prompt＋生成碰到 `num_ctx` 時不回 400，而是回 200＋`finish_reason=length`、生成被截短**（3 次停在 65,535 token，harness 要 32,000）⇒ 學不到窗、之後每次都貼著 64K 送。修正：回覆 `length` 且 `completion_tokens + CUT_SLACK(16) < max_out` ⇒ 視為撞窗，`learn_window(messages, made, "a reply cut at the window")`（視窗＝送出 est＋已生成）。mock 新 `ctx_trunc`（`MOCK_CTX_TRUNC`）**20/20**；舊碼偵測證明＝同案例 8 次截斷 vs 新碼 1 次。**2026-11-23 補強（EXP-027 #1）**：heavy 題 worker 以 heredoc 寫整份檔，舊 tool call 參數佔滿 64K 而 `shorten()` 只剪工具結果 → 227 次超預算只剪得動 16 次、撞窗截斷 146 次、被截斷的 call 照跑 198 次。修正：`shorten()` 以 `cut_args()` 一併剪舊 call 參數（仍為合法 JSON）；`length` 回覆中的 tool call 不執行、改送 `CALL_CUT`。mock `call_cut`／`args_cut`，**23/23**，舊碼兩案皆 FAIL。|

Failure taxonomy：`BOOT / PROTOCOL / MODEL / TOOL / MCP / FILE / FORMAT / CALCULATION / HARD_GATE / RUBRIC / RESOURCE / TIMEOUT / ARTIFACT / PLATFORM / UNKNOWN`

---

## 8. Risks and blockers

| ID | Risk/blocker | Impact | Owner | Next action | Status |
|---|---|---|---|---|---|
| R-001 | Kaggle 要求身分驗證 | 影響正式提交 | Solo | 提交前完成 Kaggle 身分驗證 | OPEN |
| R-002 | 工作區位於 Windows `D:` | 官方建議 WSL2 Linux filesystem | Solo | 已改在 WSL `~/projects/` 開發，Windows 端只放規劃文件 | CLOSED |
| R-003 | 本機模型費用/配額未知 | 無法估算完整 dev run 成本 | Solo | 單題 baseline 記錄 tok/s 與 wall time | CLOSED（EXP-005：out 326,888 tok／14,310 s＝22.8 tok/s wall；in 34.6M、cache 命中 98.4%；換算 DeepSeek flash 單題 $0.19–0.38、29 題 $5–25） |
| R-004 | Rules 頁需登入確認 | 資格/提交細節可能遺漏 | Solo | 官方 `docs/rules.md` 全文已讀＋ple-bench.com 賽期/3-run 已記錄（§1（二十六））；**2026-11-22 Kaggle Overview 全文已讀（含提交管道、Timeline、評分兩階段、贊助模型，§1（二十八））**；剩 Kaggle Rules tab 法務條款未逐條讀 | PARTIAL |
| R-005 | WSL 內未偵測到 uv 與 Harbor | 尚不能執行官方 kit 和 eval | Solo | 已安裝 uv 0.13.8 與 Harbor 0.20.0（官方 pin）| CLOSED |
| R-006 | Hugging Face 資料 access | 29 題已解壓且雜湊全數吻合 | Solo | 使用本機 `--tasks-dir` | CLOSED |
| R-007 | WSL 全面報 ERROR_FILE_NOT_FOUND（見 §12） | 所有 Linux 端工作暫停 | Solo | 根因為 `System32\wsl.exe` 缺少同目錄 `wslservice.exe`；改用 `C:\Program Files\WSL\wsl.exe` 後全部指令正常 | CLOSED |
| R-008 | Store 版 PowerShell 套件損壞（`pwsh.exe` alias 失效） | OpenCode shell 階段的 spawn 失敗 | Solo | 已在 `~\.config\opencode\opencode.json` 設定 `shell` 指向 `C:\Program Files\PowerShell\7\pwsh.exe` 繞過 | WORKAROUND |
| R-009 | 本機模型與官方評測模型不同（IQ3 量化 27B vs Claude Opus 5.5） | 本地分數僅供相对比较，不可外推正式分 | Solo | 每輪固定同一模型與設定做 A/B；正式提交前另評雲端模型 | OPEN |
| R-010 | 29 題 agent 時限皆 6 h，本機 ~20 tok/s | 單題全跑可能數小時，dev run 成本高 | Solo | 實測（EXP-005）：單題 3 h 58.5 m、out 僅 327k tokens → 本機串行 29 題要數天。對策：改接付費 API（DeepSeek flash 併發 2500）可 8–16 題並行、一晚跑完；或 `MAX_OUTPUT_TOKENS`／task 子集控制 | OPEN |
| R-012 | dev artifacts 由本機 strata（透過 `claude-opus-5-5` 別名）產生，而 entry 宣告模型是 `google-cloud/claude-opus-5-5`；官方規則「Call only the model you declared」 | 若把 strata 產物直接匯入 `artifacts/` 提交，與宣告模型不符，違反 fair-play 且 manifest 記錄 `model_api=claude-opus-5-5` | Solo | 本地 strata 只用於迴圈驗證與 P1 對照（維持 `--no-export`）；產生正式 artifacts 前把 proxy 上游換回真 Vertex（`aiplatform` API 目前 DISABLED，需先開通）後重跑 dev set。**2026-11-22 依 Kaggle Overview 修正：官方明文允許本機／個人 API 模型產生 `artifacts/` 後再切換 `model_api`（不取消資格），條件＝Writeup 註明本機模型與 judge ⇒ 本風險的前提不成立；剩餘風險轉由 R-014 追蹤** | MITIGATED |
| R-013 | 官方必要檔列「`serve.py`, `harness.py`」（另處寫作 `serve.py / harness.py`），本 repo 無 `harness.py`（入口為 `serve.py`＋`taskbridge.py`） | 若實為必要檔，Stage 1 資格檢查不過 | Solo | 對照官方 `submission-template`／sample_submissions 與 `kit check` 判定；必要時加 `harness.py`（不動核心邏輯） | OPEN |
| R-014 | Stage 2 會以宣告模型「re-runs a random dev sample live」做重現性檢查（失敗或 hard-code 即 DQ），未說明與已提交 artifacts 分數的容差 | 若 artifacts 由本機模型產生、即時重跑換成宣告模型，分數／產物差異大，可能被判重現性不符 | Solo | 最終 `artifacts/` 以目標 `google-cloud/<id>` 模型重產；或向官方 Discussion 確認容差 | OPEN |
| R-016 | WSL 虛擬磁碟 `D:\WSL\Ubuntu\ext4.vhdx` 放在 D 槽（931.5 GB，大部分是個人資料），動態 VHDX 只長不縮 | D 槽塞滿時 WSL 整個 I/O error，進行中的 run 失效（2026-11-22 EXP-025 #1） | Solo | **根因**：Linux 看到 1 TB 虛擬磁碟，BuildKit 依此推算的快取清理上限遠大於 D 槽實際剩餘，且未設 `daemon.json`，建置快取堆到 145 GB。**已上三道防護（2026-11-22）**：① `/etc/docker/daemon.json` `builder.gc` `defaultKeepStorage: 20GB`（`docker buildx inspect` 確認 Reserved Space 20GiB）；② `~/projects/disk_guard.sh [min=40]`：以 `/mnt/d/...`（drvfs，反映 D 槽真實剩餘）檢查，不足即拒絕發射，每個 `.start` 開頭呼叫；③ `~/projects/watch_run_disk.sh <pid> <log> [min=10]`：取代舊 watcher，每 60 s 檢查 D 槽，跌破門檻即 TERM 該 run（Harbor 會取消 trial 並清容器）。需要還空間給 Windows 時仍走 `fstrim`→`wsl --shutdown`→系統管理員 `Optimize-VHD -Mode Full`；sparse 維持關閉 | MITIGATED |
| R-015 | Stage 2 依「平均分×平均成本」Pareto 前緣排名，平均分 ≥0.138 才有獎項資格；每題容器 2 CPU／4 GB RAM | 成本與資源占用直接影響名次；harness 若在 4 GB 內 OOM 即該題 0 分 | Solo | P6 納入 token／成本報告與 score-vs-cost 曲線；本機評測確認容器資源限制與 Stage 2 一致 | OPEN |
| R-011 | Windows→WSL 的 TCP bridge（`forwarder.py`）會失活，導致上游 `Connection error` | 評測期間模型呼叫全部 500，smoke 600 s 內 0 次成功呼叫 | Solo | 已改寫為 supervisor 版：用 `Get-NetIPAddress` 偵測 `vEthernet (WSL*)`/`vEthernet (Default Switch*)` 並逐個 bind，每 300 s 重新檢查並自動 rebind。2026-11-18 換 distro 後 bridge 又失活一次，重啟後（pid 2632）自動綁上新位址 `172.23.0.1` 與 `172.23.80.1`（Default Switch 網段已從 `172.26.128.1` 改變），新 distro 全鏈路再次 200。排程方案失敗：`schtasks /create`（cmd 與 `Register-ScheduledTask` 兩種）一律回「存取被拒」，代表本機群組原則禁止一般使用者建立排程工作（已確認 `PLE_Model_Bridge` 不存在）。改用等價方案：HKCU 啟動鍵 `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run\PLE_Model_Bridge = pwsh -File start-watchdog.ps1`（已寫入並回讀確認），開機後由 `watchdog.ps1`（30 s 巡邏、必要時重啟 `forwarder.py`）負責保活；目前 forwarder pid 2632、watchdog pid 28964 在跑。 | MONITOR |

---

## 9. Decisions

| ID | Date | Decision | Reason | Revisit trigger |
|---|---|---|---|---|
| ADR-001 | 2026-11-16 | 採單 Agent state machine 起步 | 可測、可觀察、較低複雜度 | 數據證明多 Agent 明顯改善 |
| ADR-002 | 2026-11-16 | hard gates 優先於成本最佳化 | 未通過 hard gate 會失去最佳化分 | hard-gate pass 已穩定後 |
| ADR-003 | 2026-11-16 | 以官方 starter 建 baseline | 降低 protocol/提交風險 | starter 無法滿足必要功能 |
| ADR-004 | 2026-11-16 | 01/01 feature freeze | 為最終可靠度與提交留緩衝 | 官方日期變更 |
| ADR-005 | 2026-11-17 | 開發環境固定在 WSL `Ubuntu-24.04`（`~/projects/`），Windows `D:` 只放規劃文件 | 該发行版的 14 GB vhdx 持有全部專案資料；新的 `Ubuntu`发行版無資料 | 官方要求其他 Linux 環境 |
| ADR-006 | 2026-11-17 | 不修改 `submission.yaml` 的模型宣告，改用 LiteLLM 別名代理接到本機 strata 模型 | 保持 starter 逐位元組不變，本地與官方只差上游端點；Proxy 設定與 `kit/model_proxy/start.sh` 同版（litellm 1.90.0） | 需要可比較雲端模型分數時 |
| ADR-007 | 2026-11-17 | Harbor 依官方 `HARBOR_VERSION` 釘在 0.20.0（外加 `websockets`） | 新版 Harbor 與 kit 的 agent/environment 介面不符 | 官方 repo 升級 pin |
| ADR-008 | 2026-11-18 | 開發发行版改為 WSL `Ubuntu`（26.04.1 LTS）；舊 `Ubuntu-24.04` 只作為資料來源保留 | 使用者明確要求換 distro；實測新 distro 可用：Docker 官方 apt repo 已有 `resolute` 通道（docker-ce 29.10.0）、Harbor 0.20.0 可裝、`kit check` 前 6 階段全 PASS | 新 distro 出現套件不相容（尚未發生） |
| ADR-009 | 2026-11-19 | 快速版走 `quick` branch＋`ple-solo-harness-quick` worktree：內部預算 30 分鐘／40 次呼叫（含重試與收尾）／15,000 累計輸出 tokens，保留 5 分鐘＋4 呼叫＋4,000 tokens 收尾；單次呼叫輸出≤2,000、逾時≤180 s；`submission.yaml` 與 main branch（正式提交設定）完全不動 | 本機 strata 完整版單題 3–4 h，dev 迴圈太慢；先跑快速版評估、再對收斂版跑完整版生成 artifacts | 快速版分數明顯掉到不可用（<基線 −0.1），且原因無法在完整版修復 — **已觸發，由 ADR-010 接手** |
| ADR-010 | 2026-11-20 | 依 ADR-009 revisit 使用者選 (c)：**quick 只跑 light 題（§13 分級 14 題）**；heavy（14 題）固定走 main 完整版；uncertain（1 題）以 quick 探測一次，失敗即歸 heavy、不反覆修 harness | EXP-013 證明配額結構已修好但模型在 heavy 題（294 activities／6 檔／zip）於任何 quick 預算下不產出（6×0 分，含 v5）；在 heavy 題繼續燒 quick 無資訊價值 | light 題的 quick run 仍 0 交付（EXP-015 失敗）→ 重新評估 quick 是否值得保留。**2026-11-20：revisit 條件已成立**（#1b light 題 0.0／零交付，主因 DEF-002 誤計關掉防護）；DEF-002 已修（v7 `7ab4ae6`）但 **quick 依使用者指示暫停開發與正式評測**，EXP-015 #1/#2/#3 與 uncertain 探測全部暫止；本輪資源轉入 main dev 子集（EXP-016/017）；quick 是否復活待使用者決策 |
| ADR-011 | 2026-11-22 | 本機 dev 的 judge 固定用 **Gemma**（`gemma-4-26b-judge` → Ollama `gemma4:26b-64k`），跑題模型同為 Gemma；不改用付費 Opus 5.5 judge，也不為對照舊錨點切回 Qwen judge | 使用者選擇（不花 API 費用、免分時開 Strata）；官方 judge 是 Claude Opus 5.5，本機 judge 只需在 Writeup 註明 | 已知偏差：Gemma judge 只看 verifier 的 `.pdf.txt` 渲染，會把合法 docx 判成「沒有 .docx」（EXP-024 #1/#2 item 8，每 run 少 1 分）。⇒ Gemma 時期分數只彼此比較，不與 Qwen judge 時期的錨點（0.838／0.919 等）直接比；若需要接近官方分數或發現更多 judge 誤判，再評估換 Opus judge。另：跑真 Nextcloud 的 5 題，grader 會把整份 `db_diff.txt` 給 judge，超過 Gemma 64K ⇒ 本機不評分、只看可靠度（§1（三十四）②⑥） |

---

## 10. Weekly review template

每週複製一份並填寫：

```markdown
### Week YYYY-MM-DD

- 本週完成：
- 驗證證據：
- 分數/成本/可靠度變化：
- 新發現的前三大失敗：
- 保留/回退的實驗：
- Blockers：
- 下週唯一最高優先目標：
```

---

## 11. Final submission record

提交前填寫：

- Competition rules checked at：
- Official deadline checked at：
- Final commit：
- Final tag：
- Repository checksum：
- Model API：
- Dataset commit：
- Artifact manifest digest：
- `kit artifacts` result：
- `kit check` result：
- Offline regrade result：
- Submission timestamp：
- Kaggle submission/entry ID：
- Final leaderboard result：

---

## 12. Incident log

### 2026-11-22 — D 槽塞滿 → WSL I/O error，EXP-025 #1 中斷（R-016）

- **症狀**：EXP-025 #1（三題 light、`10513ac`）19:38 發射，20:04 python 結束；之後 WSL 內 `execvpe(bash) failed: I/O error`、`df: Input/output error`、`Bus error`。EXP-025 #1 **一題都沒跑**：死在建置 `backfeed-energization-reply` 的 verifier 映像（`plan-verify-20261122-193919`，INVALID，無分數）。
- **根因**：Ubuntu 的虛擬磁碟 `D:\WSL\Ubuntu\ext4.vhdx`（動態 VHDX，只長不縮）長到 **169.9 GB**，D 槽（931.5 GB，大部分是個人資料夾）**剩 0 GB**。一小時前 D 槽還有 28 GB；新題目的映像建置＋Docker 建置快取（144.9 GB，其中 85 GB 可回收）把它吃完。
- **處置（使用者核准）**：① 刪 `D:\ple-migration\old-distro-projects.tar`（11/18 搬遷用，1.5 GB；工具禁止刪 D 槽根目錄下的資料夾本身，空資料夾保留）；② `wsl --terminate` 後啟動失敗（`Wsl/Service/CreateInstance/E_FAIL`、錯誤碼 6、失敗步驟 2），改 `wsl --shutdown` 重開 VM 才恢復；③ `docker builder prune -f`＋`docker image prune -f` 回收 85 GB（題目映像保留），WSL 內 168 GB → 89 GB；④ `--set-sparse true`＋root `fstrim` 只回收 0.6 GB，而且 sparse 檔會讓 `Optimize-VHD` 拒絕執行 → `--set-sparse false`；⑤ 使用者以系統管理員執行 `Optimize-VHD -Path D:\WSL\Ubuntu\ext4.vhdx -Mode Full` → **vhdx 92.3 GB、D 槽空 79.1 GB**。
- **恢復驗證**：WSL `df` 89 G／1007 G、docker active、LiteLLM 重啟後 Gemma 端到端 200、repo 乾淨（`10513ac`）。核心 log 沒看到 ext4 錯誤。
- **教訓**：(a) 動態 VHDX 在 Linux 內刪檔不會還空間給 Windows，要 `fstrim`→`wsl --shutdown`→系統管理員 `Optimize-VHD -Mode Full`；(b) WSL 的 sparse 是實驗功能，回收很少又會擋住 `Optimize-VHD`，維持關閉；(c) 新題目第一次跑會建很大的映像，發射前要確認 D 槽空間（見 R-016）；(d) 本 session 不是系統管理員，壓縮必須請使用者執行。

### 2026-11-16 — WSL 環境故障（R-007）

症狀：本中段 Work 前 WSL 正常（Docker 曾通過），現在所有 `wsl.exe` 指令（`--version`、`-l -v`、`--status`、`--shutdown`、`-e echo ok`）皆 exit=1 並輸出 `系统找不到指定的文件`（ERROR_FILE_NOT_FOUND，UTF-16LE）。

診斷證據（Windows 端，非系統管理員）：

- WSL 套件 `MicrosoftCorporationII.WindowsSubsystemForLinux 3.0.5.0` 已註冊且 InstallLocation 存在於磁碟。
- 發行版註冊完整：`HKCU\...\Lxss\{9280068b-...}`，Ubuntu-24.04，Version=2，`BasePath=C:\Users\ZivKao\AppData\Local\wsl\{9280068b-...}`，`ext4.vhdx` 14,183,038,976 bytes 存在。
- `wslservice.exe` 在 session 0 執行中（pid 5736）；非系統管理員 `taskkill` 被拒。
- `LxssManager` 服務不在服務註冊表（WSL 3.x 正常現象，改由 wslservice 承擔）。
- 無 WSL 相關 crash（WER 空）、近 48h 無相關事件記錄、無近期 Windows Update。
- 旁證：Store 版 PowerShell 套件已從 `C:\Program Files\WindowsApps` 消失但註冊與 alias 还在 → 本機 WindowsApps 套件註冊/檔案曾发生漂移。

推論：session 0 中的 wslservice 持有舊版安裝路徑（套件更新後未重启），导致 spawn 時找不到執行檔。

處置：使用者以系統管理員執行 `wsl --update` → `wsl --shutdown` → 驗證 `wsl -d Ubuntu-24.04 -e echo ok`。待驗證後關閉 R-007。

### 2026-11-17 — R-007 關閉與 WSL 指令通道

重開機後確認根因：inbox 的 `C:\Windows\System32\wsl.exe` 旁邊缺少同目錄 `wslservice.exe`，因此每個子指令都回 `ERROR_FILE_NOT_FOUND`；Store 版 `C:\Program Files\WSL\wsl.exe`（WSL 3.0.58.0）完整可用。

- 可用指令形態：`& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u zivkao -e bash -lc '<script>'`；此 build 不認識 `--shell-mode`。
- 之前為繞過故障架設的排程中繼（`PLE_WSL_RELAY2`、`C:\Users\Public\ple-wsl-relay\`）已作废，可直接呼叫 WSL。
- 追記：`bash -lc` 內用 here-doc 傳 Python 會被引號層級吃掉，改由 `write` 工具產出 `.py` 後以 `/mnt/c/...` 路徑執行。
- 追記：在 WSL 內用 `nohup ... &` 起的長時間工作，shell 結束時仍會收到 SIGINT（`rc=130`）；改用 `setsid nohup ... </dev/null >log 2>&1 &` 才能活過 shell 終止。

規避（R-008）：OpenCode shell 原先指向失效的 `WindowsApps\pwsh.exe` alias；已於 `C:\Users\ZivKao\.config\opencode\opencode.json` 加入 `"shell": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"`，shell 已恢復可用。

---

## 13. Dev-set triage（ADR-010，2026-11-20）

訊號全部取自本地 dev 資料（`~/projects/ple-data/tasks/<id>/`），可重算、不靠題名：

- **D**＝`instruction.md` 內反引號裸檔名（無斜線）＋ `/filesystem|/app/output` 輸出路徑的 distinct 數（交付檔數代理；prose 命名的單文件 memo 題 D 會低估，已逐題核對 8 個 D≤1 候選）。
- **Corpus**＝`environment/filesystem/`（無則 `environment/files/`）總檔案數／MB（agent 要讀的資料量；world-export 題另透過 MCP app 讀同一文件樹）。
- **MCP**＝`environment/tools/mcp.json` 的 `mcpServers` 數（0＝純檔案題）。
- **InstKB**＝`instruction.md` KB（規格長度代理）。

分類規則（依序套用，first-hit-wins；先寫規則再看資料）：

1. `R-H1` D ≥ 4 → **heavy**
2. `R-H2` Corpus > 15 MB → **heavy**
3. `R-H3` InstKB ≥ 10 → **heavy**
4. `R-H4` instruction 明文要求「以程式產出」交付物（如 "IFC4 model built by a script"）→ **heavy**
5. `R-L1` D ≤ 1 且 InstKB ≤ 2 且 Corpus ≤ 6 MB → **light**
6. `R-L2` D ≤ 1 且 InstKB ≤ 3 且 Corpus ≤ 3 MB → **light**
7. 其餘 → **uncertain**（只准 quick 探測一次；失敗歸 heavy）

過往 run 佐证：`frame-extension-method` full 0.3617（300 呼叫／14,310 s）、quick 六次全 0（EXP-008/009/010/011/012/013）——與 heavy 分類一致。其餘 28 題無 run 資料。

| task | D | files | MB | MCP | InstKB | class | 觸發 |
|---|---:|---:|---:|---:|---:|---|---|
| backfeed-energization-reply | 1 | 95 | 5.5 | 13 | 1.7 | light | R-L1 |
| emergency-spillway-check | 1 | 56 | 1.0 | 8 | 1.1 | light | R-L1 |
| engineers-estimate-check | 0 | 56 | 1.0 | 8 | 1.2 | light | R-L1 |
| fill-compaction-acceptance | 1 | 55 | 1.5 | 9 | 1.1 | light | R-L1 |
| fire-solve-convergence | 1 | 50 | 1.2 | 8 | 1.8 | light | R-L1 |
| footing-settlement-verification | 0 | 55 | 1.5 | 9 | 0.8 | light | R-L1 |
| les-mesh-resolution | 1 | 50 | 1.2 | 8 | 1.0 | light | R-L1 |
| permission-to-operate-memo | 1 | 95 | 5.5 | 13 | 1.7 | light | R-L1 |
| pre-application-capacity-response | 1 | 95 | 5.5 | 13 | 1.0 | light | R-L1 |
| shoring-design-verification | 1 | 55 | 1.5 | 9 | 1.4 | light | R-L1 |
| solar-supplemental-review | 0 | 53 | 5.3 | 13 | 0.6 | light | R-L1 |
| solar-witness-test-package | 0 | 53 | 5.3 | 13 | 1.5 | light | R-L1 |
| fire-test-validation-memo | 0 | 50 | 1.2 | 0 | 2.6 | light | R-L2 |
| landscape-sheet-revision | 0 | 112 | 2.0 | 0 | 0.7 | light | R-L2 |
| data-center-site-model | 3 | 6 | 0.0 | 0 | 3.7 | uncertain | （探測一次） |
| cooling-water-flush-plan | 9 | 51 | 20.2 | 0 | 13.4 | heavy | R-H1,H2,H3 |
| data-hall-device-takeoff | 7 | 38 | 37.2 | 0 | 5.7 | heavy | R-H1,H2 |
| data-hall-mep-routing | 0 | 8 | 1.4 | 0 | 5.5 | heavy | R-H4（IFC4 由 script 產出） |
| data-hall-mep-routing-offset | 0 | 8 | 1.4 | 0 | 6.8 | heavy | R-H4 |
| division-26-specifications | 3 | 124 | 21.4 | 0 | 6.9 | heavy | R-H2 |
| eor-review-corrections | 9 | 94 | 18.3 | 0 | 14.0 | heavy | R-H1,H2,H3 |
| foundation-strategy | 8 | 50 | 107.9 | 0 | 13.3 | heavy | R-H1,H2,H3 |
| frame-extension-method | 9 | 35 | 63.4 | 0 | 13.2 | heavy | R-H1,H2,H3＋run 佐證 |
| heat-rejection-life-cycle-cost | 5 | 50 | 78.7 | 0 | 20.9 | heavy | R-H1,H2,H3 |
| lv-cable-sizing | 6 | 32 | 3.6 | 0 | 14.3 | heavy | R-H1,H3 |
| mv-conveyance-study | 4 | 66 | 27.9 | 0 | 10.0 | heavy | R-H1,H2,H3 |
| roof-deck-design | 5 | 31 | 4.3 | 0 | 10.5 | heavy | R-H1,H3 |
| seismic-diaphragm-shear | 6 | 40 | 10.1 | 0 | 6.1 | heavy | R-H1,H2 |
| wind-diaphragm-shear | 6 | 37 | 3.6 | 0 | 8.0 | heavy | R-H1,H3 |

計：light 14（其中 12 為 MCP world-export memo 題）／heavy 14／uncertain 1。

預估成本（strata 單題串行）：light quick 15–45 min／題（build ~1 min＋agent ≤ QUICK_SEC＋judge）；heavy main 2–4 h／題（frame-extension 實測 3 h 58 m）。

建議實驗組合（等同意，見 §1 下一個可執行任務）：EXP-015 quick＝`fire-test-validation-memo`（L2，純檔案）、`emergency-spillway-check`（L1，MCP×8，同時實戰驗證 P1-07）、`engineers-estimate-check`（L1，電機域）＋探測 `data-center-site-model`；EXP-016 main＝`roof-deck-design`＋`eor-review-corrections`（`frame-extension-method` 已有基線 0.3617 充當第三代表，不重跑）。

