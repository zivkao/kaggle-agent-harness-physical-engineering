# Vibe Coding 啟動 Prompt

把「Prompt 本文」貼給 Coding Agent。第一次可從 `D:\project\vide-coding` 啟動。建立 WSL2 工作副本後，將開發工作目錄切換到 `~/projects/ple-solo-harness`。

---

## Prompt 本文

協助我單人參加 Google Physical-Engineering’s Last Exam（PLE）Kaggle 競賽。以現有的官方 `plan-verify` starter 開發可重現、可測試的 harness。第一回合從 P0 環境與單題基準開始。

### 已驗證的起點

- Windows 工作區是 `D:\project\vide-coding`。官方工具在 `ple-reference`，參賽程式與文件在 `ple-solo-harness`。
- Ubuntu 24.04 的 `~/projects/ple-data/tasks` 已有 29 題，33,410 個檔案，release `0.4.6`。每題 SHA-256 均與官方 `dev_set.yaml` 相符。評測時使用 `--tasks-dir "$HOME/projects/ple-data/tasks"`。保留現有已驗證資料。
- Ubuntu 裡的 `docker info` 已通過，Git 和 gcloud 已在 PATH。兩個 Git repo 的 Linux 工作副本待準備，uv、Harbor 和本機模型連線待驗證。
- Kaggle 已加入，身分驗證留待正式提交前完成。現有本機資料足以開始開發與評測環境設定。

### 一、先建立正確上下文

開始任何修改前，必須完整閱讀：

1. `README.md`
2. `DEVELOPMENT_PLAN.md`
3. `progress.md`
4. `SETUP.md`
5. `docs/STARTER_PLAN_VERIFY.md`
6. `submission.yaml`
7. `serve.py`
8. `taskbridge.py`
9. 上層 `../ple-reference/README.md`
10. 與當前工作直接相關的官方 `../ple-reference/kit/README.md`、`eval/README.md`、`docs/models.md`、`docs/artifacts.md`、`docs/protocol.md`

閱讀後用簡短條列回報目前階段、剩餘條件與本回合驗收目標，接著執行。若文件中的環境快照與現況不同，以本回合命令的結果為準。

### 二、總目標與優先順序

總目標是完成一個合法、可重現、跨題穩健且具有競爭力的 PLE harness。優先順序固定為：

1. 規則、安全與 secrets。
2. 能建置、啟動、完成任務並留下合法 artifacts。
3. Hard safety/feasibility gates。
4. 可靠度、可恢復性與可觀測性。
5. Dev score。
6. 成本與速度最佳化。
7. 便利性與額外功能。

以能重現的基準結果為起點，逐步改善完成率、評分與成本。

### 三、工作方式

- 以 `progress.md` 的 Current focus 和下一個未完成階段任務為工作佇列。
- 一次只完成一個可驗證的小目標；不要一次實作 P1–P8。
- 開始前寫出 acceptance criteria 與最小測試集合。
- 優先修改現有官方 `plan-verify` starter，不無理由整套重寫。
- 每個功能都必須有正常路徑、失敗路徑、資源邊界與安全降級。
- 對不確定資訊先檢查官方文件或程式，不猜測 protocol、limits 或 model API。
- 工程數值優先使用 deterministic code 驗證；LLM 用於規劃、解讀、整合與修復。
- 不因公開 task ID 寫特判，不讀 harness 自身 artifacts，不使用評測時不存在的外網。
- 不把任何 API key、token 或 credential 寫入 repo、log、測試 fixture、progress 或 artifacts。
- 保留使用者既有變更；修改前檢查 Git diff。
- 若需要付費 API、登入、接受條款或其他使用者權限，停在安全邊界，明確列出一個最小操作要求，不索取真實 secret。

### 四、架構方向

維持一個可觀察、可有界恢復的主流程：

```text
BOOT -> DISCOVER -> SPECIFY -> PLAN -> EXECUTE -> VERIFY
     -> bounded REPAIR -> FINALIZE
```

重要能力逐步加入：

- task/deliverable/hard-gate 規格抽取。
- project file inventory 與按需讀取。
- 統一 model/tool/MCP adapter 與錯誤分類。
- global deadline、phase budget、retry/backoff、graceful finalize。
- assumption/calculation/evidence ledger。
- deliverable preflight、格式、單位、數值與跨檔案一致性檢查。
- defect-driven bounded repair 與 impact-based retest。
- JSONL events、redaction、run summary 與可比較 metrics。
- artifact size/file-count/secret/readability checks。

不要提早導入多 Agent；只有數據證明它比單 Agent state machine 更好時才提出 ADR。

### 五、測試要求

每次改動至少執行最小相關測試；完成里程碑時依 `DEVELOPMENT_PLAN.md` 執行完整階段驗證。測試層級包括：

- lint/type/static/secret scan。
- unit tests。
- WebSocket、model、tool、MCP contract tests。
- integration 與代表任務 functional tests。
- regression、stress、fault injection、reliability、安全測試。
- 官方 `kit artifacts`、`kit check` 與 offline regrade。

測試不得只驗 happy path。至少考慮：429/5xx/timeout、invalid tool call、巨大輸出、permission denied、disk quota、部分寫入、WebSocket 中斷、deadline 與修復造成 regression。

### 六、每回合交付格式

每次工作結束前必須：

1. 說明實際完成的結果。
2. 列出修改檔案及關鍵決策。
3. 列出執行過的驗證命令、通過/失敗結果與未執行原因。
4. 更新 `progress.md`：任務狀態、驗證證據、測試表、實驗/缺陷/風險/決策。
5. 顯示剩餘風險與下一個最小任務。
6. 不把未驗證工作宣稱為完成。

### 七、第一回合的可執行任務

1. 用 Windows 工作區的來源準備 `~/projects/ple-reference` 與 `~/projects/ple-solo-harness`。先檢查兩個目錄及 Git 狀態；若已有工作副本，保留既有內容。檢查 Git symlinks、LF 設定、Linux 路徑及 starter 與官方來源的差異。
2. 依 `SETUP.md` 確認 WSL 的 Docker、uv 與相容的 Harbor。完成可執行的安裝、靜態檢查與設定，並確認本機模型端點是否可用。沿用既有可用設定。計費、登入或其他需要我操作的項目，做完其餘步驟後再列出具體操作。
3. 具備模型條件後，從 `~/projects/ple-reference` 執行下面的 smoke check。保留各階段結果，包括 starter 可能出現的 MCP warning。官方 `ready to submit` 另需合法 artifacts 與已提交的 Git 內容。
4. Smoke 成功後，再執行一個 deterministic grader 的 dev 任務，記錄 run ID、model、score、耗時、可取得的成本與產物位置。等單題流程驗證完再展開完整評測。

```bash
cd ~/projects/ple-reference
uv run python -m kit check ../ple-solo-harness --env-file ../local.env
uv run python eval/run.py ../ple-solo-harness \
  --env-file ../local.env \
  --tasks-dir "$HOME/projects/ple-data/tasks" \
  --tasks frame-extension-method \
  --no-export
```

命令以 repo 外的 `../local.env` 為例。若採用另一個受支援的本機模型設定，依官方文件調整。以 `progress.md` 記錄工具版本、smoke 各階段、單題結果與待辦。基準建好後再進 P1，依開發書從最小 harness 逐步加入工程驗證、格式工具、功能測試、回歸、壓力及可靠度測試。

持續保留之後能用於 Kaggle Writeup 的實驗證據，包括架構、分數與成本，以及 dev 題失敗分類。準備正式提交時核對當時的 Kaggle 規則、Writeup 要求與官方 kit。

