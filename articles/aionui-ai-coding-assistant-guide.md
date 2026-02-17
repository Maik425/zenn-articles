---
title: "AionUi入門：8種類のAIコーディングアシスタントを一元管理できる無料ツール"
emoji: "🖥️"
type: "tech"
topics: ["AionUi", "AIエージェント", "オープンソース", "ClaudeCode", "GeminiCLI"]
published: true
---

## 複数のAIアシスタントを1つのアプリで管理する

2026年に入ってAIコーディングアシスタントの選択肢が一気に増えた。Gemini CLI、Claude Code、Codex、Qwen Code。それぞれ得意分野が違う。ただ、これらを同時に使い分けようとすると、ターミナルウィンドウがどんどん増えて収拾がつかなくなる。

**AionUi**はその問題を解決するツールだ。iOfficeAIが開発したオープンソースのデスクトップアプリで、複数のAIコーディングアシスタントをひとつのGUIから操作できる。GitHubでは14,800以上のスターがついている。

開発の出発点になったのはAnthropic社のClaude Coworkだ。Claude CoworkはmacOS専用でClaude限定という制約があった。AionUiはその制約を外し、Windows・Linux・macOSのクロスプラットフォームで動作する。対応AIモデルもClaudeに限らない。

主な特徴は5つある。

- **マルチAIエージェント管理** — Gemini CLI、Claude Code、Codex、OpenCode、Qwen Code、Goose CLI、Auggie、OpenClawの8種類以上を統合
- **完全ローカル動作** — データはSQLiteでローカル保存。外部サーバーには送信しない
- **スケジュールタスク** — 定型作業を24時間自動実行できる
- **WebUIモード** — ブラウザ経由でリモートアクセスできる
- **オフィス自動化** — ファイル管理、ドキュメント生成、画像編集などの補助機能がある

ライセンスはApache 2.0。ツール自体は完全無料だ。ただし各AIサービスのAPIキーは別途必要になる。Ollamaなどのローカルモデルを使えばAPI費用もかからない。

## AionUiで使えるAIアシスタント8種

AionUiはローカルにインストール済みのAIコーディングアシスタントを自動検出し、GUIから操作できるようにする。対応ツールを一覧にまとめた。

| ツール名 | 提供元 | 特徴 |
|---------|--------|------|
| **Gemini CLI** | Google | AionUiに内蔵済み。追加インストール不要で、無料枠は60リクエスト/分 |
| **Claude Code** | Anthropic | エージェント型コーディング。複雑な推論タスクに強い |
| **Codex** | OpenAI | o3モデルベース。12以上の言語に対応 |
| **OpenCode** | OSS | MITライセンス。70,000以上のスターを持つ人気ツール |
| **Qwen Code** | Alibaba | Qwen3-Coderベース。無料枠は2,000リクエスト/日 |
| **Goose CLI** | Block | MCP対応。マルチモデル構成が可能 |
| **Auggie** | Augment Code | 10,000コミット分の履歴解析が可能 |
| **OpenClaw** | 独立プロジェクト | セルフホスト型のAIアシスタント |

注意しておきたいのは、これらがすべて独立した外部プロジェクトだという点だ。AionUiが独自にライブラリを内蔵しているわけではない。各ツールのCLIインターフェースを自動検出して橋渡しする設計になっている。つまり使いたいツールは事前にインストールしておく必要がある。

各エージェントは独立したコンテキストメモリを保持する。プロジェクトAではClaude Code、プロジェクトBではGemini CLIという使い分けも簡単にできる。

## セットアップ — 5分で始める

### システム要件

| 項目 | 要件 |
|------|------|
| **OS** | macOS 10.15以上 / Windows 10以上 / Ubuntu 18.04以上 |
| **メモリ** | 4GB RAM以上 |
| **ストレージ** | 500MB以上の空き容量 |
| **ネットワーク** | インターネット接続（クラウドAPIを使う場合） |

### インストール

**macOS（Homebrew推奨）**

```bash
brew install aionui
```

**手動インストール（全OS共通）**

[GitHub Releases](https://github.com/iOfficeAI/AionUi/releases)ページからOSに合ったインストーラーをダウンロードする。

- macOS: `.dmg` ファイル
- Windows: `.exe` ファイル
- Linux: `.deb` または `.AppImage` ファイル

### 初期設定

インストールしたら、使いたいAIモデルのAPIキーを設定する。

**Gemini（Google）** — Google AI Studioでキーを取得する。AionUiにはGemini CLIが内蔵されているため、APIキーさえあればすぐに使える。

**その他のAIサービス** — OpenAI、Anthropic、Qwen等のAPIキーは各ダッシュボードから取得する。

**ローカルモデル（Ollama / LM Studio）** — APIキー不要。OllamaかLM Studioを起動しておけばAionUiが自動検出する。

外部CLIツールを使う場合は別途インストールしておくこと。

```bash
# Claude Codeのインストール例
npm install -g @anthropics/claude-code

# Qwen Codeのインストール例
npm install -g qwen-code
```

AionUiを起動すれば、インストール済みのツールが自動で検出される。

## コーディング以外の機能も充実している

AionUiの中核はAIアシスタントの統合管理だが、開発者の日常を助ける周辺機能もある。

### ファイル管理

9種類以上のファイル形式をプレビューできる。PDF、Word、Excel、PowerPoint、コード、Markdown、画像、HTMLなどだ。AIによるフォルダ整理や一括リネーム機能もついている。

たとえば散らかったダウンロードフォルダを、プロジェクト別やファイル種別で自動分類させるといった使い方ができる。

### ドキュメント自動生成

AIを使ってPowerPoint、Word、Markdownドキュメントを自動生成できる。Excelレポートの解析・整形にも対応している。報告書づくりの手間が減る。

### スケジュールタスク

定型作業のスケジュール実行ができる。毎朝9時にコミット履歴を要約してレポート生成、毎日18時にコードレビュー結果をまとめる、といった自動化が可能だ。AionUiが24時間稼働ツールと呼ばれる所以はここにある。

### WebUIモード

ブラウザからAionUiにアクセスするモードも用意されている。

```bash
aionui --webui --remote
```

このコマンドを実行するとLAN内の他デバイスからブラウザ経由で接続できる。TelegramやLark（Feishu）との連携にも対応しており、チャットアプリからAIアシスタントを操作することもできる。

## Claude Coworkとの違い

AionUiはClaude Coworkの拡張版として開発された。両者の違いを表にまとめた。

| 項目 | AionUi | Claude Cowork |
|------|--------|---------------|
| 対応OS | Windows / macOS / Linux | macOS専用 |
| 対応AIモデル | Gemini、Claude、OpenAI、Qwen、ローカルモデル等 | Claude専用 |
| 価格 | 無料（APIキーは別途） | $20/月〜 |
| データ保存場所 | ローカルSQLite | クラウド |
| オフライン動作 | 可能（ローカルモデル使用時） | 不可 |
| カスタマイズ性 | 高い（CSS変更、カスタムスキル拡張） | 限定的 |
| マルチセッション | 対応 | 対応 |
| MCP対応 | あり | あり |

Claudeだけ使うならClaude Coworkで十分だ。一方、複数のAIモデルを使い分けたい場合やWindows/Linuxで作業する場合はAionUiが合っている。コスト面でもAionUi自体が無料なのは大きい。

## AionUiが力を発揮する4つのケース

### ケース1 — 複数モデルの無料枠でコストゼロ開発

各AIサービスの無料枠を使い分ければ、月額$0で高度なAI支援を受けられる。

- Gemini CLI: 60リクエスト/分の無料枠。高頻度な簡単タスクに
- Qwen Code: 2,000リクエスト/日の無料枠。Python系の開発に
- Ollama（ローカル）: 完全無料。機密性の高いコードに

AionUiの統合管理画面からタスクに応じたモデルをワンクリックで切り替えられる。

### ケース2 — 機密コードの完全オフライン開発

セキュリティ要件が厳しく、コードを外部に送信できないプロジェクトもある。AionUiとOllama（またはLM Studio）を組み合わせれば、インターネット接続なしでAI支援を受けられる。データはすべてローカルに留まる。

### ケース3 — WebUIモードでのチーム共有

WebUIモードでAionUiをサーバー上で起動すれば、チームメンバー全員がブラウザからアクセスできる。過去のAI会話履歴を共有・検索できるので、チーム内のナレッジ共有にも使える。

### ケース4 — スケジュールタスクによる自動化

スケジュール機能で毎日決まった時間にAIタスクを自動実行できる。日次レポート生成、コードベースの定期チェック、ドキュメントの自動更新。繰り返し作業の自動化に向いている。

## よくある質問（FAQ）

### Q1. AionUiは本当に無料？

AionUi自体はApache 2.0ライセンスで完全無料だ。ただし、Gemini・OpenAI・Claude等のクラウドAIサービスを使えば各サービスのAPI利用料が発生する。OllamaなどのローカルモデルならAPI費用もかからない。

### Q2. OpenClawとの関係は？

OpenClawはAionUiとは独立した別プロジェクトだ。AionUiがOpenClawを独自に内蔵しているわけではない。AionUiはOpenClawを含む8種類以上のAIアシスタントを検出・統合するハブとして機能する。

### Q3. 日本語のドキュメントはある？

公式リポジトリに日本語READMEがある（[readme_jp.md](https://github.com/iOfficeAI/AionUi/blob/main/readme_jp.md)）。ただしWikiなどの詳細ドキュメントは英語中心だ。

### Q4. 既存の開発環境と干渉しない？

干渉しない。AionUiはElectronベースのデスクトップアプリとして動作する。各AIツールのCLIを内部で呼び出す設計なので、ターミナルから直接CLIを使う場合と同じ動作をGUI上で実行しているだけだ。

### Q5. MCPに対応している？

対応している。MCPサーバーの設定をAionUi内で管理できるため、外部データソースやツールとの連携をGUI上で構成できる。

## どんな人に向いているか

複数のAIコーディングアシスタントを1つのアプリから操作したい開発者にAionUiは合っている。

- 複数モデルを使い分けたいが、ターミナルの切り替えが面倒
- WindowsやLinuxでClaude Cowork相当の環境がほしい
- 機密コードを扱うので完全ローカルでAI支援を受けたい
- AIタスクをスケジュールで自動化したい

[公式リポジトリ](https://github.com/iOfficeAI/AionUi)からインストールして、内蔵のGemini CLIで動作を試してみてほしい。

## 参考リンク

- [GitHub - iOfficeAI/AionUi](https://github.com/iOfficeAI/AionUi)
- [AionUi Wiki - Getting Started](https://github.com/iOfficeAI/AionUi/wiki/Getting-Started)
- [AionUi 日本語README](https://github.com/iOfficeAI/AionUi/blob/main/readme_jp.md)
- [GitHub Releases（ダウンロード）](https://github.com/iOfficeAI/AionUi/releases)
