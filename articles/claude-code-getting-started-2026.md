---
title: "Claude Codeを使い始めて生産性が変わった話 ― CLAUDE.mdの設計が鍵"
emoji: "🚀"
type: "tech"
topics: ["claudecode", "ai", "cli", "開発環境", "anthropic"]
published: true
---

## Claude Codeとは何か

Claude CodeはAnthropicが公式に提供しているCLIツールだ。ターミナル上でClaudeと対話しながら、ファイルの読み書き、Git操作、コマンド実行、コードの生成・修正まで全部やってくれる。

CopilotやCursorとの違いは、エディタに依存しないこと。ターミナルさえあれば動く。そしてプロジェクト全体のコンテキストを読み込んだうえで作業するので、ファイル単位ではなくリポジトリ単位で仕事ができる。

自分は約半年使っているが、最初の1週間で「これは開発スタイルが変わる」と確信した。ただし、ただインストールして使い始めるだけだと本来の力の半分も出ない。鍵になるのはCLAUDE.mdを含む**設定ファイル群の設計**だ。

:::message
この記事では実際に使っている設定をベースに、機密情報（社名・API鍵・個人情報など）を除去・匿名化した上で紹介しています。
:::

---

## インストールと初期セットアップ

まずは導入から。

### インストール

```bash
npm install -g @anthropic-ai/claude-code
```

Node.js 18以上が必要。インストールしたら `claude` コマンドで起動できる。

```bash
cd ~/my-project
claude
```

プロジェクトのディレクトリで起動するのが基本だ。Claude Codeはカレントディレクトリのファイルを読み込んでコンテキストとして使う。

### 初回認証

初回起動時にAnthropicアカウントとの認証が走る。ブラウザが開いてログインするだけ。APIキーを環境変数に設定する方法もある。

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
```

ここまでで動く状態にはなる。だが、ここからが本番だ。

---

## settings.json：最初に設計すべき権限管理

多くの入門記事が触れていないが、インストール直後にやるべきことがある。`~/.claude/settings.json` の設定だ。これはClaude Codeに「何を許可し、何を禁止するか」を定義するファイルで、**安全に使いながらも許可確認の手間を減らす**バランスを設計する。

### 自分が実際に使っている設定（匿名化済み）

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

**allow（許可リスト）** は「毎回確認されると面倒なコマンド」を入れる。パターンマッチで `Bash(git commit:*)` のように書くと、`git commit` で始まるコマンドは全て自動許可される。自分が許可しているのは主に3カテゴリ:

1. **Git系** — `git commit`, `git pull` など
2. **スクリプト実行** — `python`, `curl` など。パイプラインやAPI確認で頻繁に使う
3. **WebFetch** — 特定ドメインへのアクセスだけ許可

**deny（拒否リスト）** は絶対に実行させたくないコマンドを入れる。`rm` を含むコマンドは全てブロックしている。Claude Codeが「不要なファイルを削除します」と言ってきても、denyに入っていれば実行されない。

**defaultMode** は `acceptEdits` にしている。ファイルの編集提案を毎回Yes/Noで確認する手間を省くためだ。ただし、初めて使う人は `default`（毎回確認）から始めて、慣れてきたら切り替えることを勧める。

---

## CLAUDE.mdがなぜ重要なのか

Claude Codeにはプロジェクト固有のルールや知識を伝える仕組みがある。それがCLAUDE.mdだ。プロジェクトルートに置くと、Claude Codeが毎回の起動時に自動で読み込む。

### CLAUDE.mdがないとどうなるか

Claude Codeは賢い。だが、プロジェクト固有の事情は知らない。

- テストは `pytest` なのか `go test` なのか
- コミットメッセージの規約はあるか
- 使っているフレームワークのバージョンは何か
- 触ってはいけないファイルはあるか

これらを毎回口頭で伝えるのは面倒だし、どこかで漏れる。CLAUDE.mdに書いておけば、Claude Codeが毎回自動でルールを守ってくれる。

### 自分の体感

CLAUDE.mdを整備する前と後で、Claude Codeへの指示回数が体感で半分以下になった。「あ、それじゃなくてこっちのフォーマットで」「テストはこのコマンドで」みたいな修正指示がほぼなくなる。最初の1時間をCLAUDE.mdに使うことで、その後の何十時間が楽になる。

---

## CLAUDE.mdの配置場所と使い分け

CLAUDE.mdは3つのレベルで配置できる。

| 場所 | スコープ | 用途 |
|------|---------|------|
| `~/.claude/CLAUDE.md` | グローバル | 全プロジェクト共通のルール |
| `プロジェクトルート/CLAUDE.md` | プロジェクト | プロジェクト固有の規約 |
| `サブディレクトリ/CLAUDE.md` | ディレクトリ | 特定ディレクトリの追加ルール |

グローバルには「どのプロジェクトでも共通のルール」を書く。自分の場合、ここに**サブエージェントのルーティングテーブル**を書いている（後述）。プロジェクトルートには技術スタックや開発コマンドを書く。この使い分けが効く。

---

## CLAUDE.mdの実践的な書き方

では実際にどう書くか。自分が使っているパターンを紹介する。

### グローバルCLAUDE.md：サブエージェントのルーティング

`~/.claude/CLAUDE.md` にはこう書いている:

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
| DB設計・SQL | sql-pro, database-administrator |
| コードレビュー | code-reviewer |
| セキュリティ | security-auditor |
| DevOps | devops-engineer |

### 選択の原則

- 単純なタスク → 直接実行（エージェント不要）
- 専門的なタスク → 該当ドメインのエージェントを選択
- 複合タスク → 複数エージェントを並列で活用
```

これが何をしているかというと、Claude Codeが「Goのコードレビューをして」と頼まれたとき、`golang-pro` と `code-reviewer` を組み合わせてサブエージェントを起動する判断材料になる。CLAUDE.mdは「指示書」であると同時に「ルーティングテーブル」としても機能する。

### プロジェクトCLAUDE.md：技術スタックと「罠」を書く

プロジェクトルートのCLAUDE.mdには、そのプロジェクト固有の情報を書く:

```markdown
# プロジェクト概要

業務管理システム — Next.js 14 + Go + PostgreSQL

## 開発コマンド

- Frontend: ローカル `npm run dev` (port 3000)
- Backend: Docker内で起動 (port 8080)
- テスト: `cd backend && go test ./...`

## コーディング規約

- コミットメッセージ: 日本語、動詞始まり
- Go: エラーは必ず fmt.Errorf("%w", err) でラップ
- TypeScript: strict mode、any禁止

## よくある間違い

- docker-compose の volume mount が ./backend:/app を上書きするため、
  Go バイナリ変更後は `go build` → `docker compose restart backend` が必要
- Frontend はDocker外でローカル実行する（HMRのため）
```

### ポイントは3つ

**1. 開発コマンドを書く**

Claude Codeがテストを走らせたりビルドしたりするとき、正しいコマンドを使ってくれる。ディレクトリの指定まで書いておくと間違いが減る。

**2. コーディング規約を書く**

コミットメッセージの形式、命名規則、エラーハンドリングのスタイル。人間の新メンバーに伝えるのと同じ内容をClaude Codeにも伝える。

**3. 「よくある間違い」を書く**

これが一番効く。上の例で言えば「docker-composeのvolume mountがバイナリを上書きする」という罠は、Claude Codeが知らないと何度でもハマる。一度ハマった問題をCLAUDE.mdに書いておけば、二度と同じ間違いをしない。

---

## すぐに試せる3つのTips

CLAUDE.mdの話だけだと抽象的なので、Claude Codeを使い始めてすぐ効果が出たTipsを3つ紹介する。

### Tip 1: まずプロジェクトの理解を頼む

新しいプロジェクトで最初にやることは、Claude Codeにプロジェクトを読ませることだ。

```
このプロジェクトの構成を把握して、CLAUDE.mdのドラフトを作って
```

Claude Codeがディレクトリ構造、package.json、設定ファイルなどを読み込んで、CLAUDE.mdのたたき台を作ってくれる。ゼロから書くより圧倒的に速い。自分はこのドラフトをベースに、規約や禁止事項を足していく形で運用している。

### Tip 2: Gitの操作はClaude Codeに任せる

ブランチ作成、コミット、差分確認。Git操作をClaude Codeに任せると楽になる。

```
この変更をフィーチャーブランチにコミットして。PRも作って
```

コミットメッセージの規約をCLAUDE.mdに書いておけば、毎回フォーマットを守った適切なメッセージを書いてくれる。PRのdescriptionも変更内容を読み取って自動で書いてくれる。

### Tip 3: エラーをそのまま貼る

ビルドエラー、テストの失敗、ランタイムエラー。エラーメッセージをそのままClaude Codeに貼るだけで、原因の特定から修正まで一気にやってくれる。

```
このエラーを直して:
Error: Cannot find module '@/components/Header'
```

Claude Codeはプロジェクト内のファイルを検索して、パスの間違いやインポートの修正を提案し、許可すればそのまま直してくれる。スタックトレースが長くても全部読んでくれるので、人間がログを追うよりも速いことが多い。

---

## さらに使いこなす：カスタムスキル・サブエージェント・Memory

ここからは、基本を超えた運用の話をする。Claude Codeを「ちょっと便利なツール」から「業務の中核」に変える機能群だ。

### カスタムスキル：スラッシュコマンドで業務を自動化

`~/.claude/commands/` にMarkdownファイルを置くと、独自のスラッシュコマンドを追加できる。自分は14個のスキルを登録している:

```
~/.claude/commands/
├── start.md              # /start — 作業開始メニュー
├── task-support.md       # /task-support — タスク管理
├── create-issues.md      # /create-issues — Issue一括作成
├── update-daily.md       # /update-daily — デイリーノート自動更新
├── meeting-prep.md       # /meeting-prep — MTG事前準備
├── meeting-start.md      # /meeting-start — MTG開始（録画・文字起こし）
├── meeting-end.md        # /meeting-end — MTG終了（議事録生成）
├── article-research.md   # /article-research — 記事リサーチ
├── article-humanize.md   # /article-humanize — AI文体除去
├── edit-gdoc.md          # /edit-gdoc — Google Docs編集
├── edit-gsheet.md        # /edit-gsheet — Google Sheets編集
├── edit-docx.md          # /edit-docx — Word編集
└── ...
```

開発だけでなく、タスク管理・記事執筆・事務作業まで全てClaude Codeから操作している。

スキルが特に威力を発揮するのは**「手順が決まっているが、毎回微妙に違う作業」**だ。例えば `/create-issues` は、Issue作成 → GitHub Projectへの追加 → ステータス設定 → ラベル付与を一括で行う。手動でやると毎回調べることになるProject IDやフィールドIDをスキルに埋め込んであるので、一発で完了する。

### サブエージェント：専門家チームを並列で動かす

`~/.claude/agents/` にエージェント定義ファイル（Markdown）を置くと、Claude Codeが専門的なタスクを委任するサブエージェントとして使える。自分は100以上のエージェント定義を置いている:

```
~/.claude/agents/
├── golang-pro.md          # Go専門
├── typescript-pro.md      # TypeScript専門
├── react-specialist.md    # React専門
├── sql-pro.md             # SQL/DB設計専門
├── code-reviewer.md       # コードレビュー専門
├── security-auditor.md    # セキュリティ監査専門
├── devops-engineer.md     # DevOps専門
└── ...（100+）
```

「このPRをレビューして」と頼むと、グローバルCLAUDE.mdのルーティングテーブルに従って `code-reviewer` と `security-auditor` を並列で起動し、それぞれの観点でレビューして結果を統合してくれる。

### Memory：セッションをまたいだ学習

Claude Codeには「Auto Memory」機能があり、`~/.claude/projects/` 配下にプロジェクトごとのメモリが永続化される。自分は「一度ハマったこと」を記録している:

```markdown
## Key Learnings

### Python環境
- venvがPython 3.9 → `int | None` 構文は使えない。`Optional[int]` を使う

### インフラ
- docker-compose volume mountがビルド済みバイナリを上書きする
  → ホスト側で go build してから docker compose restart が必要
```

CLAUDE.mdが「ルール」だとすれば、Memoryは「経験」だ。Claude Codeは新しいセッションを開始するたびにこのMemoryを読むので、過去にハマった問題を二度と踏まない。

### MCP：外部ツールとの接続

MCP（Model Context Protocol）を使うと、Claude Codeにカスタムツールを追加できる。自分は業務システムのPostgreSQLに直接クエリを投げるMCPサーバーを接続している。「先月のデータを集計して」と頼むだけで、SQLを組み立てて実行し、結果を整形して返してくれる。

---

## 使い始めて変わったこと

Claude Codeを導入して半年。一番変わったのは「作業の起動コスト」だ。

以前は新しいタスクに取りかかるとき、まずどのファイルを触るか調べて、関連するコードを読んで、方針を考えて、ようやく手が動き始めていた。

今は朝 `/start` を叩くだけで、プロジェクトの状態を把握した上で会話が始まる。タスクの内容を伝えれば、関連ファイルの特定から修正案の提示まで数秒で出てくる。自分の仕事は方針の判断と最終確認に集中できる。

CLAUDE.md、settings.json、カスタムスキル、Memory。これらを丁寧に育てておくと、Claude Codeは「ちょっと賢いターミナル」ではなく「プロジェクトを熟知したペアプログラマー」になる。新しいメンバーが即戦力になるオンボーディング資料を用意しておくのと同じ感覚だ。

---

## やってはいけないこと

半年使った中で踏んだ地雷も共有しておく。

### 1. 権限を全開放する

`settings.json` で全コマンドを許可すると楽だが、`rm -rf` や `git push --force` を意図せず実行されるリスクがある。少なくとも `deny` リストに破壊的コマンドを入れておく。

### 2. CLAUDE.mdを200行以上にする

Claude Codeのコンテキストウィンドウを圧迫する。要点を絞り、詳細は別ファイルにリンクする。

### 3. 「全部やって」と丸投げ

「ECサイトを作って」のような巨大な依頼は失敗する。機能単位に分割し、段階的に依頼する。Plan Mode（`Shift+Tab`）でまず計画を確認してから実装に移る癖をつけると手戻りが減る。

### 4. 生成コードをレビューせずに使う

Claude Codeが生成するコードは高品質だが、100%正しいわけではない。特にセキュリティに関わる部分（認証、権限チェック、SQLクエリ）は必ず人間がレビューする。

### 5. Memoryを放置する

古い情報がMemoryに残っていると、Claude Codeが間違った前提で動く。定期的に内容を確認し、不要な情報は削除する。

---

## まとめ

Claude Codeの導入は、インストールして終わりではない。設定ファイル群を育てることで、Claude Codeが本当に使えるツールになる。

| 設定 | 何をするか | 効果 |
|------|----------|------|
| `settings.json` | 権限の allow/deny 設計 | 安全かつスムーズな操作 |
| グローバル `CLAUDE.md` | 全プロジェクト共通ルール | エージェントルーティング |
| プロジェクト `CLAUDE.md` | 技術スタック、規約、罠 | 毎回の説明が不要に |
| カスタムスキル | スラッシュコマンド化 | 複雑な業務を一発実行 |
| サブエージェント | 専門AIの並列実行 | レビュー・実装の高速化 |
| Memory | セッション間の知識共有 | 同じ失敗を繰り返さない |
| MCP | 外部ツール連携 | DB・APIを直接操作 |

まずはインストールして、CLAUDE.mdを書いて、settings.jsonでdenyリストを設定する。そこから始めて、カスタムスキルやサブエージェントに手を広げていけば、Claude Codeはどんどん使えるようになる。
