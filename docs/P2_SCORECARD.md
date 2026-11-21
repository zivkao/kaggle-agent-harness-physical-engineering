# P2-06 — Baseline Scorecard & Failure Taxonomy（2026-11-21）

四領域代表題、main 完整版、全部本機 Strata（R-009：分數僅供相对比较）。
資料來源＝progress.md §6 EXP-016／017 #2／018 #2／019 各列的 run 目錄與 `results.json`／`grade.json`，可重算。

## 1. Scorecard

| task | 領域 | 級（§13） | grader 族 | 交付物 | score | wall (s) | 呼叫 | in／cache／out tokens | 碼 | gate 碼 | MCP 使用 |
|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| frame-extension-method（EXP-016） | structural | heavy | checks | `submission.zip` 17,440 B／6 檔 | **0.3673** | 10,842 | 141 | 19.80M／18.80M（94.9%）／275,778 | `eb918d8` | 無（P2 基線） | 0（MCP×0） |
| eor-review-corrections（EXP-017 #2） | structural | heavy | checks-judge | `submission.zip` 23,890 B／7 檔 | **0.2573** | 17,053 | 340 | 30.58M／28.89M（94.5%）／466,255 | `eb918d8` | 無（P2 基線） | 0（MCP×0） |
| engineers-estimate-check（EXP-018 #2） | electrical | light L1 | rubric（judge） | memo docx 43,429 B | **0.1304** | 2,497 | 70 | 1.48M／1.37M（92.3%）／78,158 | `85d1cbd` | live ✓（verdict PASS、fix 0） | 0／144 tools 目錄在位 |
| emergency-spillway-check（EXP-019） | water | light L1 | rubric（judge） | memo docx 55,494 B | **0.8378** | 4,270 | 143 | 9.72M／9.47M（97.4%）／136,834 | `85d1cbd` | live ✓（verdict PASS、fix 0） | 0／141 tools 目錄在位 |

四題均值 **0.3982**（僅 4 題代表，不是 29 題 dev mean；29 題均值待 P5-01）。

## 2. Quality dashboard 首次填值（main 線代表，quick 線暫停不計）

| 指標 | 值 |
|---|---:|
| Artifact-producing rate | 4/4＝**100%**（release target ≥95%：達標，但樣本只有 4） |
| Zero-score rate | 0/4＝0%（ERR_NO_SUBMISSION 於 main 線從未出現） |
| 單題成本帶 | light：2,497–4,270 s／70–143 呼叫；heavy：10,842–17,053 s／141–340 呼叫 |
| Cache 命中 | 92.3–97.4%（`CACHE_MARK` 穩定有效） |

## 3. Failure taxonomy（量化）

| 失敗族 | 出現 | 證據 | 狀態 |
|---|---|---|---|
| ARTIFACT／零交付（DEF-001/002，quick 線） | 0/4（main）；6/6（quick，已暫停） | §6 EXP-008..015 vs 016..019 | main 線已根除；quick 待復活驗證 |
| HARD_GATE 結構性歸零 | 2/2 heavy | 016：B8 register_hard 於 31 items 全 forfeit→壓 O；017：`hard_pass_rate` 0→0.6 權重整個作廢 | **P3-03 靶心**；ADR-002 再證 |
| CALCULATION／rubric 數值 ground truth | 1.5/2 light | 018：4 條 weight-10 全錯（$5,431,000 應 $5,384,000；Sec2 $1,350,777.75 應 $1,303,717.70）＝丟 40/46 點；019：2 條 weight-3 推導／義務归屬未寫 | **P3-01/02 靶心**（單位正規化＋計算 ledger） |
| MCP meta 工具未使用 | 2/2 機會 | 018／019：`mcp apps:` 目錄快取＋HTTP 正常，模型 0 次 `mcp_list`/`mcp_call` | 觀察项（非缺陷）：兩 light 題答案全在檔案系統；world-export 題（MCP×13）未測，可能必須用 |
| RESOURCE／context 天花板（DEF-003） | 2/2 heavy 尾聲 | 016 剩 337；017 400@262,159；light 兩題尾聲乾淨（0 筆 4xx） | 事前守門已碼未啟用（`CONTEXT_TOKENS` 未設）；live 驗證要等 heavy run |
| 模型隨機性 | 全程 | EXP-007 同碼重跑差 ±0.01 | A/B 需多 run |

## 4. 結構性結論

1. **交付管線已可靠**：main 線 4/4 capture≠{}、`serve completed`、零 ERR_NO_SUBMISSION；P1＋P2 的閘門／狀態機／收尾在 heavy 與 light 都撐住。
2. **失分主軸已轉移到內容正確性**：heavy＝hard-gate 未全過→大權重歸零；light rubric＝數值／推導 ground truth 錯。管線類修復的邊際收益已盡，**P3（驗證核心）是当前最大槓桿**（ADR-002）。
3. **gate 角色初步有效但邊界清楚**：兩次 live 均一輪 `verdict: PASS`、fix 0 輪（fix 路徑仍只有 mock 覆蓋）；且 gate 驗證的是「instruction 機械可驗要求」，**不等於 rubric 數值正確**（018 gate 全 PASS 仍丟 40 點）→ P3-02 需把「重算鏈」本身變成可驗物件。
4. **light 題性價比高**：單題 42–71 m、70–143 呼叫；heavy 3–4.7 h。dev 全量成本估算（§13）與 R-010 併行決策待 P5。
5. **DEF-003 啟用時機**：light 無感、heavy 尾聲必撞；建議下一個 heavy run 帶 `CONTEXT_TOKENS=262144`（僅本機 dev；正式不綁常數，R-009）。

## 5. 對 P3 的直接輸入

- P3-01（單位／量綱檢查）：018 的 $ 數錯誤含匯總鏈（unrounded→ceil1000）與 Sec2 小計鏈——機械可驗。
- P3-02（計算 ledger）：要求 agent 產出「每個交付數字 ← 來源檔＋公式＋中間值」的 ledger，gate 逐條重算；目標直打 CALCULATION 族。
- P3-03（hard-gate／rubric evidence matrix）：017 型「每 item hard 旗未全過→權重歸零」需要 per-item 自我查核清單。
- 對照基線：structural 兩題 0.3673／0.2573（`eb918d8`）與 rubric 兩題 0.1304／0.8378（`85d1cbd`）＝P3 改動的 A/B 錨點（同題同參、單變因）。

### P3 A/B 第一樣本（2026-11-21）：計算 ledger（`6741308`）

| 題 | 錨點（`85d1cbd`） | ledger（`6741308`） | Δ | 呼叫 | wall |
|---|---:|---:|---:|---:|---:|
| engineers-estimate-check | 0.130435 | **0.347826** | **+0.2174** | 70→92 | 2,497→3,951 s |

- 判讀：丟分族由「**算錯／內部不一致**」位移到「**解讀／取值選擇與 GT 不同**」（headwall 歸類、curb inlet 計數、VF 深度 convention）。重算紀律已把可機械自洽的錯修掉（Sec2 一致性項轉過、bond 向 GT 收斂 $44k），剩下的不是算術問題。
- 成本：+31% 呼叫、+58% wall、out 78k→137k。
- 結論：ledger 碼保留；下一槓桿＝P3-03/04（假設矩陣＋一致性），直打「解讀選擇」族。heavy 側需先補 gate-only 錨（`eb918d8` heavy run 無 gate 碼）才能做 clean A/B。
