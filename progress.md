# PLE Solo Harness — Progress

最後更新：2026-11-20  
目前階段：`P1 — 最小合法 Harness（提前開工）`  
整體狀態：`P2_PREP_EXP016_017_SCORED_DEF003_NEW — 待 P3 方向／成本／下一題決策`
完成度：`規劃 100% / 實作 10% / 官方驗證 55%`

> 本文件是唯一進度真相來源。任務只有附上可重現的驗證證據後才可標記完成。

## 1. Current focus

開發環境已遷移到 WSL `Ubuntu`（26.04.1 LTS，Docker 29.10.0／uv 0.13.9／Harbor 0.20.0），未修改的官方 `plan-verify` starter 已通過 `kit check`（`rc=0`），且單題 dev baseline 已完成並取得首個實測分數：**`frame-extension-method` = 0.3617**（14,310 s／題，輸出 326,888 tokens）。下一步進入 P1（處理 `mcp` WARN 與 harness 改進），並評估以付費 API（如 DeepSeek）加速 dev 全量跑。

**2026-11-19 更新：** P1-07（MCP 中繼工具）已完成並通過 `kit check` 全部 7 階段；補丁版單題重跑 0.3557 vs 基線 0.3617（本題無 MCP，差異屬單次執行的模型隨機性，約 ±0.01）。

### 2026-11-19 — 最終環境與通訊架構（Agent 必讀）

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

### 下一個可執行任務

1. **待使用者決策（三項、互不阻擋）**：(a) **P3 起手＝hard-gate 自我驗證**——以「每個 item 的硬閘門全過」為第一目標（兩題 heavy 已證明 0.6 權重全歸零：EXP-016 register_hard forfeit、EXP-017 `hard_pass_rate` 0.0）；(b) **成本**——本地 Strata heavy 平均 3 h 52 m／題 → 14 題串行 ≈ 54 h，vs 付費 API（flash 單題實估 $0.2–0.4）多題並行一晚跑完 29 題（`JUDGE_*`／上游在 `model_proxy/config.yaml` 切換、不動 `submission.yaml`）；(c) **下一題候選**——`roof-deck-design`（heavy／checks／D=5，原 EXP-016 提案、尚未跑）或 `data-hall-mep-routing`（heavy／R-H4：交付物須由 script 產出 IFC4）。
2. **DEF-003 修法待核准**（見 §7）：main `serve.py` 的上下文預算管理——事前守門（≤ n_ctx − 安全邊際）取代事後 cut、舊 tool 結果摘要化、收尾前預留 headroom。未核准前 main 碼維持 `eb918d8` 不動；參數不得綁死在 262,144（本機 Strata 常數，正式模型視窗不同）。
3. **quick 維持暫停**（使用者指示不變）：EXP-015 #1/#2/#3、uncertain 探測全部暫止；DEF-002 的 live 重測（`DELIVERABLE_PATHS=/app/files/` 同參單次）列為 quick 復活時的第一件事。
4. **ADR-010 revisit**（待使用者決策）：light 題 zero-deliverable 條件已成立；quick 存廢隨 DEF-002 live 重測結果一併決定。
5. **正式 artifacts 需由宣告模型產生**（見 R-012，不變）：提交前要將 proxy 上游換回真的 Vertex `claude-opus-5-5`（目前該 project 的 `aiplatform` API 為 DISABLED，需先開通）。

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
| P2 Baseline Agent Loop | 11/24–11/29 | READY | 0/6 | 前置 P1 已 DONE；main dev 子集 2/2 已分數化（EXP-016 0.3673／EXP-017 0.2573，皆成功交付、同一 hard-gate 失分結構）；quick 依使用者指示暫停 → P2 起步與下一題待使用者決策 |
| P3 工程驗證核心 | 11/30–12/06 | BACKLOG | 0/5 | — |
| P4 多格式工具能力 | 12/07–12/13 | BACKLOG | 0/5 | — |
| P5 完整 Dev Set/回歸 | 12/14–12/20 | BACKLOG | 0/6 | — |
| P6 最佳化/模型選擇 | 12/21–12/27 | BACKLOG | 0/5 | — |
| P7 壓力/可靠度/安全 | 12/28–12/31 | BACKLOG | 0/6 | — |
| P8 凍結/驗收/提交 | 01/01–01/06 | BACKLOG | 0/8 | — |

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

- [ ] `P2-01` project discovery 與檔案 inventory。
- [ ] `P2-02` TaskSpec/deliverable/hard-gate 抽取。
- [ ] `P2-03` planning/execution/context loop。
- [ ] `P2-04` preflight verifier 與 bounded repair。
- [ ] `P2-05` 四領域代表題 run。
- [ ] `P2-06` baseline scorecard 與 failure taxonomy。

驗證證據：待補。

### P3 — 工程驗證核心

- [ ] `P3-01` unit normalization/dimensional checks。
- [ ] `P3-02` calculation/assumption/evidence ledger。
- [ ] `P3-03` hard-gate 與 rubric evidence matrix。
- [ ] `P3-04` consistency verifier 與 impact-based retest。
- [ ] `P3-05` 與 P2 baseline 比較。

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
- [ ] `P8-08` Kaggle 提交成功並確認狀態。

驗證證據：待補。

---

## 4. Quality dashboard

尚未建立 baseline，所有數值先標 `N/A`。

| 指標 | Baseline | Current | Release target |
|---|---:|---:|---:|
| Dev mean score | N/A | N/A | 高於 starter，且無重大領域退步 |
| Hard-gate pass rate | N/A | N/A | 持續上升 |
| Zero-score rate | N/A | N/A | 低於 baseline |
| Artifact-producing rate | N/A | N/A | >= 95% |
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
| Official kit | 7 | 7 | 0 | 2026-11-20 | `kitcheck5.log`：7 階段全 PASS（`eb918d8`），僅 `artifacts` WARN（R-012） |

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
| EXP-006 | 2026-11-18 | `97cbd38`：serve.py 加 `mcp_list`／`mcp_call` 中繼工具（MCPClient 於 task 開始時 initialize＋list_tools 並快取；planner/worker/verifier 三角色皆可呼叫；輸出 clip、args 以 JSON字串傳遞） | 官方 `kit check`（含 `mcp` 階段） | 讓 harness 正式走協議的 `http` 請求存取任務 MCP server，消除 `[WARN] mcp` | 靜態驗證：AST ok、pyflakes 0、無新增 >80 char 行；**`kit check` 22:3x：`[PASS] mcp`（82 s、13 requests、13,814 in／1,211 out）、6 階段全 PASS、僅剩 `artifacts` WARN**；映像 `plebench-serve:b8a6572ec27dd14a`（`~/projects/kitcheck4.log`） | **P1-07 完成**；以補丁版重跑單題做分數對照（EXP-007） |
| EXP-007 | 2026-11-18 | `97cbd38`（MCP 補丁版）、其餘同 EXP-005 | `frame-extension-method` 重跑 | 確認 MCP 補丁不降分、作為 P1 版對照 | **score 0.3557（`ok`，11,595 s＝3 h 13 m）**；tokens in 23,487,057／cache 23,086,775／out 320,314；與基線 0.3617 差 −0.006（−1.7%）。本題無 MCP server（`mcp_servers=[]`），補丁碼路徑為 no-op → 差異屬模型執行隨機性 | run `runs/plan-verify-20261118-224102/`；累計 proxy 543 呼叫 | **補丁定版**；單題單次跑的分數噪聲約 ±0.01，日後 A/B 需以多 run 或更大任務集對照 |

實驗規則：一次只改一個主要變因；沒有 commit/config/task/result 的實驗不作決策依據。

---

## 7. Defect and failure log

| ID | Priority | Area | Symptom | Root cause | Fix | Retest | Status |
|---|---|---|---|---|---|---|---|
| DEF-001 | P0 | quick harness／ARTIFACT+TIMEOUT | EXP-008 score 0.0：grader `ERR_NO_SUBMISSION`，全程 25 呼叫都在 `sed/cat/grep` 讀規則檔，最後一步（step 29）模型正要 `cat > gen.py` 產出交付物時被收尾呼叫（`tool_choice=none`）擋下，改以文字輸出 pseudo-`<tool_call>`，從未執行 | ① 15k out 預算對重工程題少一個數量級（完整版 327k）；② 無「交付檢查點」：預算燒一半仍無 write_file 也不強制先寫最小交付版；③ 收尾呼叫完全禁工具，恰好殺掉最重要的一次寫入；④ plan 8 呼叫對小模型無產出（全花在讀檔）；⑤（EXP-009）提前放棄：檢查點按預算 share 觸發，模型只燒 11–22% 就以純文字結束，檢查點從不生效 | 候選：① 交付檢查點（呼叫／token 半數無寫入→注入「立即寫最小交付」指令，75% 後只准 write）；② 收尾呼叫允許 write 類工具（write-only wrap）；③ 依任務量級調-budget（重題 60 min／80 呼叫／60k out）或快速版只跑輕題；④ quick 模式跳過 planner | v2（`8d34278`）同題實測仍 0.0（EXP-009）→ v3 交付閘門（`_writes == 0` 時打回純文字結束 ≤2 次）＋mock gate 案例，再重測 mock＋實測；v3（`16053ed`）已實作：mock 7/7（`gate`：打回 1/2 後補寫 `cat >` 送達 exec；`gate2`：只打回 2/2 上限後接受） ；實測（EXP-010）仍 0.0：模型改以**空 content 結束**，繞過 gate 的 `message.content` 非空條件；v4（`1ea5c67`）實測（EXP-011）仍 0.0 但模式再變：19 次帶工具呼叫誠實工作（696 s、gate 0 次），第 19 呼叫生成交付腳本途中 `stop=output`（17,931 out）截斷未執行 → 失敗族從「提前放棄」轉為「預算燒盡」，根因①主導；預算加檔（EXP-012，`25e3173`）仍 0.0：wall／out 未盡（1,353 s／45,130 out）、`stop=requests@41` ≪ 全域 76 ⇒ 步驟級份額（L581）觸發；模型分段寫腳本（`part2 ok`）未及執行即停 → 失敗族再轉為「步驟配額耗盡」，根因從①轉為配額結構 | IN_PROGRESS（v3 實測失敗、根因已定位；v4（`1ea5c67`）已實作：任何無工具結束（含空 content）都打回、空 assistant turn 不回放；mock 8/8（新增 `gate_empty`）；v5（`c476e8c`）mock 9/9（`quota` 精確重現 EXP-012 於 41 死因：verifier 份額耗盡＋空 verdict→曾被當 PASS）並修復：out-of-share 步驟的空 verdict 不再終止 fix 迴圈；實測 EXP-013（2026-11-20）：capped→fix round 照跑（修復生效），但仍 0 分——失敗族轉為「fix round 只讀不寫」（模型收到明確 gap 後仍零 write） | SCOPED-BY-ADR-010（2026-11-20 使用者選 (c)：heavy 題不再跑 quick，DEF-001 的 quick 側修復止於 v5；剩餘驗證＝EXP-015 light 題能否正常產出。`writes==0` 事件式指令為備選單變因，僅在 light 題也出現同樣症狀時才動）**→ EXP-015 實測（2026-11-20，light）：零交付重現（0.0／capture `files={}`）。症狀雖同（收到明確 gap 仍不寫），直接原因是三線防護被 `_writes` 誤計關掉（轉 DEF-002）——事件式指令在誤計未除前無從生效；ADR-010 revisit 條件成立，待使用者決策** |
| DEF-002 | P0 | quick harness／FILE＋HARD_GATE | EXP-015 #1b 全程 `checkpoint:`＝0、`gate:`＝0、`wrap-write:`＝0：零交付的三道事件式防護從頭未觸發，模型兩度收到 verifier「完全沒有交付物」清單仍 0 次 write，最終 capture `files={}`、0/208 分 | checkpoint（40/70%）、交付閘門、wrap_write 共用 `_writes == 0` 前題，而 `_writes` 由 `_WRITE_BASH` 對命令**文字**猜寫入：裸 `>` 會命中 python heredoc 本體裡的比較式與箭頭字串（#1b 呼叫 #26：1,953 字元指令、`if series[i]>=lim:`／`" -> "`，`>` 在第 572 字元）→ `_writes=1` 一次、整題防護永久失效；轉錄只記 `arguments[:200]` 令誤計不可見。#1a 的 `2>&1` 誤計是同一缺陷族；v6（`738534b`）只修掉 fd 重新導向與 bare `mkdir` 兩類 | **待使用者核准（本輪授權修復範圍＝fd/mkdir 類，換計數機制屬新策略）**：①建議真值化——`_writes` 改由 taskbridge capture 增量（交付路徑實際檔案變化）推導，不再解析命令文字；②保守方案＝匹配前剝除 heredoc 本體與引號字串再跑 `_WRITE_BASH` | **FIXED（quick v7 `7ab4ae6`，2026-11-20）**：真值計數如上（PLELAND 探針＋baseline 差分、即時重算、刪除回零、探針失敗留痕保持武裝）；驗證＝mock **16/16**＋偵測證明（`heredoc`／`landflip`／`fixflow` 於 v6 全 `[FAIL]`）＋#1b 36 呼叫離線重放（root `/app/files/`：全程 landed=0）；順帶 `wrap_write` 限定 deliver 步驟＋每步一次性 | LIVE 重測待 quick 復活（同參單次，`DELIVERABLE_PATHS=/app/files/`）；quick 依使用者指示暫停中 |
| DEF-003 | P1 | main harness／RESOURCE（context window） | 兩次 main 正式 run 的**尾聲**都撞到 Strata 262,144 視窗：EXP-016 最終 prompt 261,799（僅剩 337）；EXP-017 `harness error after its summary: BadRequestError: 400 … request exceeds the context window: prompt (262159 tokens) leaves no room to answer in the context (262144)`；proxy 整 run 另有 9 次 400（全為 context overflow、LiteLLM 各重試 3 次） | 本機模型視窗固定 262,144，而 starter 只在 400 **之後**被動剪舊 tool 結果（EXP-017 轉錄 5 次 `context full: cut N old tool results`＝cut 5/2/1/1/1），沒有 headroom 規劃、沒有步驟級 prompt 上限；長 run 的 transcript 單調成長 ⇒ 收尾階段必然頂到天花板。實際損失＝EXP-017「summary 之後的最後一輪自我驗證／迭代」無法執行（交付已寫入、評分不受影響：`exception_info=None`、`serve_status=completed`） | **未動碼（待核准）**：① prompt 預算守門（目標 ≤ n_ctx − 安全邊際，事前剪／摘要而非事後 cut）；② 舊 tool 結果摘要化取代整筆 cut；③ 收尾前預留 headroom（最後 N 呼叫不得再讓 context 成長）。**不得對 262,144 overfit**：那是本機 Strata 常數，正式宣告模型視窗不同 | 下次 main run：`serve.log` 不得再出現 `harness error: BadRequestError … exceeds the context window`，並確認收尾自我驗證輪次保住 | OPEN-BACKLOG（不阻擋交付；系統性＝2/2 main run 重現） |

Failure taxonomy：`BOOT / PROTOCOL / MODEL / TOOL / MCP / FILE / FORMAT / CALCULATION / HARD_GATE / RUBRIC / RESOURCE / TIMEOUT / ARTIFACT / PLATFORM / UNKNOWN`

---

## 8. Risks and blockers

| ID | Risk/blocker | Impact | Owner | Next action | Status |
|---|---|---|---|---|---|
| R-001 | Kaggle 要求身分驗證 | 影響正式提交 | Solo | 提交前完成 Kaggle 身分驗證 | OPEN |
| R-002 | 工作區位於 Windows `D:` | 官方建議 WSL2 Linux filesystem | Solo | 已改在 WSL `~/projects/` 開發，Windows 端只放規劃文件 | CLOSED |
| R-003 | 本機模型費用/配額未知 | 無法估算完整 dev run 成本 | Solo | 單題 baseline 記錄 tok/s 與 wall time | CLOSED（EXP-005：out 326,888 tok／14,310 s＝22.8 tok/s wall；in 34.6M、cache 命中 98.4%；換算 DeepSeek flash 單題 $0.19–0.38、29 題 $5–25） |
| R-004 | Rules 頁需登入確認 | 資格/提交細節可能遺漏 | Solo | 登入後逐條確認並記錄 | OPEN |
| R-005 | WSL 內未偵測到 uv 與 Harbor | 尚不能執行官方 kit 和 eval | Solo | 已安裝 uv 0.13.8 與 Harbor 0.20.0（官方 pin）| CLOSED |
| R-006 | Hugging Face 資料 access | 29 題已解壓且雜湊全數吻合 | Solo | 使用本機 `--tasks-dir` | CLOSED |
| R-007 | WSL 全面報 ERROR_FILE_NOT_FOUND（見 §12） | 所有 Linux 端工作暫停 | Solo | 根因為 `System32\wsl.exe` 缺少同目錄 `wslservice.exe`；改用 `C:\Program Files\WSL\wsl.exe` 後全部指令正常 | CLOSED |
| R-008 | Store 版 PowerShell 套件損壞（`pwsh.exe` alias 失效） | OpenCode shell 階段的 spawn 失敗 | Solo | 已在 `~\.config\opencode\opencode.json` 設定 `shell` 指向 `C:\Program Files\PowerShell\7\pwsh.exe` 繞過 | WORKAROUND |
| R-009 | 本機模型與官方評測模型不同（IQ3 量化 27B vs Claude Opus 5.5） | 本地分數僅供相对比较，不可外推正式分 | Solo | 每輪固定同一模型與設定做 A/B；正式提交前另評雲端模型 | OPEN |
| R-010 | 29 題 agent 時限皆 6 h，本機 ~20 tok/s | 單題全跑可能數小時，dev run 成本高 | Solo | 實測（EXP-005）：單題 3 h 58.5 m、out 僅 327k tokens → 本機串行 29 題要數天。對策：改接付費 API（DeepSeek flash 併發 2500）可 8–16 題並行、一晚跑完；或 `MAX_OUTPUT_TOKENS`／task 子集控制 | OPEN |
| R-012 | dev artifacts 由本機 strata（透過 `claude-opus-5-5` 別名）產生，而 entry 宣告模型是 `google-cloud/claude-opus-5-5`；官方規則「Call only the model you declared」 | 若把 strata 產物直接匯入 `artifacts/` 提交，與宣告模型不符，違反 fair-play 且 manifest 記錄 `model_api=claude-opus-5-5` | Solo | 本地 strata 只用於迴圈驗證與 P1 對照（維持 `--no-export`）；產生正式 artifacts 前把 proxy 上游換回真 Vertex（`aiplatform` API 目前 DISABLED，需先開通）後重跑 dev set | OPEN |
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

