# PLE Solo Harness

Google Physical-Engineering's Last Exam（PLE）單人參賽專案。

本專案採用「先長根、再長樹幹、接著枝條、最後功能葉片」的方式開發：先建立能穩定執行與驗證的最小 harness，再逐步加入工程工作流、文件工具、品質閘門與效能最佳化。

## 文件入口

- [完整開發書](DEVELOPMENT_PLAN.md)：目標、架構、功能清單、短中長期里程碑、測試與最終驗收。
- [進度追蹤](progress.md)：目前狀態、階段任務、驗證證據、決策、風險與下一步。
- [環境建置](SETUP.md)：WSL2、Docker、資料權限、模型代理與官方檢查。
- [Vibe Coding Prompt](VIBE_CODING_PROMPT.md)：貼給 Coding Agent 的完整啟動指令。
- [官方 starter 說明](docs/STARTER_PLAN_VERIFY.md)：`plan-verify` 的原始設計與時間配置。

## 當前狀態

目前為 `P0 — 規劃與環境準備`。Google 官方 repo 已下載，官方 `plan-verify` starter 已整理為本 harness 的初始程式；尚未跑通本機 `kit check`，基準分數尚未產生。

## 核心原則

1. 先能提交，再提高分數。
2. 任何功能都要有對應測試與失敗降級策略。
3. 工程計算盡可能使用 deterministic tools 驗證，LLM 負責規劃、解讀與整合。
4. 公開 dev set 用來找通用失敗模式，不針對題目硬編答案。
5. 每次實驗都保留設定、成本、軌跡、產物與評分，確保可重現。

## 建議工作位置

官方文件建議 Windows 使用 WSL2，並將 PLE 官方 repo 與本專案放在 WSL2 的 Linux 檔案系統（例如 `~/projects/`），避免 `/mnt/d` 的 symlink、CRLF 與效能問題。本目錄可保留規劃文件；實作開始前應確認是否搬移或另建 WSL2 工作副本。

## 重要日期（Asia/Taipei）

- 規劃起點：2026-11-16
- 目標提交凍結：2027-01-03 23:59
- 官方截止：2027-01-06 07:59（對應 2027-01-05 23:59 UTC；提交前仍須再核對 Kaggle）

