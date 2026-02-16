---
title: "Google製LangExtract入門：LLMでテキストから構造化データを抽出する実践ガイド"
emoji: "🔍"
type: "tech"
topics: ["langextract", "LLM", "Python", "自然言語処理", "Gemini"]
published: false
---

## 非構造化テキストからの情報抽出、もっと楽にならないか

テキストから必要な情報を抜き出す作業は地味に手間がかかる。spaCyでNERモデルを作り込んだり、正規表現をドメインごとに書き直したり。ドメインが変わるたびに再学習やルール整備が必要になるのは、正直しんどい。

Googleがオープンソースで公開した**LangExtract**は、この問題をLLMで解決するPythonライブラリだ。数個の例示を渡すだけで、任意のテキストから構造化情報を取り出せる。GitHubでは29,000以上のスターがついている。

特徴を5つ挙げる。

- **Few-shotアプローチ** — 数個の例示（ExampleData）だけで新しい抽出タスクに対応できる
- **ソース位置の記録** — 抽出結果が元テキストのどこから来たか、文字オフセットで追跡できる
- **HTML可視化** — 結果をブラウザ上でハイライト付きで確認できる
- **複数LLM対応** — Gemini、OpenAI GPT、Claude、Ollamaなど幅広いバックエンドが使える
- **長文処理** — テキストチャンキングと並列処理で大量ドキュメントにも対応する

ただし、Googleの公式サポート製品ではない。"Not an officially supported Google product"と明記されている。ライセンスはApache 2.0で、自由に利用・改変できる。

## 3ステップで動かす

Python 3.10以上が必要だ。

### ステップ1 — インストール

```bash
pip install langextract
```

### ステップ2 — APIキーの準備

LLMをバックエンドに使うため、モデルに応じたAPIキーがいる。Geminiなら Google AI Studioからキーを取得して環境変数に入れておく。

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

### ステップ3 — 初回の抽出を実行

テキストから組織名と製品名を抽出してみる。

```python
import langextract as lx

# 抽出の例示を定義する
examples = [
    lx.data.ExampleData(
        text="Googleは新しいAIツール「Gemini」を発表した。",
        extractions=[
            lx.data.Extraction(
                extraction_class="organization",
                extraction_text="Google",
                attributes={"type": "企業"}
            ),
            lx.data.Extraction(
                extraction_class="product",
                extraction_text="Gemini",
                attributes={"category": "AIツール"}
            )
        ]
    )
]

# 抽出を実行
result = lx.extract(
    text_or_documents="Microsoftは生成AIサービスCopilotの機能を大幅に拡充した。",
    prompt_description="テキストから組織名と製品名を抽出してください。",
    examples=examples,
    model_id="gemini-2.5-flash",
)

# 結果をJSONLファイルに保存
lx.io.save_annotated_documents(result, "output.jsonl")

# HTML形式で可視化
lx.visualize("output.jsonl", "result.html")
```

ここで肝になるのが`ExampleData`だ。LangExtractはFew-shotの仕組みで動く。「このテキストから、こういう情報を取り出してほしい」という手本を渡すと、LLMが未知のテキストにも同じ要領で抽出をかける。

## ExampleDataの構造を理解する

LangExtractの抽出精度は、例示の質で決まる。`ExampleData`の構造を押さえておこう。

```python
lx.data.ExampleData(
    text="入力テキストのサンプル",
    extractions=[
        lx.data.Extraction(
            extraction_class="抽出カテゴリ名",
            extraction_text="抽出対象の文字列",
            attributes={"属性名": "属性値"}
        )
    ]
)
```

各フィールドの役割はこうだ。

- `text` — 元テキスト。ここから何を取り出すかをLLMに示す
- `extraction_class` — 抽出カテゴリの名前。medication、person、contract_clauseなど
- `extraction_text` — 実際に抽出される文字列
- `attributes` — 付随する属性を辞書形式で書く

### 精度を上げる3つのコツ

まず、本番データに近いサンプルを使うこと。処理対象と文体や語彙が似た例示を用意すると精度が上がる。

次に、エッジケースを含めること。略称や表記揺れなど判断が難しいパターンを例示に入れておくと、LLMの対応力が広がる。

例示は2〜5個が目安だ。多すぎるとAPIコストが膨らみ、少なすぎると精度が落ちる。

## 実践 — 医療文書から薬剤情報を抽出する

LangExtractが特に活きるのが医療テキストの処理だ。臨床ノートや処方箋から薬剤情報を構造化する例を見てみよう。

```python
import langextract as lx

examples = [
    lx.data.ExampleData(
        text="患者にイブプロフェン400mgを1日3回経口投与した。",
        extractions=[
            lx.data.Extraction(
                extraction_class="medication",
                extraction_text="イブプロフェン",
                attributes={
                    "dosage": "400mg",
                    "route": "経口",
                    "frequency": "1日3回"
                }
            )
        ]
    )
]

result = lx.extract(
    text_or_documents="リシノプリル10mgを毎朝1回、高血圧の治療として処方。アスピリン100mgも併用。",
    prompt_description="テキストから薬剤名、用量、投与経路、頻度を抽出してください。",
    examples=examples,
    model_id="gemini-2.5-flash",
)

lx.io.save_annotated_documents(result, "medications.jsonl")
lx.visualize("medications.jsonl", "medications.html")
```

実行すると、リシノプリルとアスピリンがそれぞれ用量・頻度とともに構造化される。可視化HTMLを開けば、元テキストのどの部分から抽出されたかがハイライトで表示される。抽出結果を人間が検証するときに、このソース追跡機能が役に立つ。

## spaCy・LangChainと何が違うのか

テキストからの情報抽出にはLangExtract以外にも選択肢がある。代表的なツールとの違いを整理した。

| 特徴 | LangExtract | spaCy | LangChain Extraction |
|------|-------------|-------|---------------------|
| アプローチ | LLM + Few-shot例示 | 機械学習 + ルール | LLMパイプライン |
| 新ドメインへの適応 | 例示を数個追加するだけ | 再学習が必要 | パイプライン構築が必要 |
| ソース位置の追跡 | 文字オフセットで正確 | トークン単位 | ネイティブ非対応 |
| 処理速度 | LLM依存（やや遅い） | 高速 | LLM依存 |
| コスト | API利用料が発生 | 無料 | API利用料が発生 |
| 可視化 | HTML自動生成 | displaCy | 別途構築が必要 |

使い分けの判断基準はシンプルだ。大量テキストを高速に処理したいならspaCy。ドメインが頻繁に変わる、または学習データを用意する余裕がないならLangExtract。抽出結果を別のLLM処理に流したいならLangChain。

## 大量データを処理するときのチューニング

本番環境では、パフォーマンスの調整が必要になることがある。

### extraction_passes

長文ドキュメントのパス回数を指定するパラメータだ。値を増やすとテキスト中の見落としが減る。ただし、API呼び出し回数も増える。

```python
result = lx.extract(
    text_or_documents=long_text,
    prompt_description="重要な条項を抽出",
    examples=examples,
    model_id="gemini-2.5-flash",
    extraction_passes=3,
)
```

### max_workers

並列処理のスレッド数を設定する。複数ドキュメントを同時に処理する場合に効く。

### モデル選択でコストを調整する

LangExtractは複数のLLMバックエンドに対応している。用途に応じて使い分ければ、コストと精度のバランスが取れる。

- **Gemini 2.5 Flash** — 高速・低コスト。大量処理向き
- **Gemini 2.5 Pro** — 高精度。複雑な抽出タスク向き
- **OpenAI GPT-4o** — Geminiと同等の精度。既存のOpenAI環境に統合しやすい
- **Ollama経由のローカルモデル** — API費用ゼロ。機密データの処理に向いている

## よくある質問（FAQ）

### Q1. 日本語テキストでも使える？

使える。LLMの多言語対応をそのまま活かせるため、ExampleDataを日本語で記述すれば日本語テキストからの抽出も問題ない。

### Q2. 無料で使える？

LangExtract自体はApache 2.0のオープンソースで無料だ。ただしバックエンドLLMのAPI利用料は別途かかる。Ollamaでローカルモデルを使えばAPI費用もゼロにできる。

### Q3. 既存のNLPパイプラインに組み込める？

組み込める。Pythonライブラリとして動くので、既存のデータ処理パイプラインにimportするだけだ。抽出結果はJSONL形式で出力されるため、後続処理との連携もしやすい。

### Q4. 精度はどの程度出る？

タスクの複雑さ、例示の質、使用モデルによって変わる。公式ブログでは医療テキストの薬剤抽出で高い精度を達成した事例が紹介されている。例示を3〜5個用意して適切なプロンプトを設定すれば、実用に耐える精度は出る。

## LangExtractが向いている場面

新しいドメインのテキストから、すぐに構造化データを取り出したい。そんな場面でLangExtractは力を発揮する。再学習不要のFew-shotアプローチ、文字オフセットによるソース追跡、ワンコマンドのHTML可視化。この3つが揃っているおかげで、情報抽出タスクの立ち上げが速い。

公式リポジトリ [google/langextract](https://github.com/google/langextract) でドキュメントを確認して、自分のプロジェクトに合った例示を作ってみてほしい。

## 参考リンク

- [GitHub - google/langextract](https://github.com/google/langextract)
- [Introducing LangExtract - Google Developers Blog](https://developers.googleblog.com/introducing-langextract-a-gemini-powered-information-extraction-library/)
- [langextract - PyPI](https://pypi.org/project/langextract/)
