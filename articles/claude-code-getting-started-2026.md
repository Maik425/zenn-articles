---
title: "Claude Codeを半年使い込んで辿り着いた設定と運用 ― 実際の設定ファイルを公開"
emoji: "🚀"
type: "tech"
topics: ["claudecode", "ai", "cli", "開発環境", "anthropic"]
published: true
---

## はじめに

Claude Codeの入門記事は山ほどある。「インストールしてCLAUDE.md書きましょう」で終わるやつだ。

この記事はそういう記事ではない。半年間、毎日Claude Codeを使い込んで辿り着いた**実際の設定ファイル**と**運用パターン**を公開する。CLAUDE.mdだけでなく、`settings.json`の権限設計、カスタムスキル、サブエージェント、Memory、MCPまで含めた「Claude Codeの本当の使い方」を書く。

:::message
この記事では実際に使っている設定をベースに、機密情報（社名・API鍵・個人情報など）を除去・匿名化した上で公開しています。
:::

---

## 前提：Claude Codeとは

知っている人は読み飛ばしてほしい。

Claude CodeはAnthropicが公式に提供しているCLIツール。ターミナル上でClaudeと対話しながら、ファイルの読み書き、Git操作、コマンド実行、コードの生成・修正を行う。エディタに依存しない。プロジェクト全体のコンテキストを理解した上で作業するので、ファイル単位ではなくリポジトリ単位で仕事ができる。

```bash
npm install -g @anthropic-ai/claude-code
cd ~/my-project
claude
```

Node.js 18以上が必要。初回起動でブラウザ認証が走る。ここまでは他の記事と同じなので省略する。

---

## settings.json：権限設計が安全性と効率を決める

多くの記事が触れていないが、Claude Codeを本格運用する上で最も重要なのが `~/.claude/settings.json` だ。これはClaude Codeに「何を許可し、何を禁止するか」を定義するファイルで、**安全に使いながらも許可確認の手間を減らす**バランスを設計する。

### 実際の設定（匿名化済み）

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "allow": [
      "Bash(git commit:*)",
      "Bash(git pull:*)",
      "Bash(curl:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip3 install:*)",
      "Bash(gh run list:*)",
      "Bash(gh workflow run:*)",
      "WebFetch(domain:github.com)",
      "WebFetch(domain:api.github.com)"
    ],
    "deny": [
      "Bash(rm *)",
      "Bash(* | rm *)"
    ],
    "defaultMode": "acceptEdits"
  }
}
```

### 設計思想

**allow（許可リスト）**は「毎回確認されると面倒なコマンド」を入れる。パターンマッチで `Bash(git commit:*)` のように書くと、`git commit` で始まるコマンドは全て自動許可される。

自分が許可しているのは主に3カテゴリ:

1. **Git系** — `git commit`, `git pull` など。ファイル編集は `acceptEdits` モードで自動許可しつつ、コミットも通す
2. **スクリプト実行** — `python`, `python3`, `curl` など。パイプライン実行やAPI確認で頻繁に使う
3. **WebFetch** — 特定ドメインへのアクセス。`github.com` と `api.github.com` だけ許可している

**deny（拒否リスト）**は絶対に実行させたくないコマンドを入れる。`rm` を含むコマンドは全てブロックしている。Claude Codeが「不要なファイルを削除します」と言ってきても、deny に入っていれば実行されない。

**defaultMode** は `acceptEdits` にしている。ファイルの編集提案を毎回Yes/Noで確認する手間を省くためだ。ただし、初めて使う人は `default`（毎回確認）から始めて、慣れてきたら `acceptEdits` に切り替えることを勧める。

### env（環境変数）

```json
"env": {
  "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
}
```

実験的機能のフラグをここで有効化できる。エージェントチーム機能（後述）はこのフラグで有効になる。

---

## CLAUDE.md：プロジェクトに「記憶」を持たせる

CLAUDE.mdの基本（配置場所、読み込み順）は他の記事でも触れられているので、ここでは「実際にどう書くと効くのか」に絞る。

### 配置場所のおさらい

| 場所 | 用途 | 共有 |
|------|------|------|
| `~/.claude/CLAUDE.md` | 全プロジェクト共通ルール | 個人 |
| `プロジェクトルート/CLAUDE.md` | プロジェクト固有設定 | git管理（チーム共有） |
| `.claude/CLAUDE.md` | ローカル上書き | .gitignore（個人用） |

### グローバルCLAUDE.md：自分が実際に書いていること

グローバルCLAUDE.mdには「どのプロジェクトでも共通のルール」を書く。自分の場合、**サブエージェントのルーティングテーブル**を書いている。

```markdown
# グローバル Claude Code 設定

## サブエージェント活用ルール

Task ツールでチームを構成する際、~/.claude/agents/ のエージェントを適切に選択する。

### タスク別エージェント選択

| タスク種別 | 推奨エージェント |
|-----------|-----------------|
| Go開発 | golang-pro |
| TypeScript/JS | typescript-pro, javascript-pro |
| Next.js | nextjs-developer |
| React | react-specialist |
| Python | python-pro |
| API設計 | api-designer |
| DB設計・SQL | sql-pro, database-administrator |
| コードレビュー | code-reviewer |
| テスト | test-automator, qa-expert |
| セキュリティ | security-auditor |
| DevOps | devops-engineer |

### 選択の原則

- 単純なタスク → 直接実行（エージェント不要）
- 専門的なタスク → 該当ドメインのエージェントを選択
- 複合タスク → 複数エージェントを並列で活用
- 不明な場合 → 汎用エージェント（general-purpose）を使用
```

これが何をしているかというと、Claude Codeが「Goのコードレビューをして」と頼まれたとき、自動的に `golang-pro` と `code-reviewer` を組み合わせてサブエージェントを起動する判断材料になる。CLAUDE.mdは「指示書」であると同時に「ルーティングテーブル」としても機能する。

### プロジェクトCLAUDE.md：実際に書いている内容

プロジェクトルートのCLAUDE.mdには、そのプロジェクト固有の情報を書く。以下は実際に使っているものを匿名化した例:

```markdown
# プロジェクト概要

業務管理システム — Next.js 14 + Go + PostgreSQL

## 技術スタック

- Frontend: Next.js 14 (App Router) / TypeScript / Tailwind CSS
- Backend: Go 1.22 / Echo framework
- DB: PostgreSQL 15
- 開発環境: Docker Compose

## 開発コマンド

- Frontend: ローカル `npm run dev` (port 3000)
- Backend: Docker内で起動 (port 8080)
- DB接続: postgresql://user:pass@localhost:5432/mydb

## 重要な注意事項

- docker-compose の volume mount が ./backend:/app を上書きするため、
  Go バイナリ変更後は `go build` → `docker compose restart backend` が必要
- Frontend はDocker外でローカル実行する（HMRのため）

## コーディング規約

- コミットメッセージ: 日本語、動詞始まり
- Go: エラーは必ず fmt.Errorf("%w", err) でラップ
- TypeScript: strict mode、any禁止
```

ポイントは**「よくある間違い」を書いておくこと**だ。上の例で言えば「docker-compose のvolume mountがバイナリを上書きする」という罠は、Claude Codeが知らないと何度でもハマる。一度ハマった問題をCLAUDE.mdに書いておけば、二度と同じ間違いをしない。

---

## カスタムスキル：スラッシュコマンドで複雑な業務を一発実行

Claude Codeで最も過小評価されている機能がカスタムスキルだ。`~/.claude/commands/` にMarkdownファイルを置くだけで、独自のスラッシュコマンドを追加できる。

### 自分が実際に使っているスキル一覧

```
~/.claude/commands/
├── start.md              # /start — 作業開始メニュー
├── task-support.md       # /task-support — タスク管理
├── create-issues.md      # /create-issues — Issue一括作成
├── update-daily.md       # /update-daily — デイリーノート自動更新
├── meeting-prep.md       # /meeting-prep — MTG事前準備
├── meeting-start.md      # /meeting-start — MTG開始
├── meeting-end.md        # /meeting-end — MTG終了
├── article-research.md   # /article-research — 記事リサーチ
├── article-humanize.md   # /article-humanize — AI文体除去
├── sales-outreach.md     # /sales-outreach — 営業アウトリーチ
├── edit-gdoc.md          # /edit-gdoc — Google Docs編集
├── edit-gsheet.md        # /edit-gsheet — Google Sheets編集
├── edit-docx.md          # /edit-docx — Word編集
└── scrape-jobs.md        # /scrape-jobs — 求人スクレイピング
```

14個のスキルを登録している。開発だけでなく、タスク管理、記事執筆、営業、事務作業まで全てClaude Codeから操作する運用だ。

### スキルの書き方：具体例

スキルの実体はMarkdownファイルで、Claude Codeへの「手順書」を書く。例として、作業開始メニュー `/start` の構成を紹介する:

```markdown
# 作業開始メニュー (/start)

セッション開始時に作業カテゴリを選択させ、適切なワークフローに誘導する。

## 手順

1. AskUserQuestion で作業カテゴリを選択
   - 開発 (Dev) — コーディング、バグ修正、機能追加
   - タスク管理 — GitHub Issues確認・作成・ステータス更新
   - 記事作成 — 記事生成・リサーチ・ヒューマナイズ
   - 自動化パイプライン — 定期実行スクリプト管理
   - 事務・リサーチ — メール下書き、資料作成、調査

2. 選択に応じたフォローアップ

   ### 「開発」を選んだ場合
   - 対象プロジェクトを確認
   - git status や最近の変更を確認
   - CLAUDE.md を読み込んでプロジェクト固有ルールを適用

   ### 「タスク管理」を選んだ場合
   - gh issue list でオープンタスクを取得
   - 次のアクションを選択（確認/新規作成/ステータス更新）

   ### 「記事作成」を選んだ場合
   - フェーズを選択（新規/ブラッシュアップ/ヒューマナイズ）
   ...
```

スキルファイルに書くべきことは3つ:

1. **目的**（何をするスキルか）
2. **手順**（ステップバイステップの指示）
3. **分岐**（ユーザーの選択に応じた処理の分岐）

Claude Codeの `AskUserQuestion` ツールを活用すると、対話的にユーザーに選択肢を提示して処理を分岐させることができる。これにより、1つのスキルで複数のワークフローをカバーできる。

### スキルが効くケース

スキルが特に威力を発揮するのは**「手順が決まっているが、毎回微妙に違う作業」**だ。

例えば `/create-issues` は、Issue作成 → GitHub Projectへの追加 → ステータス設定 → 優先度設定 → ラベル付与を一括で行う。GraphQL APIの呼び出し、Project IDの指定、ステータスフィールドのOption IDなど、手動でやると毎回調べることになる情報をスキルに埋め込んである。

```
/create-issues ユーザー招待機能を実装する。優先度:高、プロジェクト:MyApp
```

これだけで、正しいラベル、正しいProject、正しいステータスでIssueが作成される。

---

## サブエージェント：専門家チームを並列で動かす

Claude Codeは単体でも強力だが、サブエージェント（Taskツール）を使うと**複数の専門AIを並列で動かせる**。

### 仕組み

`~/.claude/agents/` にエージェント定義ファイル（Markdown）を置く。各エージェントは特定のドメインに特化したシステムプロンプトを持つ。

```
~/.claude/agents/
├── golang-pro.md          # Go専門
├── typescript-pro.md      # TypeScript専門
├── react-specialist.md    # React専門
├── sql-pro.md             # SQL/DB設計専門
├── code-reviewer.md       # コードレビュー専門
├── security-auditor.md    # セキュリティ監査専門
├── devops-engineer.md     # DevOps専門
└── ...（100+のエージェント定義）
```

### 使い方の例

Claude Codeに「このPRをレビューして」と頼むと、CLAUDE.mdのルーティングテーブルに従って、`code-reviewer` と `security-auditor` を並列で起動する。各エージェントがそれぞれの観点でレビューし、結果を統合して報告してくれる。

大きな機能実装では、`golang-pro` にバックエンドを、`react-specialist` にフロントエンドを同時に書かせることもできる。人間は方針を決めてレビューするだけだ。

### エージェントチーム

`settings.json` で `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` を有効にすると、複数エージェントがタスクリストを共有して協調作業できる。チームリーダーがタスクを分配し、各エージェントが完了報告して次のタスクを取る、というワークフローが動く。

---

## Memory：セッションをまたいだ学習

Claude Codeには「Auto Memory」という機能がある。`~/.claude/projects/` 配下にプロジェクトごとのメモリディレクトリが作られ、セッション間で情報が永続化される。

### 何を記憶させるか

自分の場合、以下のような「一度ハマったこと」をMemoryに書いている:

```markdown
# Memory

## Key Learnings

### Python環境
- venvがPython 3.9 → `int | None` 構文（3.10+）は使えない。`Optional[int]` を使う
- `list[str]` も不可 → `List[str]` from typing を使う

### API制約
- X API Free tier: 投稿のみ、読み取りエンドポイントは401
- 日本語は1文字=2カウント → 実質140文字制限

### インフラ
- docker-compose volume mountがビルド済みバイナリを上書きする
  → ホスト側で `go build` してから `docker compose restart` が必要
```

Claude Codeは新しいセッションを開始するたびにこのMemoryを読む。過去にハマった問題を二度と踏まない。CLAUDE.mdが「ルール」だとすれば、Memoryは「経験」だ。

### MemoryとCLAUDE.mdの使い分け

| | CLAUDE.md | Memory |
|---|---|---|
| 内容 | プロジェクトのルール・規約 | 過去の失敗・知見 |
| 更新頻度 | 意図的に編集 | Claude Codeが自動追記 |
| 共有 | git管理でチーム共有可 | 個人のみ |
| 例 | 「テストは go test ./... で実行」 | 「Python 3.9では int\|None が使えない」 |

---

## MCP：外部ツールとの接続

MCP（Model Context Protocol）を使うと、Claude Codeにカスタムツールを追加できる。データベースへの直接クエリ、外部APIの認証付き呼び出しなど、標準のBashやWebFetchでは面倒な操作をツールとして統合する。

### 使い方の例

自分の場合、業務システムのPostgreSQLに直接クエリを投げるMCPサーバーを接続している。

```
「先月の売上データを集計して」
```

と頼むと、Claude Codeが `query_db` ツールでSQLを組み立てて実行し、結果を整形して返してくれる。いちいちDBクライアントを開いてSQLを書く必要がない。

MCPサーバーの設定はプロジェクトの `.mcp.json` に書く:

```json
{
  "mcpServers": {
    "my-db": {
      "command": "node",
      "args": ["mcp-server.js"],
      "env": {
        "DATABASE_URL": "postgresql://..."
      }
    }
  }
}
```

---

## 実践的な運用パターン

ここまでの設定を踏まえて、実際にどう運用しているかを紹介する。

### パターン1: 朝の作業開始

```
/start
```

カスタムスキルの `/start` で、作業カテゴリを選択する。「開発」を選ぶとプロジェクト一覧が出て、選んだプロジェクトの `git status` とCLAUDE.mdを自動で読み込んでくれる。

毎朝ゼロからコンテキストを説明する必要がない。スラッシュコマンド一発でClaude Codeが「今日もこのプロジェクトですね」と準備完了した状態になる。

### パターン2: デイリーノートの自動生成

```
/update-daily
```

GitHub Projectボードからタスクの状態を取得し、本日完了したタスク・進行中のタスク・依頼中のタスクを自動でMarkdownに整理する。GraphQL APIの呼び出し、ステータスのマッピング、既存内容との差分マージまで全部スキルに書いてある。

手動でやると15分かかる作業が10秒で終わる。

### パターン3: 段階的な機能実装

大きな機能は一気に頼まない。

```
# Step 1: 設計（Plan Mode: Shift+Tab）
「ユーザー招待機能を設計して。DB変更、API、UIの変更をリストアップ。まだコードは書かないで」

# Step 2: 確認 → 承認

# Step 3: 実装
「設計通りに実装して。DBマイグレーションから」

# Step 4: テスト
「テストを書いて走らせて」
```

Claude Codeの `Plan Mode`（`Shift+Tab` で切り替え）を使うと、コードを書く前に計画を提示してくれる。方向性がズレていたらここで修正できるので、手戻りが劇的に減る。

### パターン4: コードレビューの自動化

```
「git diff main...HEAD の変更をレビューして。セキュリティとパフォーマンスの観点で」
```

サブエージェント（`code-reviewer` + `security-auditor`）が並列でレビューし、ファイル名と行番号付きで指摘してくれる。人間のレビュアーの前にAIレビューを通すことで、ケアレスミスの指摘をAIに任せ、人間はアーキテクチャの判断に集中できる。

---

## やってはいけないこと

半年使った中で踏んだ地雷を共有する。

### 1. 権限を全開放する

`settings.json` で全コマンドを許可すると楽だが、`rm -rf` や `git push --force` を意図せず実行されるリスクがある。少なくとも `deny` リストに破壊的コマンドを入れておく。

### 2. CLAUDE.mdを200行以上にする

Claude Codeのコンテキストウィンドウを圧迫する。要点を絞り、詳細は別ファイルにリンクする。

### 3. 「全部やって」と丸投げ

「ECサイトを作って」のような巨大な依頼は失敗する。機能単位に分割し、段階的に依頼する。

### 4. 生成コードをレビューせずに使う

特にセキュリティに関わる部分（認証、権限チェック、SQLクエリ）は必ず人間がレビューする。

### 5. Memoryを放置する

古い情報がMemoryに残っていると、Claude Codeが間違った前提で動く。定期的にMemoryの内容を確認し、不要な情報は削除する。

---

## まとめ

Claude Codeの本当の力を引き出すには、インストール後の設定設計が鍵になる。

| 設定 | 何をするか | 効果 |
|------|----------|------|
| `settings.json` | 権限設計、deny/allowルール | 安全かつスムーズな操作 |
| グローバル `CLAUDE.md` | 全プロジェクト共通ルール | エージェントルーティング |
| プロジェクト `CLAUDE.md` | 技術スタック、規約、罠 | 毎回の説明が不要に |
| カスタムスキル | スラッシュコマンド化 | 複雑な業務を一発実行 |
| サブエージェント | 専門AIの並列実行 | レビュー・実装の高速化 |
| Memory | セッション間の知識共有 | 同じ失敗を繰り返さない |
| MCP | 外部ツール連携 | DB・APIをClaude Codeから直接操作 |

「インストールして使う」段階から「設定を育てて使いこなす」段階に進むと、生産性は段違いに上がる。この記事で紹介した設定を参考に、自分のワークフローに合わせてカスタマイズしてほしい。
