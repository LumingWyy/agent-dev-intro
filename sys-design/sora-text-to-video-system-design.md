# Sora / Text-to-Video システム設計

> 出典動画: 「Design Sora / Text-to-Video System (OpenAI 面接問題解析)」 / YouTube チャンネル s09g
> 整理日: 2026-05-07

---

## 一、問題の核心と背景

ユーザーのテキストプロンプト（Text Prompt）から高品質な動画を生成するサービスを設計する。ベンチマーク対象は **OpenAI Sora**。

### 従来の動画 / 画像システムとの本質的な違い

- **計算量のオーダーが桁違い**: 動画生成の FLOPs は LLM をはるかに上回る
  - 比較: Llama 3 70B が一文生成する際は **約 140 Tflops**
  - Sora が 16 秒 720p 動画 1 本を生成: **約 220 Petaflops**（**6 桁以上** 大きい）
- **GPU は希少かつ高価なリソース**: すべての設計判断は「いかに GPU を節約するか」を軸に行う
- **時間次元という新たな難所**: 画像生成は空間のみ考慮すればよいが、動画は **時間的一貫性** と **物理的整合性** を保たねばならない

### 設計上の難点

| 難点 | 内容 |
|---|---|
| 時間的一貫性 | 物体が再生中に突然変形・消失してはならない |
| 物理的整合性 | 重力方向、鏡面反射、光と影のロジックなど |
| 解像度 | 最低 720p（スマホ向け）、エンタープライズ向けは 1080p |
| リソースコスト | GPU は極めて高価で希少 |
| 法令遵守 | 公人の肖像、暴力、IP 侵害（ディズニー等）を拒絶、AI 透かしの強制 |

---

## 二、Functional Requirements（機能要件）

- **コア機能**: ユーザーがテキスト prompt を入力 → 対応する動画を生成
- **動画スペック**:
  - 標準時間: **15 秒**
  - エンタープライズ拡張: **60 秒、1080p**
- **配信方式**: 非同期タスク、完了時に **Push Notification** で通知
- **ダウンロード**: CDN による **Adaptive Downloading**（回線状況で解像度を選択）

---

## 三、Capacity Estimation（容量見積もり）

### 推計プロセス

| 項目 | 値 | 説明 |
|---|---|---|
| 日次リクエスト数 | 5,000,000 | 500 万件/日と設定 |
| 1 日の秒数 | ~86,400 | 概算で 100,000 |
| 平均 QPS | ~50 | 5M / 100K ≈ 50 |
| ピーク倍率 | 3–5× | 経験値 |
| ピーク QPS | ~200 | 4× で算出 |
| エンド to エンド遅延目標 | < 5 分 | |

### 動画ファイルサイズ（ストレージと帯域への影響）

| スペック | サイズ |
|---|---|
| 15 秒動画（720p） | ~50 MB |
| 60 秒動画（1080p） | ~180 MB |

---

## 四、Non-Functional Requirements（非機能要件）

| 観点 | 目標 |
|---|---|
| エンド to エンド遅延 | < 5 分 |
| 初フレーム遅延 | ユーザー体感の核心指標 |
| 可用性 | 単一ルーム / 単一ユーザーの障害がサイト全体を巻き込まないこと |
| 一貫性 | タスク状態は結果整合性 |
| コンプライアンス | 安全審査 + AI 透かしの強制 |
| GPU リソース | 厳格な admission control、過負荷回避 |

---

## 五、High-Level Architecture（高レベル構成）

```
[Client]
   ↓
[API Gateway]              ← Rate Limit, Quota Check, Auth
   ↓
[Backend Server]           ← タスク生成、状態マシン管理
   ↓
[Task DB]  ←──────────────  状態の永続化
   ↓
[Priority Message Queue]   ← Free / Paid / Enterprise の 3 段優先度
   ↓
┌──────────────────────────────────┐
│  Worker Pool                      │
│  ├─ Preprocessing (CPU)           │
│  ├─ Model Inference (8× H100 GPU) │
│  └─ Post-processing (small GPU)   │
└──────────────────────────────────┘
   ↓
[Object Storage (S3-like Blob)]
   ↓
[CDN (Adaptive Downloading)]
   ↓
[Notification Service] → [Client]
```

| コンポーネント | 役割 |
|---|---|
| API Gateway | リクエスト受付、レート制限、Quota 確認、サブスクリプション検証 |
| Backend Server | タスク生成、状態マシンの維持 |
| Priority Queue | ユーザーランク別に並ぶタスクキュー |
| GPU Worker Pool | 3 段階のパイプライン、異なるハードで構成 |
| Object Storage | 大量の小ファイル、Blob / S3 |
| CDN | グローバル配信 + 自動解像度切替 |
| Notification Service | 非同期でユーザーに完了通知 |

---

## 六、Workflow DAG（詳細ワークフロー）

動画生成フローの 3 大ステージと時間予算:

```
[Prompt 入力]
     ↓
─────────────  Preprocessing (CPU / 小 GPU, ~数百 ms)  ──────
  ├─ テキスト安全審査（キーワード / IP ブロック）
  ├─ Prompt Enhancement（Text Rewriter で拡張）
  └─ 拡張後にもう一度安全審査
     ↓
─────────────  Model Inference (8× H100, ~30s)  ────────────
  ├─ Text Encoder: text → embedding
  ├─ Diffusion Transformer (DiT)
  │     30B パラメータ、50 denoising steps、latent space でデノイズ
  └─ Video Decoder (VAE / TAEF): latent → pixel
     ↓
─────────────  Post-processing (1 枚の旧 GPU, 短時間)  ──────
  ├─ 超解像 (SR): 720p → 1080p
  ├─ フレーム補間 (Frame Interpolation)
  ├─ 視覚層の最終安全チェック
  └─ 透かし付与（顕在 / 不可視 / C2PA）
     ↓
[Object Storage] → [CDN] → [Push Notification]
```

---

## 七、DiT モデルの核心 — 系列長と FLOPs の導出

### 1. 系列長 73K の根拠

```
オリジナル動画: 16 s × 16 fps = 256 frames
解像度:         768 × 768
                    ↓ VAE 時空圧縮 (8 × 8 × 8)
Latent:         96 × 96 × 32       (空間 96×96, 時間 32)
                    ↓ Patch Tokenization (2 × 2 × 1)
Tokens:         (96/2) × (96/2) × (32/1)
             =  48 × 48 × 32
             =  73,728 ≈ 73K
```

### 2. モデルパラメータ

| 項目 | 値 |
|---|---|
| パラメータ数 | 30B（300 億） |
| Denoising Steps | 50 |
| 系列長 n | 73K |
| 1 回の推論時間 | ~30 秒 |

### 3. FLOPs 計算

精密公式:

```
FLOPs ≈ 24 · n · d² · L · s
```

ここで `n` = 系列長、`d` = 隠れ次元、`L` = レイヤ数、`s` = denoising step 数。

概算公式（パラメータ数法）:

```
FLOPs ≈ 2 × パラメータ数 × 系列長 × ステップ数
      = 2 × 30B × 73K × 50
      ≈ 220 Petaflops
```

### 4. Self-Attention 計算量

- 計算量: **O(n²)**
- n = 73K → n² ≈ 5.3 × 10⁹ オーダー → **系列並列化が必須**

---

## 八、GPU 選定とパイプラインへのリソース配分

### 1. ハードウェア

| ステージ | ハードウェア | VRAM | 備考 |
|---|---|---|---|
| Preprocessing | CPU または小型 GPU | — | テキスト処理、数百 ms |
| Model Inference | 8× H100 | 80 GB / 枚 | 同時確保・同時解放 |
| Post-processing | 1 枚の旧 GPU / 小型 GPU | — | コスト節減 |

### 2. 1 回の推論あたりのリソース消費

- **1 ノード = 8 GPU H100**
- 所要時間: ~30 秒
- 30B モデル推論時の **中間活性化値 ~60 GB**（VRAM 占有の大部分）

### 3. 系列並列 / USP（Unified Sequence Parallelism）

73K 長系列の VRAM と計算負荷への最適化:

- **コアアイデア**: Self-Attention、Cross-Attention、Feed-Forward の 3 層で並列を統一し、本来 3 回独立で行う通信（Reduce 操作）を **1 回にまとめる**
- 実運用での組み合わせ: **CP4 + TP2**
  - CP4 = Context Parallelism × 4
  - TP2 = Tensor Parallelism × 2

### 4. 中間活性化 60 GB の意味

これは本システム設計でも **最も反直観的かつ核心的な判断ポイント** の 1 つ。

- **60 GB の中間活性化値を保存する IO コスト > 30 秒推論を再実行するコスト**
- 結論: **タスクのプリエンプション非対応 / チェックポイント不要**
- 一度推論ステージに入ったら、その 30 秒を **走り切らせるのが最も得**

---

## 九、Admission Control（admission control の 3 段階）

GPU が高価すぎるため、複数のゲートで絞る必要がある。

### Stage 1 — Rate Limit（レート制限）

- ユーザーの Quota とサブスクリプションプランをチェック
- 無料ユーザー: 上限低、優先度低
- 有料ユーザー: 高優先度
- エンタープライズ: **BYOM / BYOC**（自前マシン / 自前キャパシティ）対応可

### Stage 2 — Resource Check（リソース確認）

- 空き GPU の有無を確認
- リソース不足 → キューイング / 拒否

### Stage 3 — Traffic Shaping（トラフィック整形）

- **優先度キュー**: Free / Paid / Enterprise の 3 段
- **リージョン分散**: 北米のピーク時 → 深夜の欧州データセンターへ振り分け、時差を活用

### タスクステートマシン

```
Ready → Scheduling → Running → Complete
                        ↓
                       Fail → Retriable → Retry → Ready  (ループ)
                        ↓
                     Final Fail (最大リトライ回数到達)
```

---

## 十、Storage 設計

### 1. 動画ストレージ — Blob / Object Storage

- 選定: **S3 系 Object Storage**
- 理由: 大量の断片的小ファイルでは Object Storage が File System（HDFS）より優れる
- CDN と直結し、グローバルに配信

### 2. タスクメタデータ

- 関係 DB または NoSQL
- フィールド: TaskID、UserID、Prompt、Status、CreatedAt、CompletedAt、VideoURL 等

### 3. 中間生成物

- DiT の中間活性化 60 GB → **永続化しない、推論完了即解放**

---

## 十一、動画エンコード、CDN、ダウンロード

| 観点 | 設計 |
|---|---|
| 出力解像度 | 720p（デフォルト）/ 1080p（エンタープライズ + SR） |
| フレームレート処理 | 256 フレーム + フレーム補間 |
| ファイルサイズ | 15s ≈ 50 MB / 60s ≈ 180 MB |
| CDN 戦略 | グローバル配信、人気動画はエッジに事前ロード |
| クライアント DL | Adaptive Downloading（回線速度で解像度を選択） |

---

## 十二、Safety Pipeline（前後 2 段の安全審査）

### 前段審査（Preprocessing 段階）

- ブロック手段: キーワードマッチ + テキスト分類
- ブロック対象:
  - 公人 / 著名人の肖像
  - 暴力コンテンツ
  - 特定 IP の著作権（ディズニー等）

### 後段審査（Post-processing 段階）

- ブロック手段: 生成された動画コンテンツに視覚レイヤの最終チェック
- ブロック対象: モデル生成過程で混入する不適切な細部

### Prompt Enhancement

- Text Rewriter で拡張: 「猫が走る」 → 「夕陽の差す草原を、オレンジ色のぽっちゃりした猫が嬉しそうに駆ける」
- 遅延: 数百 ms
- 拡張後は **必ずもう一度安全審査** を通す（拡張が新たなリスクを生むため）

---

## 十三、AI 透かし（Watermark）

すべての生成動画に AI 生成コンテンツである旨の透かしを **強制付与**。

| タイプ | 説明 |
|---|---|
| 顕在透かし | 視覚的に見える、ロゴ等 |
| 不可視透かし | ピクセル単位エンコード、肉眼では見えない |
| C2PA 標準 | 業界標準、メタデータレベルでのトレーサビリティ |

---

## 十四、Notification & Queue

### Notification Service

- 動画生成は分単位の長時間タスク → **必ず非同期化**
- 完了後 Push Notification でユーザーに通知
- ユーザータップ → CDN 経由で Adaptive Download

### タスクキュー

- 技術選定: 汎用 Message Queue
- 優先度: Free / Paid / Enterprise の 3 段
- リトライ: ステートマシン `Running → Retriable → Retry → Ready` のループ、上限到達で Final Fail

---

## 十五、Billing & 課金軸

主要な課金軸:

- **動画長**: 15s vs 60s
- **解像度**: 720p vs 1080p
- **モデルバージョン**: 標準 vs 高品質

API Gateway 段階の **Rate Limiter** で Quota とサブスクリプション検証を実施。

---

## 十六、Cost Reduction（コスト削減策）

| 戦略 | 仕組み |
|---|---|
| FP8 量子化 | VRAM 削減 + スループット向上 |
| オフライン GPU 回収 | ピーク時に学習タスクを停止し、推論に GPU を回す |
| 時差スケジューリング | 北米ピーク時 → 深夜の欧州データセンターへ |
| CDN 事前ロード | 人気動画をエッジへ先回りプッシュ |
| 異種ハード Pipeline | 前処理は CPU、後処理は旧 GPU、H100 は DiT 専用 |
| 長時間タスクをプリエンプトしない | 60 GB 活性化の保存コスト > 再実行コスト |

---

## 十七、Trade-offs（トレードオフ）

| 観点 | 判断 | 理由 |
|---|---|---|
| 同期 vs 非同期 | **非同期** | 5 分 SLA、同期は不可能 |
| プリエンプション | **しない** | 60 GB 活性化の保存コスト > 30s 再実行 |
| 精度 vs 速度 | **FP8 量子化** | わずかな精度損失で大幅スループット向上 |
| ハード統一 vs 異種 | **異種パイプライン** | H100 を DiT に専念させる |
| 全件 SR vs 選別 SR | **エンタープライズのみ 1080p** | GPU 時間コストを制御 |

---

## 十八、比較: Sora vs LLM システム

| 観点 | LLM (Llama 3 70B) | Sora (DiT 30B) |
|---|---|---|
| 1 回の FLOPs | ~140 Tflops | ~220 Petaflops |
| 計算量差 | baseline | 約 **6 桁** 大きい |
| 系列長 | 数 K | 73K（動画 token） |
| 遅延 | 秒オーダー | 分オーダー |
| プリエンプション | 可能 | 不可 |
| 同期性 | 通常はストリーミング同期 | 必ず非同期 |
| 出力サイズ | 数 KB のテキスト | 50–180 MB の動画 |

---

## 十九、主要用語

| 用語 | 意味 |
|---|---|
| DiT (Diffusion Transformer) | Sora の核心: 拡散モデル + Transformer の拡張性 |
| VAE / TAEF | 動画エンコーダ / デコーダ、pixel ↔ latent |
| Latent Space（潜在空間） | 圧縮空間で推論、計算コスト削減 |
| Patch Tokenization | 2×2×1 patch で動画をトークン化 |
| Denoising Steps | 拡散デノイズの反復回数（50） |
| Prompt Enhancement | Text Rewriter による prompt 拡張 |
| USP | Unified Sequence Parallelism、統一系列並列 |
| CP / TP | Context Parallelism / Tensor Parallelism |
| C2PA | コンテンツ出所 / 真正性の業界標準（透かし） |
| BYOM / BYOC | Bring Your Own Machine / Capacity |
| Adaptive Downloading | CDN が回線速度で解像度を切替 |

---

## 二十、核心結論と実戦的アドバイス

### 核心結論

- **GPU は絶対的な制約条件**: すべての設計判断は「GPU をいかに節約 / 利用率最大化するか」を軸にする
- **推論の途中で止めない**: 60 GB 活性化を保存する IO コストは再実行より高い
- **障害領域を分離する**: 多段 admission control + 前段安全審査で無駄な GPU 消費を防ぐ
- **時差を活用する**: グローバルデータセンターは天然の **コスト裁定機会**

### 最適化の方向

- Self-Attention の **二乗複雑度** が最大ボトルネック
- **系列並列（CP4 + TP2）+ FP8 混合精度** が主力武器
- **異種ハード Pipeline**（CPU / 小 GPU / H100）でコスト差を最大化

### 面接で議論すべき要点

- 自発的に **Capacity を計算**（5M/日 → 平均 50 QPS → ピーク 200）
- 自発的に **FLOPs を計算**（`2 × params × seq_len × steps` 公式）
- 自発的に **活性化値を計算**（60 GB → 「プリエンプトしない」判断を導く）
- 自発的に「オフライン GPU 回収」によるスパイク対応を議論

---

## 二十一、システム設計への示唆

- **高価リソース → 多段ゲート**: GPU のような希少リソースの前には 3 段の admission control を並べる
- **大きな状態はプリエンプトしにくい**: worker 中間状態が GB 級になると、プリエンプトコストが完走コストを上回る
- **非同期 + ステートマシン**: 長時間タスクは必ず非同期化し、`Ready → Running → Complete/Fail/Retry` を明示モデル化
- **異種パイプライン分割**: ステージ（前処理 / 推論 / 後処理）ごとに適切なハードを割当て、高価な GPU に安価な処理をさせない
- **クロスリージョン時差スケジューリング**: GPU 系業務独自のコスト武器
- **Capacity Estimation は面接の基本動作**: QPS / FLOPs / ストレージは必ず自分から計算する
- **安全審査は「前段 + 後段」の 2 重必須**: 片方では不十分、前段は入力防御、後段は生成物防御
- **Self-Attention O(n²)**: 長系列タスクの根本ボトルネック、系列並列が存在する理由
