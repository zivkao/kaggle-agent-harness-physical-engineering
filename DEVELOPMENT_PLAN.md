# PLE Solo Harness 開發書

版本：0.1  
建立日期：2026-11-16  
適用時區：Asia/Taipei  
開發模式：單人參賽、LLM-assisted / vibe coding、測試與證據驅動

---

## 1. 專案任務

建立一套可提交至 Google Physical-Engineering's Last Exam（PLE）的自主 Agent harness。它必須能在隔離的 task container 中：

1. 理解任務與交付要求。
2. 盤點 PDF、試算表、郵件、CAD/BIM、規範與既有文件。
3. 建立可追蹤的工程假設、限制與計算計畫。
4. 呼叫 shell、檔案與 task-local MCP 工具完成工作。
5. 產生計算書、設計審查、圖面、模型、表格或技術備忘錄。
6. 在提交前檢查安全硬條件、數值、單位、格式、完整性與檔案存在性。
7. 發現問題時進行有界、針對性的修復。
8. 在資源與時間限制內穩定結束，留下可評測 artifacts。

### 1.1 成功定義

成功分三層，不把得獎當成唯一結果：

- **最低成功**：通過官方 `kit check`，完成合法提交，29 題 artifacts 可離線重評。
- **競爭成功**：dev set 平均分穩定高於 starter baseline，且三次重跑變異小。
- **伸展成功**：hidden leaderboard 具競爭力，形成可公開的 agent engineering 作品與技術報告。

### 1.2 非目標

- 不在 harness 中硬編公開題答案或讀取自身 artifacts。
- 不將 LLM 文字信心視為工程驗證。
- 不在早期投入複雜多 Agent 編排。
- 不依賴評測時不存在的外網、雲端服務或未允許模型。
- 不為單題分數破壞跨題穩健性。

---

## 2. 官方邊界與不可違反條件

以下條件應視為架構輸入，而不是最後才處理的部署問題：

| 項目 | 條件 | 設計影響 |
|---|---|---|
| 提交內容 | 單一 Git commit；根目錄含 `submission.yaml`、`serve.py`、依賴與 `artifacts/` | 所有建置須可重現，禁止手動漏步 |
| 模型 | 正式提交限官方允許的 `google-cloud/<id>` | provider adapter 不可綁死本機模型 |
| Harness 介面 | `0.0.0.0:$PORT` WebSocket server，120 秒內就緒 | 啟動路徑必須輕量且可健康檢查 |
| Serve 資源 | Linux amd64、2 CPU、4 GB RAM、512 processes | 限制併發、記憶體與子程序數量 |
| 可寫空間 | 唯讀 root；`/tmp`、`$HOME` 各 1 GB | cache 與暫存檔需配額治理 |
| 網路 | 僅能經 egress proxy 呼叫已宣告模型；task container 無外網 | 所有工具與參考資料必須在容器內可用 |
| 任務時間 | 每題最多 6 小時 | 全域 deadline、階段預算與 graceful finalize 必須內建 |
| Build | 最長 30 分鐘；系統 apt 套件不會自動帶入 serve | 依賴安裝於 `/opt/harness`，建置必須鎖版 |
| Artifact | 單檔 95 MiB、單題 256 MiB/2,000 files、全體 512 MiB/10,000 files | 產物預檢與大小治理是必要功能 |
| 公平性 | harness 執行時不得讀取自己已提交的 artifacts | 程式與 artifacts 嚴格分離 |

### 2.1 Windows 開發限制

正式實作建議在 WSL2 Linux filesystem 中進行：

- 不放在 `/mnt/c` 或 `/mnt/d`。
- Git 設定 `core.autocrlf input`。
- `.gitattributes` 使用 LF。
- Docker Desktop 至少配置 6 CPU、16.25 GB RAM，並預留 task/world images 空間。

---

## 3. 生長式架構：根、樹幹、枝條、葉片

### 3.1 根（Foundation）

根決定系統能否活著完成任務：

- 官方 repo、資料存取與 WSL2/Docker 環境。
- 可重現依賴與設定管理。
- WebSocket protocol 與 taskbridge。
- 模型 provider adapter、重試、timeout、token/cost accounting。
- 結構化 log、run ID、錯誤分類與軌跡保存。
- 單元測試、CI、secret scan、lint/type check。

**根的完成門檻**：官方 smoke 與 MCP check 通過；斷線、timeout、格式錯誤時不會無限循環或遺失最終訊息。

### 3.2 樹幹（Core Agent Loop）

樹幹是一條簡單、可觀察、可恢復的單 Agent 主迴圈：

```text
BOOT
  -> DISCOVER
  -> SPECIFY
  -> PLAN
  -> EXECUTE
  -> VERIFY
  -> REPAIR (bounded)
  -> FINALIZE
```

- `DISCOVER`：盤點目錄、工具、輸入檔、deliverables 與 task-local MCP。
- `SPECIFY`：建立交付物契約、硬限制、工程假設、未知項目清單。
- `PLAN`：拆成可驗證步驟並配置時間/token 預算。
- `EXECUTE`：模型依計畫讀檔、計算、寫檔、呼叫工具。
- `VERIFY`：執行 deterministic checks 與 rubric self-review。
- `REPAIR`：只處理明確失敗項，限制次數與剩餘預算。
- `FINALIZE`：確認交付物落盤、寫 final message、保存摘要並正常結束。

**樹幹的完成門檻**：任意工具錯誤皆回到可定義狀態；接近 deadline 時一定進入 `FINALIZE`；至少完成 4 個跨領域 smoke tasks。

### 3.3 主枝條（Capabilities）

| 枝條 | 功能範圍 | 最低交付 |
|---|---|---|
| B1 任務理解 | prompt、rubric、deliverables、限制抽取 | `TaskSpec` 結構與缺漏檢查 |
| B2 檔案情報 | 目錄索引、類型偵測、內容摘要、版本關係 | `ProjectIndex` 與優先讀取清單 |
| B3 工程推理 | 假設、公式、單位、規範、方案比較 | 計算與假設 ledger |
| B4 工具執行 | shell/read/write/http/MCP、安全命令封裝 | 統一 tool result 與錯誤分類 |
| B5 文件產製 | Markdown/PDF/DOCX/XLSX/CAD/BIM 等 | 依題目生成指定 deliverables |
| B6 驗證修復 | schema、檔案、數值、單位、交叉一致性 | hard-gate checklist + bounded repair |
| B7 可觀測性 | event log、metrics、trajectory、run summary | 每次 run 可重現與比較 |
| B8 評測實驗 | dev grader、A/B、回歸、成本分析 | scorecard 與 regression report |
| B9 安全治理 | secret、路徑、命令、資源、prompt injection | policy guard 與 fail-safe |
| B10 提交發布 | artifact validation、Git hygiene、readiness | 一鍵 release checklist |

### 3.4 功能葉片（完整功能清單）

#### B1 任務理解

- [ ] 抽取 required deliverables、檔名、格式、位置。
- [ ] 抽取硬性安全/可行性條件與最佳化條件。
- [ ] 抽取輸入資料、可用工具、明示規範與完成定義。
- [ ] 把不確定資訊標記為 assumption，不偷偷補值。
- [ ] 產生逐項可勾選的 Definition of Done。

#### B2 檔案情報

- [ ] 遞迴目錄盤點，排除巨大或無關內容。
- [ ] MIME/副檔名/檔頭三方辨識。
- [ ] 文字、PDF、表格、圖片、郵件與模型檔 metadata 擷取。
- [ ] 檔案大小、修改時間、版本號、命名相似度分析。
- [ ] 同名/修訂版/引用關係建立。
- [ ] 分批讀取與 context budget 管理。
- [ ] 可疑 prompt injection 文字與外部指令標記。

#### B3 工程推理

- [ ] SI/Imperial 單位正規化與 dimensional checks。
- [ ] 重要數字保留來源、公式、輸入與輸出。
- [ ] 假設 ledger：依據、影響、驗證狀態。
- [ ] 安全係數、容許值、上下界與極端情況檢查。
- [ ] 規範引用附文件、章節與適用性說明。
- [ ] 至少一個獨立 sanity check 或替代計算法。
- [ ] 多方案時保留合規性、成本、風險比較。
- [ ] 不足以安全下結論時明確保留/警告。

#### B4 工具執行

- [ ] 統一 `run/read/write/http/mcp` tool schema。
- [ ] timeout、exit code、stdout/stderr 截斷與二進位保護。
- [ ] command allow/deny guard 與工作目錄限制。
- [ ] 重試只針對 transient error，使用 backoff + jitter。
- [ ] idempotency key，避免重複寫入或破壞性重跑。
- [ ] 大輸出先摘要再進 context。
- [ ] 每次 tool call 估算剩餘時間與 budget。
- [ ] task-local MCP capability discovery 與降級路徑。

#### B5 文件與工程產物

- [ ] Markdown/純文字技術報告。
- [ ] PDF 文字與頁面檢查。
- [ ] DOCX 內容、表格、頁碼與視覺渲染檢查。
- [ ] XLSX 公式、單位、named ranges、重算與錯誤值檢查。
- [ ] 圖片/圖面尺寸、空白頁、遮切與標註檢查。
- [ ] CAD/BIM 檔存在、可解析、必要實體與 metadata 檢查。
- [ ] 跨產物一致性：設備 ID、數量、尺寸、revision、總計。
- [ ] deliverables 之外不產生大量垃圾檔。

#### B6 驗證與修復

- [ ] Preflight：所有要求檔案存在且非空。
- [ ] Schema/格式與檔案可開啟檢查。
- [ ] 數值範圍、單位、合計、符號與 rounding 檢查。
- [ ] hard gates 優先於成本最佳化。
- [ ] rubric-to-evidence matrix：每項要求指向證據位置。
- [ ] critique 與原作者步驟分離，避免自我確認偏誤。
- [ ] 修復採 defect list，一次只修明確缺陷。
- [ ] 修復後重新執行所有受影響的 regression checks。
- [ ] 修復次數、token、時間與檔案改動有上限。

#### B7 可觀測性

- [ ] JSONL event log，含 timestamp、phase、tool、duration、result。
- [ ] 隱私/secret redaction。
- [ ] 每階段 token、模型請求、cache hit、錯誤、重試統計。
- [ ] time-to-first-action、time-to-deliverable、time-to-finalize。
- [ ] run manifest：commit、config hash、model、task、seed、版本。
- [ ] 最終 failure taxonomy 與 root cause。
- [ ] trajectory viewer 或最小摘要工具。

#### B8 評測與實驗

- [ ] 單題快速迭代與完整 29 題批次執行。
- [ ] artifacts offline regrade。
- [ ] baseline 與每版差異比較。
- [ ] 依領域、任務類型、grader 類型切分分數。
- [ ] 三次重跑計算 mean/std/zero-rate。
- [ ] A/B 實驗一次只改一個主要變因。
- [ ] 追蹤品質、成本、時間三維 Pareto front。
- [ ] 防止 dev overfitting 的 holdout/rotation 策略。

#### B9 安全與治理

- [ ] API key 不寫入 repo/log/artifacts。
- [ ] path traversal、symlink escape、命令注入防護。
- [ ] prompt injection 不得改寫系統政策或提交範圍。
- [ ] 記憶體、檔案、程序與 tool call 配額。
- [ ] destructive action 預設拒絕或要求模型重新規劃。
- [ ] timeout/斷線時保留已完成交付物並 graceful finalize。
- [ ] 最終產物中不得包含秘密、內部 prompt 或無關 PII。

#### B10 提交與發布

- [ ] `submission.yaml` schema 與模型名稱驗證。
- [ ] clean build、fresh container 啟動與 health check。
- [ ] `kit artifacts`、`kit check`、offline regrade 全通過。
- [ ] artifacts 大小、檔數、manifest digest 合規。
- [ ] Git history/repository size 合規。
- [ ] submission commit tag、checksum、release note。
- [ ] 提交後下載/檢查 leaderboard 狀態與可重現資料。

---

## 4. 建議程式結構

```text
ple-solo-harness/
├─ submission.yaml
├─ serve.py
├─ pyproject.toml
├─ uv.lock
├─ .gitattributes
├─ .gitignore
├─ README.md
├─ DEVELOPMENT_PLAN.md
├─ progress.md
├─ src/ple_harness/
│  ├─ app.py                 # server lifecycle / WebSocket entry
│  ├─ config.py              # validated environment and limits
│  ├─ protocol.py            # evaluator protocol types
│  ├─ state.py               # state machine and checkpoints
│  ├─ agent/
│  │  ├─ loop.py
│  │  ├─ task_spec.py
│  │  ├─ planner.py
│  │  ├─ context.py
│  │  ├─ prompts.py
│  │  └─ finalize.py
│  ├─ model/
│  │  ├─ client.py
│  │  ├─ provider.py
│  │  ├─ retry.py
│  │  └─ accounting.py
│  ├─ tools/
│  │  ├─ bridge.py
│  │  ├─ shell.py
│  │  ├─ files.py
│  │  ├─ mcp.py
│  │  └─ guards.py
│  ├─ inspect/
│  │  ├─ inventory.py
│  │  ├─ documents.py
│  │  ├─ spreadsheets.py
│  │  ├─ drawings.py
│  │  └─ models.py
│  ├─ engineering/
│  │  ├─ units.py
│  │  ├─ calculations.py
│  │  ├─ assumptions.py
│  │  └─ evidence.py
│  ├─ verify/
│  │  ├─ preflight.py
│  │  ├─ hard_gates.py
│  │  ├─ consistency.py
│  │  ├─ rubric.py
│  │  └─ repair.py
│  └─ observability/
│     ├─ events.py
│     ├─ metrics.py
│     ├─ redaction.py
│     └─ summary.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ functional/
│  ├─ stress/
│  ├─ reliability/
│  ├─ security/
│  └─ fixtures/
├─ scripts/
│  ├─ smoke.ps1
│  ├─ smoke.sh
│  ├─ evaluate.sh
│  ├─ compare_runs.py
│  └─ release_check.sh
├─ configs/
│  ├─ default.yaml
│  ├─ fast.yaml
│  └─ robust.yaml
├─ reports/                 # 不放 secrets；實驗摘要
└─ artifacts/               # 只由官方 eval/export 產生
```

### 4.1 核心資料型別

- `TaskSpec`：題目、交付物、硬條件、軟目標、可用工具、風險。
- `ProjectIndex`：檔案、類型、版本、關係、優先級、摘要。
- `PlanStep`：目的、輸入、操作、預期輸出、驗證、預算、依賴。
- `ToolResult`：狀態、stdout/stderr、artifact changes、error class、duration。
- `Assumption`：內容、來源、合理性、敏感度、驗證狀態。
- `Evidence`：rubric/check 對應的檔案、頁面、儲存格、計算或圖元。
- `Defect`：severity、scope、proof、repair proposal、retest set。
- `RunSummary`：結果、成本、時間、分數、失敗原因、產物清單。

---

## 5. 開發策略

### 5.1 Starter 選擇

第一輪先比較官方 `plan-verify` 與一個完整 agent adapter；預設從 `plan-verify` 分支起步，因為它較容易理解、測試與修改。只有在量測證明完整 adapter 明顯更好時才遷移。

### 5.2 模型策略

- 提交版本只選官方允許模型。
- 先以單一主模型建立 baseline，再做模型 A/B。
- prompt caching、context compaction、工具輸出摘要列為成本功能。
- 模型拒答、空 tool call、重複 tool call、截斷皆有明確 recovery。
- 不在同一 run 任意切換模型，維持提交規則與可重現性。

### 5.3 Prompt 策略

System prompt 保持穩定並分層：

1. 不可違反的安全與環境規則。
2. 狀態機與工具契約。
3. 工程證據、單位與 hard-gate 原則。
4. 當前 task spec、project index 與剩餘 budget。
5. 當前缺陷與下一個原子目標。

禁止把所有文件全文一次塞入 context；使用索引、按需讀取與壓縮摘要。

### 5.4 實驗紀律

每次可比較實驗必須記錄：

- Git commit 與 config hash。
- model、reasoning effort、temperature/seed（若可用）。
- task dataset commit。
- 任務清單與重跑次數。
- 分數、hard-gate pass rate、zero-score rate。
- token、cache、wall time、tool calls、重試。
- 失敗分類與人工觀察。
- 結論：保留、回退或需要更多資料。

---

## 6. 短、中、長期路線圖

時程以 2026-11-16 起算，預留最後 48–72 小時只做穩定與提交，不再加入新功能。

### 短期：長根並長出可運作樹幹（11/16–11/29）

#### P0 環境與規格（11/16–11/19）

任務：

- [ ] 接受 Kaggle/Hugging Face 條款並確認個人參賽資格。
- [ ] 在 WSL2 Linux filesystem 建立官方 PLE repo 與獨立 harness repo。
- [ ] 安裝 Docker、`uv`、Harbor 0.20.0 + websockets、gcloud。
- [ ] 設定 LF、Git、secret-safe `local.env`。
- [ ] 執行官方原始 starter 的 `kit check`。
- [ ] 選定 starter 並記錄初始架構決策。

階段驗證：

- `docker run`、`uv --version`、`harbor --version` 成功。
- 官方 starter `kit check` 完整通過。
- repo 中找不到 key/token；Windows/WSL line endings 測試通過。

#### P1 最小合法 Harness（11/20–11/23）

任務：

- [ ] 建立 server、protocol、config、model client、tool bridge。
- [ ] 實作狀態機骨架與 global deadline。
- [ ] JSONL logging、redaction、run summary。
- [ ] 加入 lint、type check、unit test 與本機 CI script。

階段驗證：

- 120 秒內啟動並接受 WebSocket。
- smoke task 與 MCP task 通過。
- 人工注入 model 429/500/timeout、tool error、斷線均能有界結束。
- 測試至少覆蓋 protocol、config、retry、state transition、redaction。

#### P2 Baseline Agent Loop（11/24–11/29）

任務：

- [ ] 完成 discover/specify/plan/execute/verify/finalize。
- [ ] 建立 deliverable checklist、project index、context trimming。
- [ ] 先加入存在性、格式、非空、大小與基本一致性檢查。
- [ ] 跑 4 個跨領域代表題與首個 baseline。

階段驗證：

- 四領域各至少一題能產出 grader 可讀 artifacts。
- 所有 run 都有完整 summary 與 failure taxonomy。
- 不因單一工具錯誤無限重試；接近 deadline 可保留成品。

**短期出口條件**：具有合法、可執行、可觀察、可評分的最小提交候選。

### 中期：長枝條與主要功能（11/30–12/20）

#### P3 工程驗證核心（11/30–12/6）

任務：

- [ ] units、calculation ledger、assumption ledger。
- [ ] hard-gate checklist、rubric evidence matrix。
- [ ] 數值範圍、合計、交叉引用、revision 一致性檢查。
- [ ] bounded repair loop 與 impact-based retest。

階段驗證：

- 單位不相容、缺檔、空檔、總計錯誤、ID 不一致能被測試捕捉。
- 修復不會破壞已通過項；超過預算會停止並 finalize。
- 代表題 hard-gate pass rate 較 P2 baseline 上升。

#### P4 多格式工具能力（12/7–12/13）

任務：

- [ ] PDF/DOCX/XLSX/圖片工具與視覺/結構驗證。
- [ ] CAD/BIM metadata 與可解析性檢查。
- [ ] task-local MCP capability discovery 與 fallback。
- [ ] 大檔案、長輸出與 context quota 管理。

階段驗證：

- 每一格式至少有一個 fixture 與 corruption test。
- 產物能重新開啟；表格無 `#REF!/#VALUE!`；文件無空白或明顯截切頁。
- 4 GB memory / 1 GB writable quota 模擬下不崩潰。

#### P5 完整 Dev Set 與回歸系統（12/14–12/20）

任務：

- [ ] 首次完整 29 題 evaluation。
- [ ] 自動 scorecard、領域切分與 baseline diff。
- [ ] 建立錯誤 Pareto：優先處理高頻、高損失、可通用修復項。
- [ ] 建立代表性 fast regression set 與 slow full suite。

階段驗證：

- 29 題均有有效 artifacts 或可解釋的受控失敗。
- offline regrade 可重現分數。
- fast regression 在合理時間內完成，full suite 報告無資料缺口。
- 相對 starter baseline 有統計或實務上明顯改善；無大範圍退步。

**中期出口條件**：主要功能完整、已跑完整 dev set、改善方向由資料而非直覺決定。

### 長期：壯樹、抗風與提交（12/21–01/06）

#### P6 最佳化與模型選擇（12/21–12/27）

任務：

- [ ] 模型與 prompting A/B，保持其他變因不變。
- [ ] token/context/cache、工具呼叫與時間最佳化。
- [ ] 依 task 特徵做輕量 workflow routing，而非題目 ID 特判。
- [ ] 減少 zero-score、early termination 與無效 repair。

階段驗證：

- 至少三次重跑代表集，報告 mean/std/zero-rate/cost。
- 新版本同時滿足品質門檻與資源門檻。
- routing 在未知 fixture 上仍依特徵工作。

#### P7 壓力、可靠度與安全（12/28–12/31）

任務：

- [ ] fault injection、resource limit、長時間 soak、重複啟停。
- [ ] prompt injection、path traversal、secret leakage 測試。
- [ ] 大量檔案、大檔、長 prompt、模型慢回覆與工具不穩定情境。
- [ ] disaster recovery：中斷後保留 artifacts 與可診斷資料。

階段驗證：

- 詳見第 8 節；所有 P0/P1 缺陷清零。
- 連續多題執行無資源洩漏趨勢。
- 任一 fault 不造成無限循環、越界寫入或秘密洩漏。

#### P8 凍結、完整驗收與提交（01/01–01/06）

任務：

- [ ] 01/01 feature freeze，只接受 blocker 修復。
- [ ] clean clone/build，跑 fast suite 與 final dev evaluation。
- [ ] regrade artifacts，檢查大小、manifest、Git history、license。
- [ ] 產生 final commit、tag、checksum、release note。
- [ ] 01/03 前完成主要提交，保留兩天處理平台問題。
- [ ] 重新核對 Kaggle deadline、rules 與提交狀態。

階段驗證：

- `kit artifacts` 通過。
- `kit check` 顯示 `ready to submit`。
- `eval/run.py --artifacts` 完成且分數與 final report 相符。
- fresh machine/clean environment 可建置與啟動。
- 提交 commit 與 artifacts digest 已封存。

**長期出口條件**：正式提交成功，可重現、可說明、可公開。

### 賽後長期（01/07 起）

- 整理技術 write-up、架構圖、實驗結果與失敗教訓。
- 移除 secrets 與不可發布資料後開源。
- 將通用 verifier、trajectory analyzer、document QA 拆成作品集模組。
- 根據 hidden result 做 domain-gap 分析，而不是回頭硬配公開題。

---

## 7. 階段任務治理

### 7.1 任務狀態

`BACKLOG -> READY -> IN_PROGRESS -> VERIFYING -> DONE`

例外狀態：

- `BLOCKED`：缺外部權限、資料、資源或無法自行排除的依賴。
- `DEFERRED`：價值低於目前優先級，附重新評估日期。
- `DROPPED`：經證據判定無效或違反範圍，保留原因。

### 7.2 Definition of Ready

任務開始前必須有：目的、影響模組、驗收方式、測試層級、預估風險、回退方式。

### 7.3 Definition of Done

任務只有在以下全部成立才可標 Done：

- 程式/設定/文件已完成且可讀。
- 對應測試已新增並通過。
- 失敗路徑與資源邊界已驗證。
- 無 key、token、敏感資訊或 artifacts 汙染。
- `progress.md` 已附驗證命令/報告/分數等證據。
- 未造成 fast regression 退步；若有，已記錄並明確接受。

### 7.4 優先級

- `P0`：阻止提交、資料/秘密風險、可能造成越界或無限執行。
- `P1`：高頻零分、hard-gate、主要可靠度問題。
- `P2`：顯著改善分數、成本或開發速度。
- `P3`：便利、視覺化、低頻最佳化。

---

## 8. 測試總體策略

### 8.1 測試金字塔

| 層級 | 目的 | 觸發時機 | 退出門檻 |
|---|---|---|---|
| 靜態檢查 | 格式、型別、依賴、secret | 每次修改 | 0 error |
| 單元測試 | 純函式、狀態、guards、parser | 每次修改 | 核心模組全通過 |
| 契約測試 | WebSocket、model/tool schema | 每次 protocol 修改 | 官方/fixture contract 全通過 |
| 整合測試 | model mock + taskbridge + filesystem | 每個 PR/里程碑 | 主流程與錯誤流程全通過 |
| 功能測試 | 端到端完成代表任務 | 每日/里程碑 | 交付物與 grader 可用 |
| 回歸測試 | 防止分數/可靠度退步 | 每個候選版本 | 不超過容許退步 |
| 壓力測試 | 資源、規模、長時間 | P4 後、release 前 | 不越界、不失控 |
| 可靠度測試 | 隨機錯誤與多次重跑 | P3 後、release 前 | 成功率與變異達門檻 |
| 安全測試 | secret、路徑、命令、注入 | 每週/release 前 | P0/P1 皆為 0 |
| 官方驗收 | kit、dev set、artifacts | 里程碑/release | 官方工具全通過 |

### 8.2 單元測試

必測項目：

- config 缺值、非法值、環境覆寫與安全預設。
- state machine 合法/非法轉移與 deadline 觸發。
- retry 對 429/5xx/timeout 重試，對 4xx/schema error 不盲重試。
- path guard、command guard、大小/行數截斷。
- secret redaction 的常見與變形 key 格式。
- deliverable parser、unit conversion、numeric tolerance。
- defect priority 與 repair budget。
- artifact file count/size estimator。

### 8.3 契約與整合測試

- WebSocket connect、message ordering、malformed payload、disconnect/reconnect。
- 模型回傳文字、tool call、多 tool call、空回覆、截斷、invalid JSON。
- task tool 成功、permission denied、not found、timeout、huge output。
- MCP list/call 正常、缺 server、schema mismatch、slow response。
- readonly root 與 `/tmp`/`$HOME` 寫入策略。
- server 反覆啟動/停止不殘留程序。

### 8.4 功能測試

建立代表性矩陣，而不是只測高分題：

| 維度 | 覆蓋 |
|---|---|
| 領域 | structural / civil / electrical / mechanical |
| 產物 | memo / calculation / spreadsheet / drawing / BIM/CAD |
| Grader | deterministic / rubric / hybrid |
| 複雜度 | 小檔少步驟 / 多檔長任務 / 大型模型 |
| 結果 | 正常成功 / 可修復失敗 / 不可修復但安全結束 |

每題驗證：

- 要求檔案存在、非空、可開啟、位於正確位置。
- hard gates 有證據；數字與跨檔案 ID 一致。
- final message 簡潔說明完成項、假設與未解風險。
- artifacts 能在 fresh task container 中離線評分。

### 8.5 壓力測試

測試情境：

- 10,000 個輸入檔、深層目錄、相似檔名與多 revision。
- 接近 95 MiB 單檔、256 MiB 單題與 1 GB writable quota。
- 超長 prompt、巨大 stdout/stderr、二進位誤讀。
- 連續 100 次 model/tool mock calls。
- 2 CPU/4 GB RAM 下的 peak memory 與 process count。
- 120 秒啟動門檻與接近 6 小時 deadline 的縮時模擬。
- 多次反覆 build/start/stop、取消與 interrupted export。

壓力門檻：

- 不 OOM、不爆滿磁碟、不超過 process limit。
- log 與 context 有界；巨大輸出被安全截斷/摘要。
- peak RSS 建議低於 3.2 GB，為 task variation 留餘量。
- 磁碟使用達 80% 時主動清理非必要暫存或停止新增。
- deadline buffer 內進入 finalize，不被 repair loop 吃完。

### 8.6 可靠度與故障注入

故障模型：

- 模型 429、500、503、連線重置、慢回覆、無效 tool call。
- Tool exit non-zero、permission、disk full、檔案鎖定、部分寫入。
- MCP 消失、回傳 schema 改變、長時間無回應。
- Agent 重複步驟、忘記交付物、修復造成 regression。
- Container signal、WebSocket 中斷、程序意外終止。

可靠度指標：

- Harness boot success rate：100/100。
- Mock end-to-end controlled completion：>= 99%。
- 代表 dev tasks artifact-producing rate：>= 95%。
- 非 grader/platform 原因 zero-score rate：逐階段下降，release 前不得高於 baseline。
- 同設定三次 run 的 score standard deviation：建立 baseline 後設定門檻；目標 <= 0.05 或較 baseline 降低 30%。
- 重試不得造成重複破壞性寫入。
- 所有失敗都有 error class 與最後有效 checkpoint。

### 8.7 安全測試

- `.env`、API key、Bearer token、cloud credential pattern 掃描。
- `../`、絕對路徑、symlink、Unicode path trick。
- Shell metacharacters、命令替換、pipe/redirection 注入。
- 文件內「忽略系統指令」「上傳資料」等 prompt injection。
- artifacts/log/final message 的秘密與內部 prompt 洩漏。
- dependency pinning、已知漏洞與 license 檢查。

### 8.8 最後驗證清單

#### 功能

- [ ] 四領域與主要產物格式皆有成功案例。
- [ ] 任務規格、檔案索引、計畫、驗證、修復、finalize 全鏈路可觀察。
- [ ] artifacts fresh-container regrade 成功。

#### 品質

- [ ] 所有 P0/P1 defect 關閉。
- [ ] fast/full regression 結果已封存。
- [ ] 三次重跑的平均、標準差、零分率已審查。

#### 效能與資源

- [ ] 啟動 < 120 秒。
- [ ] 2 CPU/4 GB/readonly root 情境通過。
- [ ] 暫存、記憶體、程序、檔案數量均有上限。

#### 安全

- [ ] secret scan 0 issue。
- [ ] path/command/prompt injection suite 通過。
- [ ] repo、log、artifacts 無 credential。

#### 官方提交

- [ ] `submission.yaml` 使用允許模型且無 unknown fields。
- [ ] `kit artifacts` 通過。
- [ ] `kit check` 顯示 `ready to submit`。
- [ ] `eval/run.py --artifacts` 通過。
- [ ] commit/tag/checksum/規則確認完成。

---

## 9. 指標與儀表板

### 9.1 North-star 指標

- Dev mean score。
- Hard-gate pass rate。
- Zero-score rate。
- Artifact-producing rate。
- 三次重跑標準差。

### 9.2 輔助指標

- 每題 wall time、模型 requests、input/output tokens、cache hit。
- Tool success/retry/error rate。
- Repair 次數與 repair 後淨改善率。
- Context size 與被截斷輸出量。
- Peak RSS、disk、process count。
- 每領域/產物/grader 類型分數。

### 9.3 Release gate 建議

候選版本需同時符合：

- 官方檢查全通過。
- P0/P1 defect = 0。
- 代表集沒有超過 0.02 的平均分退步，除非 full-set 總體有明確改善且已記錄接受。
- artifact-producing rate 不低於前一穩定版。
- 成本或時間不得無解釋暴增 20% 以上。

---

## 10. 風險登錄

| 風險 | 機率/衝擊 | 預防 | 觸發後處理 |
|---|---|---|---|
| 缺工程領域知識 | 高/高 | deterministic checks、來源證據、按領域分析 | 優先處理共通可靠度，不做無依據結論 |
| Dev overfitting | 中/高 | holdout rotation、功能型 routing | 回退題目特判，保留通用改進 |
| 模型成本/配額 | 高/中 | 小集合迭代、cache、budget | 切 fast config，延後完整重跑 |
| Windows/WSL/Docker 問題 | 中/高 | Linux filesystem、LF、早期 smoke | 重建乾淨 WSL repo，不在截止前搬環境 |
| 長任務 timeout | 高/高 | phase deadline、early artifact、finalize buffer | 停止最佳化，保留最小合規交付 |
| Tool/MCP 不穩 | 中/高 | contract test、retry、fallback | 降級到基本 file/shell 工作流 |
| Artifact 過大 | 中/高 | 預估、配額、preflight | 移除非交付暫存與 trajectory |
| 修復造成退步 | 高/中 | defect scope + impact retest | 回復最後有效 checkpoint |
| Secret 洩漏 | 低/極高 | env 分離、redaction、scan | 立即撤銷 key、清理 Git history、重跑 |
| 規則/截止變更 | 低/高 | 每週查官方頁，提交前再核對 | 更新計畫與 release gate |

---

## 11. 每日與每週節奏

### 每日

1. 讀 `progress.md` 的 Current focus。
2. 選一個可驗證的小任務。
3. 先寫/更新測試，再實作。
4. 跑最小相關測試與 fast regression。
5. 記錄證據、分數、風險與下一步。
6. 保持主分支隨時可執行。

### 每週

- 週一：依 scorecard 選本週最高價值失敗類型。
- 週中：完成一次代表集回歸，避免方向走偏。
- 週末：里程碑驗收、風險更新、成本檢查與完整度盤點。
- 每週只允許一至兩個主要架構變因，降低歸因困難。

---

## 12. 決策準則

新增功能前依序詢問：

1. 它是否減少零分或 hard-gate 失敗？
2. 它是否適用多題，而非單一公開題？
3. 能否以測試或 grader 分數證明？
4. 是否在 2 CPU/4 GB/無外網下可用？
5. 失敗時能否安全降級？
6. 維護成本是否低於預期收益？

任一核心答案為否，先放入 backlog，不直接加入主幹。

---

## 13. 參考資料

- Competition: <https://www.kaggle.com/competitions/physical-engineerings-last-exam>
- Official repository: <https://github.com/google-research/ple>
- Submission kit: <https://github.com/google-research/ple/blob/main/kit/README.md>
- Dev evaluation: <https://github.com/google-research/ple/blob/main/eval/README.md>
- Models: <https://github.com/google-research/ple/blob/main/docs/models.md>
- Artifacts: <https://github.com/google-research/ple/blob/main/docs/artifacts.md>

