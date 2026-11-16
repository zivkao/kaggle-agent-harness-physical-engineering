# Setup Guide

## 1. 已準備內容

- Google 官方 PLE repo：`../ple-reference/`
- 官方 `plan-verify` starter：本目錄的 `serve.py`、`taskbridge.py`、`submission.yaml` 與 `requirements.txt`
- 官方 Apache 2.0 `LICENSE`
- LF line-ending 設定 `.gitattributes`
- 開發書、進度表與 vibe coding prompt
- 29 題 dev dataset，Windows 壓縮包位於 `../ple-data/ple-data.tar.gz`，WSL2 已解壓至 `~/projects/ple-data/tasks`

## 2. 目前環境快照（2026-11-16）

| 項目 | 狀態 |
|---|---|
| WSL | Ubuntu 24.04 可用 |
| Docker | WSL 內 `docker info` 通過 |
| uv、Harbor | WSL PATH 未偵測 |
| gcloud | WSL PATH 已偵測，模型代理與憑證待驗證 |
| WSL 工作副本 | `~/projects/ple-reference` 與 `~/projects/ple-solo-harness` 待建立 |
| 資料 | WSL 內 29 題 SHA-256 符合官方清單 |

官方建議在 WSL2 Linux filesystem 中執行，不要直接從 `/mnt/d` 跑 evaluation。建議最終結構：

```text
~/projects/
├─ ple-reference/
├─ ple-data/tasks/
└─ ple-solo-harness/
```

## 3. 帳號與模型設定

- Kaggle 參賽規則已接受。正式提交前完成 Kaggle 要求的身分驗證。
- Hugging Face 資料已取得。使用 `--tasks-dir` 時直接讀取本機題目。
- 選定本機模型路徑。沿用 starter 的 Google-sponsored 設定時，依官方模型文件配置本機代理。官方也支援本機測試用的自有模型。須經使用者同意才啟用計費或開始可能扣費的 run。

## 4. WSL2 安裝與搬移

在 WSL2 shell 執行；實際 Windows 掛載路徑可依環境調整：

```bash
mkdir -p ~/projects
test -e ~/projects/ple-reference || cp -a /mnt/d/project/vide-coding/ple-reference ~/projects/
test -e ~/projects/ple-solo-harness || cp -a /mnt/d/project/vide-coding/ple-solo-harness ~/projects/
cd ~/projects/ple-solo-harness
git config core.autocrlf input
git config core.symlinks true
```

檢查 Windows 複製過來的 Git tracked symlink 是否真的存在。若官方 repo 含未正確還原的 symlink，在 WSL 建立新副本並核對 commit。

安裝 `uv` 與 Harbor：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install harbor==0.20.0 --with websockets
```

確認工具：

```bash
docker version
uv --version
harbor --version
gcloud --version
```

## 5. Secrets

實際 `local.env` 應放在 `~/projects/`，即兩個 repo 外，不要 commit：

```bash
MODEL_PROXY_URL=http://localhost:4000
MODEL_PROXY_KEY=<locally-generated-random-key>
```

請勿把真實 token 貼進聊天、程式、`progress.md`、log 或 artifacts。

## 6. 啟動本機模型代理

```bash
gcloud auth application-default login
export VERTEXAI_PROJECT=<your-gcp-project>
export MODEL_PROXY_KEY=$(openssl rand -hex 24)
cd ~/projects/ple-reference
kit/model_proxy/start.sh
```

將相同的 `MODEL_PROXY_KEY` 與 `MODEL_PROXY_URL` 放入 repo 外的 `local.env`。

## 7. 第一輪官方檢查

另開 WSL2 shell：

```bash
cd ~/projects/ple-reference
uv run python -m kit check ../ple-solo-harness --env-file ../local.env
```

`plan-verify` 原始 starter 不會呼叫 task MCP，官方檢查可能在 MCP 階段提出 warning；P1/P2 會處理這項能力。

## 8. 執行已下載的公開 dev tasks

先跑一題 deterministic grader 的 baseline，將產物放在實驗 run 目錄：

```bash
cd ~/projects/ple-reference
uv run python eval/run.py ../ple-solo-harness \
  --env-file ../local.env \
  --tasks-dir "$HOME/projects/ple-data/tasks" \
  --tasks frame-extension-method \
  --no-export
```

確認單題流程後，才執行全部 29 題：

```bash
uv run python eval/run.py ../ple-solo-harness \
  --env-file ../local.env \
  --tasks-dir "$HOME/projects/ple-data/tasks"
```

## 9. 重要安全規則

- `artifacts/` 只能由官方 evaluation/export 產生。
- 不把 `local.env`、tokens、credentials 加入 Git。
- 不讓 harness 讀自己的 artifacts。
- 不在 dev task ID 上寫 hard-coded 解法。
- 每次功能變更都更新 `progress.md` 並留下測試證據。

