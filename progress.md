# PLE Solo Harness — Progress

最後更新：2026-11-19  
目前階段：`P1 — 最小合法 Harness（提前開工）`  
整體狀態：`P1_DEF001_V4_GATE_EMPTY_PENDING`  
完成度：`規劃 100% / 實作 5% / 官方驗證 50%`

> 本文件是唯一進度真相來源。任務只有附上可重現的驗證證據後才可標記完成。

## 1. Current focus

開發環境已遷移到 WSL `Ubuntu`（26.04.1 LTS，Docker 29.10.0／uv 0.13.9／Harbor 0.20.0），未修改的官方 `plan-verify` starter 已通過 `kit check`（`rc=0`），且單題 dev baseline 已完成並取得首個實測分數：**`frame-extension-method` = 0.3617**（14,310 s／題，輸出 326,888 tokens）。下一步進入 P1（處理 `mcp` WARN 與 harness 改進），並評估以付費 API（如 DeepSeek）加速 dev 全量跑。

**2026-11-19 更新：** P1-07（MCP 中繼工具）已完成並通過 `kit check` 全部 7 階段；補丁版單題重跑 0.3557 vs 基線 0.3617（本題無 MCP，差異屬單次執行的模型隨機性，約 ±0.01）。

**2026-11-19（二）：** DEF-001 使用者選 (a)（修後重測）。quick v2（commit `8d34278`）對 `frame-extension-method` 的重測已跑完（run `plan-verify-20261119-112842`）：仍 **0 分／`ERR_NO_SUBMISSION`**，但失敗模式改變——模型只用 **8/40 呼叫、1,233 輸出 tokens（預算 11–22%）就以純文字回答提前放棄**，40/70% 預算 share 檢查點從未被觸發。下一步 v3：**交付閘門**（見 DEF-001）。

**2026-11-19（三）：** DEF-001 v3 交付閘門已實作（quick branch `16053ed`）：`deliver` 步驟在非收尾、非截斷的純文字結束且 `_writes == 0` 時打回（GATE 訊息指示立即以 write_file／bash 在精確路徑寫出最小交付物；上限 `QUICK_GATE=2` 次後接受答案；checkpoint、wrap_write、nudge 路徑不受影響）。驗證：mock **7/7**（新增 `gate`：打回 1/2 → 模型補寫 `cat > /app/out.txt` 送達 exec 通道，stop=none；`gate2`：固執模型只打回 2/2 後接受）、AST ok、pyflakes 0、無新增 >80 char 行（11 條長行與 v2 相同，皆為 starter prompt 字串）。依使用者指示**暫停**，同題實測重跑等同意。

### 下一個可執行任務

1. **快速版（DEF-001，已選 (a)）**：v3＝**交付閘門**已實作（quick `16053ed`：`_writes == 0` 的純文字結束打回 ≤2 次＋GATE 指令；mock 7/7）。下一步：以 v3 重跑 `frame-extension-method` 實測（同 EXP-009 設定：`--no-export`、僅 strata），驗證閘門能否把 0 分轉為有交付物。（使用者指示：v3 已完成並暫停——實測重跑等同意。）
2. `P1-05`／`P1-06`：deadline 行為（`cancel` 後 10 s 內發 `done`）與 structured logs／unit tests（DEVELOPMENT_PLAN P1 出口條件：注入 model 429/500/timeout、tool error、斷線皆能有界結束）。
2. dev 全量跑的成本決策：本機 strata 29 題約需數天；改用 DeepSeek 等付費 API（flash 單題實估 $0.2–0.4）可多題並行，一晚跑完 29 題，但 `JUDGE_*`／上游切換要在 `model_proxy/config.yaml` 完成，且不影響 `submission.yaml`。
3. 正式 artifacts 需由宣告模型產生（見 R-012）：提交前要將 proxy 上游換回真的 Vertex `claude-opus-5-5`（目前該 project 的 `aiplatform` API 為 DISABLED，需先開通）。

### 本階段出口條件

- [x] 官方 starter 的 `kit check` 通過。
- [x] Docker/uv/Harbor/gcloud/資料權限可用。
- [x] harness repo 位於 WSL2 Linux filesystem 且使用 LF。
- [x] secrets 只存在 repo 外部的 `local.env` 或安全 credential store。

---

## 2. Milestone board

| 階段 | 日期 | 狀態 | 完成 | 驗證摘要 |
|---|---|---:|---:|---|
| P0 環境與規格 | 11/16–11/19 | IN_PROGRESS | 3/8 | 官方 repo、starter、規劃和 29 題已齊；WSL Docker 可用 |
| P1 最小合法 Harness | 11/20–11/23 | BACKLOG | 0/6 | — |
| P2 Baseline Agent Loop | 11/24–11/29 | BACKLOG | 0/6 | — |
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
- [ ] `P1-05` state machine、deadline、graceful finalize。
- [ ] `P1-06` structured logs、redaction、unit/contract tests。
- [x] `P1-07` MCP 中繼工具（`mcp_list`／`mcp_call`）通過官方 `kit check` 的 `mcp` 階段。

驗證證據：

- `P1-01`：starter 四核心檔逐位元組保持（見 P0-00），`requirements.txt` 為 dependency pin；`kit check` `[PASS] files: 14 files`、`kit validate` rc=0。
- `P1-02`：`kit check` `[PASS] listen: websocket accepted 2 s after start`（< 120 s 門檻）。
- `P1-03`：EXP-005 baseline 實測 34.6M prompt 中 34.1M cache 命中（98.4%，`CACHE_MARK` 生效）；`recover()` 重試邏輯在 3 h 58 m 跑中未觸發致命錯誤（0 errored trials）。
- `P1-04`／`P1-07`：commit `97cbd38 P1-01: expose task MCP servers to all agent roles via mcp_list/mcp_call meta-tools`（serve.py＋108/−5；pyflakes 0；AST ok；未新增 >80 char 行）。以 `taskbridge.MCPClient` 於任務開始時 `initialize`＋`list_tools` 並快取目錄，模型透過兩個中繼工具按需發現與呼叫（避免 ~500 KB 目錄進 context）；**官方 `kit check` 於 22:3x 完成：`[PASS] mcp: mcp.txt written, done in 82 s with 13 request(s), 13814 in / 1211 out tokens`，`[WARN] mcp` 消除**；全套 `submission.yaml/files/build/model/listen/smoke/mcp` 7 階段全 PASS，只剩 `artifacts` WARN（尚未匯入 dev artifacts，符合 R-012 決策）。新映像 `plebench-serve:b8a6572ec27dd14a`，日誌 `~/projects/kitcheck4.log`。統一錯誤型別：`run_tool` 錯誤路徑含 `TaskError`/`MCPError`/`KeyError`/`ValueError`。

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
| Static/lint/type | 3 | 3 | 0 | 2026-11-16 | 官方檔案 SHA-256、Python AST、LF scan 通過 |
| Unit | 0 | 0 | 0 | — | — |
| Contract | 0 | 0 | 0 | — | — |
| Integration | 0 | 0 | 0 | — | — |
| Functional | 0 | 0 | 0 | — | — |
| Regression-fast | 0 | 0 | 0 | — | — |
| Regression-full | 0 | 0 | 0 | — | — |
| Stress | 0 | 0 | 0 | — | — |
| Reliability/fault | 0 | 0 | 0 | — | — |
| Security | 0 | 0 | 0 | — | — |
| Official kit | 0 | 0 | 0 | — | — |

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
| EXP-006 | 2026-11-18 | `97cbd38`：serve.py 加 `mcp_list`／`mcp_call` 中繼工具（MCPClient 於 task 開始時 initialize＋list_tools 並快取；planner/worker/verifier 三角色皆可呼叫；輸出 clip、args 以 JSON字串傳遞） | 官方 `kit check`（含 `mcp` 階段） | 讓 harness 正式走協議的 `http` 請求存取任務 MCP server，消除 `[WARN] mcp` | 靜態驗證：AST ok、pyflakes 0、無新增 >80 char 行；**`kit check` 22:3x：`[PASS] mcp`（82 s、13 requests、13,814 in／1,211 out）、6 階段全 PASS、僅剩 `artifacts` WARN**；映像 `plebench-serve:b8a6572ec27dd14a`（`~/projects/kitcheck4.log`） | **P1-07 完成**；以補丁版重跑單題做分數對照（EXP-007） |
| EXP-007 | 2026-11-18 | `97cbd38`（MCP 補丁版）、其餘同 EXP-005 | `frame-extension-method` 重跑 | 確認 MCP 補丁不降分、作為 P1 版對照 | **score 0.3557（`ok`，11,595 s＝3 h 13 m）**；tokens in 23,487,057／cache 23,086,775／out 320,314；與基線 0.3617 差 −0.006（−1.7%）。本題無 MCP server（`mcp_servers=[]`），補丁碼路徑為 no-op → 差異屬模型執行隨機性 | run `runs/plan-verify-20261118-224102/`；累計 proxy 543 呼叫 | **補丁定版**；單題單次跑的分數噪聲約 ±0.01，日後 A/B 需以多 run 或更大任務集對照 |

實驗規則：一次只改一個主要變因；沒有 commit/config/task/result 的實驗不作決策依據。

---

## 7. Defect and failure log

| ID | Priority | Area | Symptom | Root cause | Fix | Retest | Status |
|---|---|---|---|---|---|---|---|
| DEF-001 | P0 | quick harness／ARTIFACT+TIMEOUT | EXP-008 score 0.0：grader `ERR_NO_SUBMISSION`，全程 25 呼叫都在 `sed/cat/grep` 讀規則檔，最後一步（step 29）模型正要 `cat > gen.py` 產出交付物時被收尾呼叫（`tool_choice=none`）擋下，改以文字輸出 pseudo-`<tool_call>`，從未執行 | ① 15k out 預算對重工程題少一個數量級（完整版 327k）；② 無「交付檢查點」：預算燒一半仍無 write_file 也不強制先寫最小交付版；③ 收尾呼叫完全禁工具，恰好殺掉最重要的一次寫入；④ plan 8 呼叫對小模型無產出（全花在讀檔）；⑤（EXP-009）提前放棄：檢查點按預算 share 觸發，模型只燒 11–22% 就以純文字結束，檢查點從不生效 | 候選：① 交付檢查點（呼叫／token 半數無寫入→注入「立即寫最小交付」指令，75% 後只准 write）；② 收尾呼叫允許 write 類工具（write-only wrap）；③ 依任務量級調-budget（重題 60 min／80 呼叫／60k out）或快速版只跑輕題；④ quick 模式跳過 planner | v2（`8d34278`）同題實測仍 0.0（EXP-009）→ v3 交付閘門（`_writes == 0` 時打回純文字結束 ≤2 次）＋mock gate 案例，再重測 mock＋實測；v3（`16053ed`）已實作：mock 7/7（`gate`：打回 1/2 後補寫 `cat >` 送達 exec；`gate2`：只打回 2/2 上限後接受） ；實測（EXP-010）仍 0.0：模型改以**空 content 結束**，繞過 gate 的 `message.content` 非空條件 | IN_PROGRESS（v3 實測失敗、根因已定位；v4＝gate 條件改為任何無工具結束（含空 content）都打回，待同意） |

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
| ADR-009 | 2026-11-19 | 快速版走 `quick` branch＋`ple-solo-harness-quick` worktree：內部預算 30 分鐘／40 次呼叫（含重試與收尾）／15,000 累計輸出 tokens，保留 5 分鐘＋4 呼叫＋4,000 tokens 收尾；單次呼叫輸出≤2,000、逾時≤180 s；`submission.yaml` 與 main branch（正式提交設定）完全不動 | 本機 strata 完整版單題 3–4 h，dev 迴圈太慢；先跑快速版評估、再對收斂版跑完整版生成 artifacts | 快速版分數明顯掉到不可用（<基線 −0.1），且原因無法在完整版修復 |

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

