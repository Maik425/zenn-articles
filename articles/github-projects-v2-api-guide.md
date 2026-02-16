---
title: "GitHub Projects v2 API完全攻略 — 実務でハマった罠と突破法"
emoji: "🎯"
type: "tech"
topics: ["GitHub", "GraphQL", "API", "自動化", "ProjectsV2"]
published: false
---

## やりたかったこと

GitHub Projects v2は、IssueやPRをKanbanボード風に管理できる機能だ。Web UIで使う分には直感的だが、APIで操作しようとした途端、難易度が跳ね上がる。

個人のタスク管理を自動化したくて、Projects v2 APIに手を出した。やったのはこのあたり。

- Issueを一括作成してProjectに自動追加
- ステータスの自動変更（Todo、In Progress、Done）
- ミーティング議事録からTODOを抜き出してIssue化し、Projectに登録

自動化自体はうまくいった。ただ、**公式ドキュメントに書いていない罠**を何度も踏んだ。同じところで時間を溶かす人が減るよう、ゼロから書き残しておく。

### この記事でできるようになること

`gh` CLIを使って、以下の操作を一通りこなせるようになる。

1. Projectの情報を取得する
2. Issueを作成してProjectに追加する
3. ステータスや優先度を変更する

コード例はすべて **`gh api graphql`** で書いた。コピペして手元で動かせる。

---

## Projects v2 APIの全体像

### v1とv2は完全に別物

GitHubにはProjects (classic)とProjects v2がある。名前は似ているが、**APIレベルでは完全に別物**だ。

| | Projects (classic) | Projects v2 |
|---|---|---|
| API | REST API | **GraphQL API** |
| エンドポイント | `/repos/{owner}/{repo}/projects` | `https://api.github.com/graphql` |
| 状態 | 非推奨 | 現行 |

この記事で扱うのは **v2だけ**だ。ネット上の古い情報はv1向けのものが多いので注意してほしい。

### RESTとGraphQLの役割分担

Projects v2の操作では、**2つのAPIを使い分ける**ことになる。

```
Issueの作成・更新 → REST API（従来通り）
Projectへの追加・フィールド操作 → GraphQL API（v2専用）
```

ここが最初のつまずきポイントだった。Issueを作るだけならRESTで済む。でもそのIssueをProjectに追加したり、ステータスを変えたりするにはGraphQLが必須になる。REST一本では完結しない。

---

## 準備 — 認証トークンの取得

### Fine-grained PATでは動かない

GitHubは最近、**Fine-grained Personal Access Token**を推奨している。権限をきめ細かく設定できる新しいトークンだ。しかし、**Projects v2のGraphQL APIはFine-grained PATに対応していない**。

```
# Fine-grained PATだとこうなる
gh api graphql -f query='{ viewer { projectsV2(first: 5) { nodes { title } } } }'
# → エラー or 空の結果
```

ここでかなり時間を使った。**Classic Personal Access Token（`ghp_` で始まるトークン）でないと動かない。**

### Classic PATの作り方

1. [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens) を開く
2. Generate new token (classic) をクリック
3. スコープにチェックを入れる
   - `repo` — Issue操作に必要
   - `project` — Projects v2操作に必要
   - `read:org` — Organizationの Projectを扱う場合
4. トークンを生成してコピー

### gh CLIに認証を通す

```bash
gh auth login
# → "Paste an authentication token" を選んでClassic PATを入力

# 動作確認
gh api graphql -f query='{ viewer { login } }'
# → {"data":{"viewer":{"login":"あなたのユーザー名"}}}
```

:::message
APIを直接叩く場合、Authorizationヘッダーは `Bearer` 形式を使う。

```
# ✅ 正しい
Authorization: Bearer ghp_xxxxxxxxxxxx

# ❌ 動くけど非推奨
Authorization: token ghp_xxxxxxxxxxxx
```
:::

---

## GraphQLの基礎 — GitHub APIで使う最低限

GraphQLに触れたことがない人向けに、必要最低限だけ押さえておく。

### RESTとの違い

REST APIは機能ごとにエンドポイントが分かれている。

```
GET  /repos/owner/repo/issues       ← Issue一覧
GET  /repos/owner/repo/issues/1     ← Issue #1 の詳細
POST /repos/owner/repo/issues       ← Issue作成
```

GraphQLはエンドポイントが**1つだけ**。欲しいデータをクエリで指定する。

```bash
# すべてこの1つのエンドポイントにPOSTする
gh api graphql -f query='...'
```

### queryとmutation

GraphQLの操作は2種類しかない。

- **`query`** — データの読み取り。RESTのGETに相当する
- **`mutation`** — データの書き込み。RESTのPOST/PATCH/DELETEに相当する

```bash
# query：自分のログイン名を取得
gh api graphql -f query='
  query {
    viewer {
      login
    }
  }
'

# mutation：Projectにアイテムを追加
gh api graphql -f query='
  mutation {
    addProjectV2ItemById(input: {projectId: "xxx", contentId: "yyy"}) {
      item { id }
    }
  }
'
```

### Node IDという厄介な概念

GitHub GraphQL APIでは、すべてのリソースが**グローバルなNode ID**を持っている。

```
User:       MDQ6VXNlcjEyMzQ1
Project:    PVT_kwHOA8RUPc4BOtNm
Issue:      I_kwDONJlQ5s6m...
Field:      PVTSSF_lAHOA8RU...
```

REST APIの数値ID（`#123`）とは別物で、GraphQLの操作にはこのNode IDが必要になる。ここを理解しておかないと、このあとの手順で確実に詰まる。

---

## ステップ1 — Projectの情報を取得する

### Project一覧を取得

まず操作したいProjectのIDを調べる。

```bash
gh api graphql -f query='
  query {
    viewer {
      projectsV2(first: 20) {
        nodes {
          id
          number
          title
          url
        }
      }
    }
  }
'
```

結果はこう返ってくる。

```json
{
  "data": {
    "viewer": {
      "projectsV2": {
        "nodes": [
          {
            "id": "PVT_kwHOA8RUPc4BOtNm",
            "number": 1,
            "title": "maik-LIFE タスク管理",
            "url": "https://github.com/users/Maik425/projects/1"
          }
        ]
      }
    }
  }
}
```

`id`の`PVT_`で始まる文字列を控えておく。以降のすべての操作でこのIDを使う。

### フィールド一覧を取得する

ProjectにはStatusやPriorityといったフィールドがある。これらを操作するには、フィールドのIDと、各選択肢のIDの両方を知っておく必要がある。

```bash
gh api graphql -f query='
  query {
    node(id: "PVT_kwHOA8RUPc4BOtNm") {
      ... on ProjectV2 {
        fields(first: 20) {
          nodes {
            ... on ProjectV2Field {
              id
              name
            }
            ... on ProjectV2SingleSelectField {
              id
              name
              options {
                id
                name
              }
            }
            ... on ProjectV2IterationField {
              id
              name
            }
          }
        }
      }
    }
  }
'
```

:::message alert
**罠 — フィールドの型が3種類ある**

Projects v2のフィールドには `ProjectV2Field`、`ProjectV2SingleSelectField`、`ProjectV2IterationField` の3つの型がある。GraphQLの**インラインフラグメント**（`... on Type { }`）で3つとも指定しないと、一部のフィールドが返ってこない。

```graphql
# ❌ これだとStatusやPriorityが取れない
fields(first: 20) {
  nodes {
    id
    name
  }
}

# ✅ フラグメントで3種類すべて指定する
fields(first: 20) {
  nodes {
    ... on ProjectV2Field { id name }
    ... on ProjectV2SingleSelectField { id name options { id name } }
    ... on ProjectV2IterationField { id name }
  }
}
```
:::

取得結果から、必要なIDをメモしておく。

```
Status フィールド ID:   PVTSSF_lAHOA8RUPc4BOtNmzg9VCog
  - Todo:              f75ad846
  - In Progress:       47fc9ee4
  - Review:            e2ca4b48
  - Done:              98236657

Priority フィールド ID: PVTSSF_lAHOA8RUPc4BOtNmzg9ZIxI
  - 🔴高:              581cc2eb
  - 🟡中:              c315e4e5
  - 🟢低:              b84312df
```

このIDの控えが、後続ステップでそのまま使える。

---

## ステップ2 — Issueを作成してProjectに追加する

ここからREST + GraphQLのハイブリッドになる。

### 2-1. REST APIでIssueを作成

Issueの作成は従来のREST APIで行う。

```bash
gh api repos/Maik425/maik-LIFE/issues \
  -f title="サンプルタスク" \
  -f body="テスト用のIssueです" \
  -f labels[]="priority:中" \
  -f labels[]="type:dev"
```

返ってきたJSONの `number`（例えば `42`）を控える。

### 2-2. GraphQLでIssueのNode IDを取得

REST APIが返すのは数値のIssue番号（`#42`）だが、GraphQLの操作にはNode IDが要る。そこで変換のクエリを挟む。

```bash
gh api graphql -f query='
  query {
    repository(owner: "Maik425", name: "maik-LIFE") {
      issue(number: 42) {
        id
      }
    }
  }
'
```

```json
{
  "data": {
    "repository": {
      "issue": {
        "id": "I_kwDONJlQ5s6mXXXXXX"
      }
    }
  }
}
```

### 2-3. Projectに追加

IssueのNode IDが手に入ったら、Projectに追加する。

```bash
gh api graphql -f query='
  mutation {
    addProjectV2ItemById(input: {
      projectId: "PVT_kwHOA8RUPc4BOtNm",
      contentId: "I_kwDONJlQ5s6mXXXXXX"
    }) {
      item {
        id
      }
    }
  }
'
```

返ってきた `item.id` がProject内でのアイテムIDだ。次のステップでステータス変更に使う。

### 整理すると3ステップ

```
1. REST:    Issue作成 → Issue番号を取得
2. GraphQL: Issue番号 → Node IDを取得
3. GraphQL: Node ID → Projectに追加 → アイテムIDを取得
```

たったIssueをProjectに追加するだけで3ステップ。面倒だが、これがProjects v2 APIの現状だ。

---

## ステップ3 — ステータスや優先度を変更する

Projectに追加したアイテムのステータスをTodoに設定してみる。

### フィールド値の更新

```bash
gh api graphql -f query='
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: "PVT_kwHOA8RUPc4BOtNm",
      itemId: "PVTRI_xxxxxxxxxx",
      fieldId: "PVTSSF_lAHOA8RUPc4BOtNmzg9VCog",
      value: {
        singleSelectOptionId: "f75ad846"
      }
    }) {
      projectV2Item {
        id
      }
    }
  }
'
```

各パラメータの意味はこの通り。

| パラメータ | 値 | 説明 |
|---|---|---|
| `projectId` | `PVT_kwHO...` | ProjectのID |
| `itemId` | `PVTRI_...` | ステップ2-3で取得したアイテムID |
| `fieldId` | `PVTSSF_...Cog` | StatusフィールドのID |
| `value.singleSelectOptionId` | `f75ad846` | TodoのOption ID |

:::message
**罠 — valueの指定方法がフィールド型で異なる**

`value` パラメータの形式はフィールドの型ごとに違う。

```graphql
# Single Select（Status, Priorityなど）
value: { singleSelectOptionId: "option_id" }

# テキストフィールド
value: { text: "テキスト" }

# 数値フィールド
value: { number: 42 }

# 日付フィールド
value: { date: "2025-01-01" }
```

Single Selectの場合、**Optionの名前ではなくIDを指定する**。だからステップ1でフィールド一覧を取得して、Option IDを控えておく必要があった。
:::

Priorityも同じ要領で、`fieldId` と `singleSelectOptionId` を差し替えるだけでいい。

```bash
gh api graphql -f query='
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: "PVT_kwHOA8RUPc4BOtNm",
      itemId: "PVTRI_xxxxxxxxxx",
      fieldId: "PVTSSF_lAHOA8RUPc4BOtNmzg9ZIxI",
      value: {
        singleSelectOptionId: "581cc2eb"
      }
    }) {
      projectV2Item {
        id
      }
    }
  }
'
```

---

## 運用で踏んだ地雷集

自動化スクリプトを実際に動かして遭遇したエラーと、その対処法を並べておく。

### 地雷1 — GraphQL 502エラー

Issueを一括でProjectに追加していると、突然 **502 Bad Gateway** が返ってくる。

```
Error: GraphQL: 502 Bad Gateway
```

GitHubサーバー側の一時的なエラーで、バッチ処理で連続リクエストすると起きやすい。対処はリトライと指数バックオフだ。

```bash
# シェルスクリプトでのリトライ例
for i in 1 2 3; do
  result=$(gh api graphql -f query='...' 2>&1)
  if echo "$result" | grep -q '"data"'; then
    break
  fi
  echo "リトライ ${i}/3..."
  sleep $((2 ** i))  # 2秒, 4秒, 8秒
done
```

### 地雷2 — レート制限

GitHub GraphQL APIのレート制限は**1時間あたり5,000ポイント**。クエリの複雑さでポイント消費が変わる。大量にリクエストを飛ばすならsleepを挟んでおく。

```bash
for issue_number in 1 2 3 4 5; do
  # ... GraphQLリクエスト ...
  sleep 1
done
```

### 地雷3 — 存在しないラベルで422エラー

Issue作成時に、リポジトリに存在しないラベルを指定すると **422 Validation Failed** が返る。

```json
{
  "message": "Validation Failed",
  "errors": [{"value": "priority:高", "resource": "Label", "code": "invalid"}]
}
```

事前にラベルを作っておけば済む話だが、忘れがちだ。

```bash
# ラベルを作成（既に存在すれば422が返るが問題ない）
gh api repos/Maik425/maik-LIFE/labels \
  -f name="priority:高" \
  -f color="d73a4a" \
  -f description="優先度：高"
```

### 地雷4 — Organizationの Projectにアクセスできない

個人のProjectは `viewer.projectsV2` で取得できるが、OrganizationのProjectは別のクエリが要る。

```bash
gh api graphql -f query='
  query {
    organization(login: "your-org") {
      projectsV2(first: 20) {
        nodes {
          id
          title
        }
      }
    }
  }
'
```

加えて、PATのスコープに `read:org` を付けておく必要がある。

---

## 応用 — 実際の自動化パイプライン

### ミーティング議事録からIssueを自動生成

実際に運用している自動化パイプラインはこんな流れだ。

```
議事録テキスト
  ↓ TODOを抽出（LLMで解析）
  ↓ REST APIでIssue作成（ラベル・担当者付き）
  ↓ GraphQLでIssue Node ID取得
  ↓ GraphQLでProjectに追加
  ↓ GraphQLでStatus = "Todo" に設定
```

ミーティングが終わったら議事録を流し込む。それだけでProjectボードにTODOが並ぶ。

### Claude Codeのスキルとして組み込む

GitHub CLIとGraphQLクエリをClaude Codeのカスタムコマンドとして登録しておくと、自然言語でタスク管理ができる。

```
> /create-issues
「認証機能のリファクタリング」「テスト追加」「ドキュメント更新」を
priority:中 で作成してProjectに追加して
```

---

## 振り返り

### 3つの大きな罠

| # | 罠 | 対策 |
|---|---|---|
| 1 | Fine-grained PATでは動かない | **Classic PAT**（`ghp_*`）を使う |
| 2 | フィールド取得にフラグメントが必要 | `... on ProjectV2SingleSelectField` 等を3種類書く |
| 3 | Option IDを事前に知る必要がある | フィールド一覧を取得してIDをメモしておく |

### 操作フローの全体像

```
[REST] Issue作成
  ↓ issue_number
[GraphQL] Issue Node ID取得
  ↓ content_id
[GraphQL] Projectに追加（addProjectV2ItemById）
  ↓ item_id
[GraphQL] ステータス設定（updateProjectV2ItemFieldValue）
```

RESTとGraphQLのハイブリッドだという点さえ飲み込めば、あとは同じパターンの繰り返しだ。一度クライアントを組んでしまえば、タスク管理の自動化がかなり自由にできるようになる。
