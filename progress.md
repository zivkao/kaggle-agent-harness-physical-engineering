# PLE Solo Harness — Progress

最後更新：2026-11-16  
目前階段：`P0 — 環境與規格`  
整體狀態：`ENVIRONMENT_SETUP`  
完成度：`規劃 100% / 實作 0% / 官方驗證 0%`

> 本文件是唯一進度真相來源。任務只有附上可重現的驗證證據後才可標記完成。

## 1. Current focus

在 WSL2 建立兩個 repo 工作副本、設定評測工具和本機模型，再跑未修改的 starter。

### 下一個可執行任務

`P0-03`、`P0-04`：建立 Linux repo 工作副本，安裝並驗證 uv 與 Harbor。Kaggle 身分驗證可在準備提交前完成。

### 本階段出口條件

- [ ] 官方 starter 的 `kit check` 通過。
- [ ] Docker/uv/Harbor/gcloud/資料權限可用。
- [ ] harness repo 位於 WSL2 Linux filesystem 且使用 LF。
- [ ] secrets 只存在 repo 外部的 `local.env` 或安全 credential store。

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
- [ ] `P0-03` WSL2 Linux filesystem 建立官方 repo 與獨立 harness repo。
- [ ] `P0-04` Docker Desktop 資源、uv、Harbor、gcloud 安裝驗證。
- [ ] `P0-05` 建立 repo 外 `local.env`，完成 secret scan。
- [ ] `P0-06` 官方 starter `kit check` 通過並保存輸出。
- [x] `P0-07` 建立開發書、短中長期計畫、測試與 progress tracker。

驗證證據：

- `P0-00`：`../ple-reference/` commit `8320f0402fdca9f42476607f72bcfd5271cd50c9`；本 repo 含 `serve.py`、`taskbridge.py`、`submission.yaml`、`requirements.txt`、`LICENSE` 與 `.gitattributes`。
- `P0-00` 驗證：四個 starter 核心檔 SHA-256 與官方來源相同；`serve.py`、`taskbridge.py` 通過 Python AST parse；所有非 Git 檔案未偵測到 CRLF；獨立 Git repo 已初始化為 `main`。
- `P0-02` 驗證：release `0.4.6`，資料 commit `e0c21fa558c3127785656398e3b3bd7da5e5a5a6`。WSL 的 `~/projects/ple-data/tasks` 內 29 題共 33,410 個檔案，各題 SHA-256 同時吻合 `release.json` 和官方 `dev_set.yaml`。Windows 壓縮包為 `../ple-data/ple-data.tar.gz`。
- `P0-04` 部分完成：Ubuntu 24.04 可用，`docker info` 通過，git 與 gcloud 在 PATH，uv 與 Harbor 尚未偵測到。
- `P0-07`：`DEVELOPMENT_PLAN.md`、`progress.md`、`README.md`。

### P1 — 最小合法 Harness

- [ ] `P1-01` `submission.yaml`、`serve.py` 與 dependency lock。
- [ ] `P1-02` WebSocket protocol adapter 與健康啟動。
- [ ] `P1-03` model client、timeout、retry、cache marking。
- [ ] `P1-04` taskbridge tool adapter 與統一錯誤型別。
- [ ] `P1-05` state machine、deadline、graceful finalize。
- [ ] `P1-06` structured logs、redaction、unit/contract tests。

驗證證據：待補。

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

實驗規則：一次只改一個主要變因；沒有 commit/config/task/result 的實驗不作決策依據。

---

## 7. Defect and failure log

| ID | Priority | Area | Symptom | Root cause | Fix | Retest | Status |
|---|---|---|---|---|---|---|---|
| — | — | — | 尚無執行結果 | — | — | — | — |

Failure taxonomy：`BOOT / PROTOCOL / MODEL / TOOL / MCP / FILE / FORMAT / CALCULATION / HARD_GATE / RUBRIC / RESOURCE / TIMEOUT / ARTIFACT / PLATFORM / UNKNOWN`

---

## 8. Risks and blockers

| ID | Risk/blocker | Impact | Owner | Next action | Status |
|---|---|---|---|---|---|
| R-001 | Kaggle 要求身分驗證 | 影響正式提交 | Solo | 提交前完成 Kaggle 身分驗證 | OPEN |
| R-002 | 工作區位於 Windows `D:` | 官方建議 WSL2 Linux filesystem | Solo | 決定實作 repo 的 WSL2 路徑 | OPEN |
| R-003 | 本機模型費用/配額未知 | 無法估算完整 dev run 成本 | Solo | P0 後跑一題記錄成本 | OPEN |
| R-004 | Rules 頁需登入確認 | 資格/提交細節可能遺漏 | Solo | 登入後逐條確認並記錄 | OPEN |
| R-005 | WSL 內未偵測到 uv 與 Harbor | 尚不能執行官方 kit 和 eval | Solo | 依 `SETUP.md` 在 WSL2 安裝並驗證 | OPEN |
| R-006 | Hugging Face 資料 access | 29 題已解壓且雜湊全數吻合 | Solo | 使用本機 `--tasks-dir` | CLOSED |
| R-007 | WSL 全面報 ERROR_FILE_NOT_FOUND（見 §12） | 所有 Linux 端工作暫停 | Solo | 使用者以系統管理員執行 `wsl --update` + `wsl --shutdown` | OPEN |
| R-008 | Store 版 PowerShell 套件損壞（`pwsh.exe` alias 失效） | OpenCode shell 階段的 spawn 失敗 | Solo | 已在 `~\.config\opencode\opencode.json` 設定 `shell` 指向 `C:\Program Files\PowerShell\7\pwsh.exe` 繞過 | WORKAROUND |

---

## 9. Decisions

| ID | Date | Decision | Reason | Revisit trigger |
|---|---|---|---|---|
| ADR-001 | 2026-11-16 | 採單 Agent state machine 起步 | 可測、可觀察、較低複雜度 | 數據證明多 Agent 明顯改善 |
| ADR-002 | 2026-11-16 | hard gates 優先於成本最佳化 | 未通過 hard gate 會失去最佳化分 | hard-gate pass 已穩定後 |
| ADR-003 | 2026-11-16 | 以官方 starter 建 baseline | 降低 protocol/提交風險 | starter 無法滿足必要功能 |
| ADR-004 | 2026-11-16 | 01/01 feature freeze | 為最終可靠度與提交留緩衝 | 官方日期變更 |

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

規避（R-008）：OpenCode shell 原先指向失效的 `WindowsApps\pwsh.exe` alias；已於 `C:\Users\ZivKao\.config\opencode\opencode.json` 加入 `"shell": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"`，shell 已恢復可用。

