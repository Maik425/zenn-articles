---
title: "Claude Codeのカスタムスキルで日常業務を自動化した話"
emoji: "🤖"
type: "tech"
topics: ["claudecode", "ai", "automation", "cli", "productivity"]
published: true
meta_description: "Claude Codeのカスタムスキル機能を使い、Issue作成・タスク管理・MTG録画・記事執筆まで日常業務を自動化した実例とノウハウを紹介。スラッシュコマンド1つで複雑な業務フローが動き出すまでの試行錯誤を、スキル8つぶん丸ごと解説します。"
featured_image: "" # TODO: アイキャッチ画像を設定（推奨: 1200x630px）
---

## Claude Codeのカスタムスキルとは

Claude Codeには `~/.claude/commands/` にMarkdownファイルを置くだけで、自分だけのスラッシュコマンドを追加できる機能がある。カスタムスキルと呼ばれている。

`/create-issues` でGitHub Issueを一括作成し、`/record-meeting` で会議の録画から議事録生成まで一気に走る。やっていることはClaude Codeへの指示書をファイルに書いておくだけ。それだけなのに、想像以上に使える。

### なぜスキルを作るのか

Claude Codeは毎回チャットで頼めばだいたいやってくれる。それでもスキルを作る理由が3つある。

**1. 手順の再現性**

Issue作成、Project追加、ステータス設定、優先度設定。この手順を毎回口で伝えるのは面倒だし、どこかで抜ける。スキルに書いておけば同じ品質で何度でも回せる。

**2. 暗黙知の明文化**

ラベルは `priority:高` の形式、担当者名はGitHubユーザー名にマッピング。こういう暗黙のルールをスキルに埋め込んでおける。自分が忘れてもClaude Codeが覚えている。

**3. ワークフローの起動コスト削減**

MTG録画、文字起こし、議事録生成、共有メッセージ作成、TODO同期。この5ステップが `/record-meeting` の一言で走り出す。体験としてかなり大きい。

### 基本の仕組み

`~/.claude/commands/` に `.md` ファイルを置く。ファイル名がそのままコマンド名になる。

```
~/.claude/commands/
├── create-issues.md      → /create-issues
├── task-support.md       → /task-support
├── record-meeting.md     → /record-meeting
├── start.md              → /start
├── update-daily.md       → /update-daily
├── article-research.md   → /article-research
├── article-humanize.md   → /article-humanize
└── meeting-prep.md       → /meeting-prep
```

中身はMarkdownで書いたClaude Codeへの指示書だ。見出し、箇条書き、コードブロックで手順を記述する。特別な構文はほぼない。`$ARGUMENTS` という変数でスラッシュコマンドの引数を受け取れるのが唯一の独自機能になる。

```markdown
# Issue一括作成 (/create-issues)

$ARGUMENTS に渡されたタスクリストからIssueを一括作成する。

## 手順

1. $ARGUMENTS のタスクリストをパースする
2. 各タスクに対して gh issue create を実行
3. 作成したIssueをProjectに追加する
...
```

人間がClaude Codeに毎回伝えていた指示を、ファイルに永続化したもの。それがスキルだ。


## 自分が作ったスキル一覧

現時点で8つ動かしている。用途別に整理するとこうなる。

### タスク管理系

- `/create-issues` — タスクリストからGitHub Issueを一括作成し、Projectに追加
- `/task-support` — GitHub Projects v2のボードを表示し、ステータス更新を対話的に実行
- `/update-daily` — その日の完了タスクをデイリーノートに記録

### 会議系

- `/record-meeting` — 画面+音声録画→文字起こし→議事録→共有メッセージ→TODO同期
- `/meeting-prep` — 前回議事録から未完了TODOとアジェンダたたき台を生成

### 記事執筆系

- `/article-research` — ファクトチェック・SEO分析・競合調査でブラッシュアップ
- `/article-humanize` — AI文体を除去して自然な日本語に書き直し

### ナビゲーション系

- `/start` — 作業開始メニュー。何をするか選ぶと適切なスキルやプロジェクトに誘導

ではここから、スキルの作り方と実例を見ていく。


## スキルの作り方 — 3ステップ

### ステップ1: ファイルを作る

`~/.claude/commands/` に `.md` ファイルを置く。

```bash
mkdir -p ~/.claude/commands
touch ~/.claude/commands/my-skill.md
```

### ステップ2: 指示を書く

Markdownで手順を書く。Claude Codeに口頭で伝えるのと同じ感覚でいい。

```markdown
# デプロイ確認 (/deploy-check)

本番環境のヘルスチェックを実行し、結果を報告する。

## 手順

1. curl で /health エンドポイントを叩く
2. レスポンスのステータスコードを確認
3. 200以外なら警告を出す
4. 結果をSlackメッセージ形式で出力する
```

### ステップ3: 使う

Claude Codeのチャットで `/deploy-check` と打つだけ。引数を渡すなら `/deploy-check staging` と空白の後に続ける。スキル内では `$ARGUMENTS` で `staging` を受け取れる。

ここまでが基本の流れだ。では実際に動かしているスキルの中身に入ろう。


## 実例で解説 `/create-issues`

最初に作ったスキルで、一番よく使っている。テキストのタスクリストをGitHub Issueに変換する。

### 何が面倒だったか

会議やチャットで出たタスクを手作業でIssue化する。1件あたりタイトル入力、ラベル選択、Project追加、ステータス設定、優先度設定で5ステップ。10件あれば50ステップになる。

このスキルならタスクリストを渡すだけで全部終わる。

### 引数の受け取りと解析

```markdown
## 入力形式

$ARGUMENTS にタスクリストが渡される。以下の形式に対応する:

- 箇条書き: `- タスク名`
- 番号付き: `1. タスク名`
- 担当者付き: `- タスク名 @担当者`
- 優先度付き: `- タスク名 !高`
```

`$ARGUMENTS` は文字列としてそのまま渡される。解析はClaude Codeに任せている。フォーマットが多少揺れても文脈から判断してくれるのがスキルの強みだ。厳密なパーサーを書かなくていい。

### ラベルの自動判定

スキル内にマッピングテーブルを持たせている。

```markdown
## ラベルマッピング

タスクの内容からラベルを自動判定する:

- 高、急ぎ、至急 → `priority:高`
- 中 → `priority:中`
- 低、余裕 → `priority:低`
- 開発、実装、バグ → `type:dev`
- 記事、ブログ、SNS → `type:marketing`
```

CI修正なら `type:dev`、ブログ記事執筆なら `type:marketing` が自動で付く。完璧ではないが8割は当たるので、外れた分だけ手で直せばいい。

### Issue作成からProject追加までのフロー

スキルの核心部分はこう書いている。

```markdown
## 実行手順

1. タスクリストをパースし、各タスクのタイトル・ラベル・担当者を抽出
2. 各タスクに対して:
   a. `gh issue create` でIssueを作成
   b. GraphQL で Issue の node_id を取得
   c. `addProjectV2ItemById` でProjectに追加
   d. `updateProjectV2ItemFieldValue` でStatusをTodoに設定
   e. 優先度があれば同様にPriorityフィールドを設定
3. 作成したIssue一覧を表示
```

REST APIとGraphQLが混在しているのは、GitHub Projects v2の仕様上やむを得ない。Issue作成はREST、Project操作はGraphQLでしか動かない。こういう知識もスキルに埋めておけば、毎回説明せずに済む。

### IDの埋め込み

Project IDやフィールドIDなどの定数もスキルに直接書いてある。

```markdown
## 定数

- Project ID: `PVT_xxxxxxxxxxxxxxxxxxxx`
- Status Field ID: `PVTSSF_xxxxxxxxxxxxxxxxxxxxxxxx`
- Status Options:
  - Todo: `abcd1234`
  - In Progress: `efgh5678`
  - Done: `ijkl9012`
```

IDの値はダミーだが、実際のスキルには本物を書いている。これがないとClaude Codeは毎回「Project IDは？」と聞いてくる。一度調べたIDを書いておくだけで、完全に自動化できる。


## 実例で解説 `/record-meeting`

一番複雑で、一番手応えがあったスキルだ。会議の録画から議事録共有まで5つのフェーズを一気通貫で回す。

### 全体フロー

```
録画開始 → 録画停止 → 文字起こし → 議事録生成 → 共有メッセージ → TODO同期
```

手でやると30分。スキルなら待ち時間込みで10分。人間がやるのは録画停止のCtrl+Cと、TODOをIssueに登録するかどうかの判断だけだ。

### AskUserQuestionで対話的に進める

このスキルの特徴はClaude Codeの `AskUserQuestion` を使っている点にある。

```markdown
1. **AskUserQuestion でMTGタイプを選択**

   質問: 「MTGタイプを選択してください」
   選択肢:
   - 社内定例 (internal)
   - クライアントMTG (client)
   - プロジェクト会議 (project)
   - 1on1
```

こう書いておくとClaude Codeが選択肢付きの質問を出す。ユーザーはクリックで選ぶだけ。スキル実行中に必要な情報を対話的に集められる。

### 引数でショートカットする

一方で毎回質問に答えるのが面倒な場面もある。そこで引数によるスキップも用意した。

```markdown
## 引数

`$ARGUMENTS` が渡された場合:
- `internal` → 社内定例で即開始
- `client` → クライアントMTGで即開始
- `audio-only` → 音声のみモードで即開始
```

`/record-meeting internal` で質問なしに即録画が始まる。対話モードと即時モードの両方を持たせておくと使い勝手がいい。

### 外部スクリプトの呼び出し

録画にはPythonスクリプトを使っている。呼び出し方もスキルに書いてある。

```markdown
## 録画を開始

作業ディレクトリ: `/home/user/projects/my-app/_automation`

```bash
# 画面+音声モード
.venv/bin/python on_demand/meeting_recorder.py \
  --start --transcribe --device "BlackHole 2ch"
```
```

作業ディレクトリ、仮想環境のパス、コマンドオプション。環境固有の情報をスキルに持たせておくと、Claude Codeが迷わず実行できる。


## 実例で解説 `/task-support`

GitHub Projects v2のカンバンボードをCLIで操作するスキルだ。ブラウザを開かずにタスクのステータスを確認・更新できる。

### GraphQLクエリを埋め込む

Projects v2のデータ取得にはGraphQLが必要になる。スキルにクエリそのものを書いている。

```markdown
## ボード表示用クエリ

```graphql
query {
  node(id: "PVT_xxxxxxxxxxxxxxxxxxxx") {
    ... on ProjectV2 {
      items(first: 50) {
        nodes {
          content { ... on Issue { number title } }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
              }
            }
          }
        }
      }
    }
  }
}
```
```

Claude Codeがこのクエリを `gh api graphql` で叩き、結果をステータス別に整形して表示する。

### ステータス更新は対話で

表示後、ユーザーが更新したいタスクと新しいステータスを選ぶ。

```markdown
## ステータス更新

1. AskUserQuestionで更新するIssue番号を質問
2. AskUserQuestionで新しいステータスを選択:
   - Todo
   - AI - In Progress
   - Human - In Progress
   - review
   - Done
3. GraphQLのupdateProjectV2ItemFieldValueで更新
```

ブラウザでドラッグ&ドロップする代わりに、CLIの対話で同じことをやる。コードを書きながらタスク管理できるのが地味にいい。


## スキルを作るときのコツ

8つ作ってきて見えたことを並べる。

### 1. 雑に書いて、使いながら育てる

最初から完璧を目指さない。最低限の手順だけ書いて動かし、Claude Codeが迷った箇所や情報が足りなかった箇所を改善していく。

`/create-issues` は最初、ラベルマッピングもProject IDもなかった。使うたびにProject IDを聞かれるのが面倒で追加し、ラベルを毎回指定するのが面倒で自動判定を足した。

### 2. 定数はスキルに直接書く

APIのエンドポイント、Project ID、フィールドID、ラベル名、担当者マッピング。定数はスキルファイルにそのまま書く。

環境変数で管理したくなるかもしれないが、読み手はClaude Codeだ。Markdownのテーブルで渡したほうが確実に読み取ってくれる。

### 3. AskUserQuestion と $ARGUMENTS を両方用意する

初めて使うときや選択肢が多いときは `AskUserQuestion` で対話的に進める。慣れたら `$ARGUMENTS` で一発起動。両方あるのが一番使いやすい。

```markdown
## 引数

$ARGUMENTS が渡された場合:
- `internal` → 社内定例で即開始（ヒアリングをスキップ）
- 上記以外 → MTGタイプとして解釈を試みる
- 引数なし → AskUserQuestion で対話的に選択
```

### 4. パスは絶対パスで書く

Claude Codeのカレントディレクトリは変わることがある。スキル内のファイルパスは絶対パスにしておく。

```markdown
# NG
.venv/bin/python scripts/run.py

# OK
作業ディレクトリ: /home/user/projects/my-app/_automation
/home/user/projects/my-app/_automation/.venv/bin/python \
  on_demand/meeting_recorder.py
```

### 5. エラーケースも書く

指示にないエラーに遭遇するとClaude Codeは独自に対処しようとする。それが望ましくない場合もある。

```markdown
## エラー時の対応

- GraphQL 502エラー → 2〜5秒待ってリトライ（最大3回）
- ラベルが存在しない → 自動作成してからIssueを作成
- 前回議事録が見つからない → 空のアジェンダたたき台を表示
```

想定されるエラーと対処をあらかじめ書いておけば、変な方向に暴走しない。

### 6. サブエージェントに委任する

`/article-research` では `research-analyst` エージェントにWebリサーチを任せている。スキルからTask ツールでサブエージェントを呼び出す指示を書けば、専門的な処理を切り出せる。

```markdown
## research-analyst エージェントにリサーチを依頼

Task ツールで research-analyst エージェントを起動し、以下を依頼する:
- ファクトチェック
- 一次ソース確認
- 背景情報の補強
- 競合記事の確認
```

スキル本体はワークフロー制御に徹して、専門処理はサブエージェントに渡す。この分離がうまく機能している。


## /start — スキルへのエントリーポイント

最後に `/start` を紹介したい。これは他のスキルへのルーターだ。

```markdown
# 作業開始メニュー (/start)

AskUserQuestion で作業カテゴリを選択:
- 開発作業 → プロジェクト選択 → 該当ディレクトリで作業開始
- タスク管理 → /task-support or /create-issues に誘導
- 記事作成 → /article-research → /article-humanize の流れを案内
- 自動化パイプライン → 設定や実行のサポート
- 管理・リサーチ → 汎用的な調査や管理作業
```

朝の作業開始時に `/start` と打てば、今日やることを選んで適切なスキルに飛べる。スキルの数が増えてくるとこういうナビゲーションが地味に助かる。


## 振り返り

カスタムスキルを使い始めて約2ヶ月が経った。Markdownで手順を書くだけという手軽さと、Claude Codeの柔軟な解釈力が噛み合って、想像以上に実用的な自動化ができている。

作りながら気づいたのは、スキルはコードではなくドキュメントだということ。プログラミング言語の文法は要らない。自分の業務フローを日本語で書き下ろしてClaude Codeに読ませるだけでいい。

万能ではない。Claude Codeの解釈に頼る以上、厳密な制御が必要な処理には向かない。人間がやっていた手作業をClaude Codeに代行させる、というのがスキルの守備範囲だ。

8つのスキルがすっかり業務ルーティンに入り込んでいる。Claude Codeを日常的に使っているなら、一番よく繰り返す作業から1つ試してみるといい。
