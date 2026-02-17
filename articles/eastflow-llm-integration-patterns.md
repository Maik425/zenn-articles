---
title: "業務システムにLLMを組み込む実践パターン — 社内業務管理システム EastFlowの事例"
emoji: "🧠"
type: "tech"
topics: ["go", "llm", "anthropic", "ollama", "architecture"]
published: true
---

## はじめに

自分はSI開発の担当をしている。会社にはSES事業の部署もあって、そっちがメールの処理で毎日かなりの時間を使っていた。何十通と届く案件情報メールや候補者のスキルシート。それを人が読んで、案件管理シートに転記して、候補者データベースに登録して、マッチングを考える。延々とこの繰り返しだ。

SI側もSI側で、プロジェクトの契約管理や予算管理をスプレッドシートで回していた。そろそろ限界だった。

両方まとめてシステムにすればいい。メールの構造化はLLMにやらせる。

そう考えて、社内の業務管理システム EastFlow を4日間で作った。Go + Next.js + PostgreSQL。メール受信からLLMによる自動分類・解析、案件や候補者の自動登録、マッチングまで一気通貫で動く。MCPサーバーも用意したので、Claude Codeなどからも EastFlow のデータを直接触れる。

この記事ではLLM統合の部分に絞って、実装パターンと設計判断を書いていく。

## 何をLLMにやらせるか

LLMに何を任せて何を任せないか。最初にやったのはこの線引きだった。万能に見えるが、安定性やコスト、レイテンシを考えると何でも投げるわけにはいかない。

### LLMに任せた3つの処理

**1. メール分類**

受信メールを3つに振り分ける。

- `project` — 案件情報。Javaエンジニア募集、単価60万〜、みたいなやつ
- `candidate` — 候補者のスキルシート。Python3年経験、フルリモート希望、など
- `other` — それ以外。営業メールや請求書

テキスト分類はLLMが得意な領域だ。ルールベースで件名や送信元をパターンマッチしてもカバーしきれないケースが多すぎた。

**2. メール解析**

分類後のメールから構造化データを抽出する。案件メールなら20以上のフィールド。タイトル、スキル、単価、勤務地、リモート可否、清算時間、面談回数。候補者メールなら13フィールド。名前、スキル、単価、最寄り駅、年齢、国籍。これを一発で抜く。

正規表現でやろうとすると地獄を見る。SES業界のメールはフォーマットがまったく統一されていない。同じ単価でも「50万〜」「500,000円/月」「50-60万」「～550K」。表記がバラバラだ。LLMならこの揺れを吸収できる。

**3. ドラフト生成**

案件への提案書、面談調整メール、フォローアップメールのドラフトを自動で作る。StructureText APIでフォーマットを指定して、ビジネスメールとして出力させている。

### あえてLLMを使わなかった処理

マッチングには重み付きアルゴリズムを採用した。

```
スコア = スキル一致率(0.4) + 単価適合度(0.3) + 勤務地(0.15) + 稼働可能時期(0.15)
```

マッチングには説明可能性がいる。なぜこの候補者を推薦したのか聞かれたとき、スキルが80%マッチ、希望単価レンジ内、勤務地が近い——と数値で答えられた方がいい。AIがそう判断しました、では通用しない。

曖昧な入力を構造化するのはLLMの仕事。構造化済みデータの定量比較はアルゴリズムの仕事。この切り分けが効いた。

## Provider抽象化 — interfaceひとつで3プロバイダー

LLMプロバイダーは移り変わりが速い。半年後にどのサービスがベストかわからない。だからプロバイダーへの依存を最小にした。

Go の interface で抽象化している。

```go
// Provider defines the LLM provider interface
type Provider interface {
    ParseEmail(ctx context.Context, input ParseEmailInput) (*ParseEmailOutput, error)
    ClassifyEmail(ctx context.Context, body string) (Classification, error)
    StructureText(ctx context.Context, text string, schema JSONSchema) (map[string]any, error)
    Name() string
}
```

これを実装するプロバイダーは3つ。

| プロバイダー | 用途 | 特徴 |
|-------------|------|------|
| Anthropic | クラウド（本番推奨） | 高精度、リトライ付き |
| OpenAI | クラウド or ローカル推論サーバー | vLLM等と互換 |
| Ollama | ローカル | APIキー不要、オフライン動作可 |

ここでのポイントは、interface のメソッドが `Generate(prompt)` みたいな汎用APIではないこと。`ParseEmail`、`ClassifyEmail`、`StructureText` と、業務で実際にやりたい操作だけを定義した。プロンプトの組み立てからJSONの解析まで各プロバイダーの実装が内包するので、呼び出し側はメールを渡すだけでいい。

### プロバイダー間の挙動差

抽象化しても、LLM APIの挙動はプロバイダーごとに違う。厄介なのがレスポンス形式の差だ。

Ollama は `format: "json"` を指定すればきれいなJSONが返る。ところが Anthropic や OpenAI はプロンプトでJSONだけ返せと指示しても、こういうレスポンスを返してくることがある。

```
Here is the extracted information:

```json
{"classification": "project", "confidence": 0.95}
```
```

マークダウンのコードフェンスで囲んでしまうパターンだ。これを剥がすのが `extractJSON` 関数。

```go
func extractJSON(raw string) string {
    raw = strings.TrimSpace(raw)
    if strings.HasPrefix(raw, "```") {
        lines := strings.Split(raw, "\n")
        var jsonLines []string
        inside := false
        for _, line := range lines {
            trimmed := strings.TrimSpace(line)
            if strings.HasPrefix(trimmed, "```") {
                inside = !inside
                continue
            }
            if inside {
                jsonLines = append(jsonLines, line)
            }
        }
        if len(jsonLines) > 0 {
            return strings.Join(jsonLines, "\n")
        }
    }
    return raw
}
```

地味な処理だが、これがないとクラウドLLMのレスポンスの半分近くでJSONパースが壊れる。LLMを業務システムに入れるとき、たぶん最初にぶつかる壁だと思う。

## Chain-of-Responsibility — 壊れても動くパイプライン

LLMは壊れる。APIが落ちる。レートリミットに引っかかる。意味不明なレスポンスが返ってくる。業務システムでLLMが不調だからメール処理できません、は許されない。

ではどうするか。EastFlow では Chain-of-Responsibility パターンで複数プロバイダーを順番に試す Manager を実装した。

```go
type Manager struct {
    providers []Provider
    logger    zerolog.Logger
}

func (m *Manager) tryChain(ctx context.Context, operation string, fn func(Provider) error) error {
    var errs []string
    for i, p := range m.providers {
        if err := fn(p); err == nil {
            return nil
        } else {
            errs = append(errs, fmt.Sprintf("%s: %v", p.Name(), err))
            if i < len(m.providers)-1 {
                m.logger.Warn().Err(err).Str("provider", p.Name()).
                    Msgf("%s failed, trying next provider", operation)
            }
        }
    }
    return fmt.Errorf("all providers failed for %s: %s",
        operation, strings.Join(errs, "; "))
}
```

Manager は `ParseEmail`、`ClassifyEmail`、`StructureText` の3メソッドを持つ。それぞれ `tryChain` を呼ぶ。最初のプロバイダーが失敗したら次に行き、全部失敗して初めてエラーを返す。

### BuildManager — チェーンの組み立て

プロバイダーをどの順番で並べるかは `BuildManager` が決める。

```go
func BuildManager(cfg ProviderConfig, logger zerolog.Logger) *Manager {
    var providers []Provider

    // --- Cloud providers (require API keys) ---
    if cfg.AnthropicAPIKey != "" {
        providers = append(providers, NewAnthropicProvider(cfg.AnthropicAPIKey, cfg.AnthropicModel))
    }
    if cfg.OpenAIAPIKey != "" {
        providers = append(providers, NewOpenAIProvider(cfg.OpenAIBaseURL, cfg.OpenAIModel, cfg.OpenAIAPIKey))
    }

    // --- Local providers (no API key required) ---
    if cfg.OpenAIBaseURL != "" && cfg.OpenAIAPIKey == "" {
        providers = append(providers, NewOpenAIProvider(cfg.OpenAIBaseURL, cfg.OpenAIModel, ""))
    }
    if cfg.OllamaURL != "" {
        providers = append(providers, NewOllamaProvider(cfg.OllamaURL, cfg.OllamaModel))
    }

    if len(providers) == 0 {
        logger.Warn().Msg("LLM: no providers configured — LLM features will be unavailable")
        return NewChainManager(logger) // 空のManagerを返す（呼び出しは全エラー）
    }

    return NewChainManager(logger, providers...)
}
```

設計判断が4つ入っている。

1. **クラウド優先** — APIキーがあれば Anthropic と OpenAI が先にチェーンに入る。精度が高い
2. **ローカルフォールバック** — Ollama は常に最後尾。クラウドAPIが全滅してもローカルモデルで最低限は動く
3. **ゼロ設定で起動できる** — APIキーが一つもなくても、OllamaのURLだけあればシステムは動く。開発環境で助かる
4. **プロバイダーゼロでも落ちない** — 何も設定しなくても空の Manager を返す。LLM呼び出しがエラーになるだけで、システム自体は起動する

### プロバイダー別の Confidence

同じメールをパースしても、プロバイダーによって返す信頼度を変えた。

| プロバイダー | Confidence（project/candidate） | Confidence（other） |
|-------------|-------------------------------|---------------------|
| Anthropic | 0.8 | 0.5 |
| OpenAI | 0.75 | 0.5 |
| Ollama | 0.7 | 0.5 |

クラウドLLMの方がモデルが大きく精度が高い傾向がある。フォールバックで Ollama が使われたときは Confidence が下がるので、後から人間が確認すべきレコードとして拾える。

## ドメイン特化プロンプト — SES業界の用語を教える

LLMは賢いが、ニッチな業界用語は知らない。SES業界には独特の用語がいくつもある。

- **清算時間** settlement_hours — 月の稼働時間の下限と上限。140-180hのように書かれ、超過や不足は精算対象
- **商流** business_flow — エンド企業から自社まで何社入るか。エンド→元請→当社なら2次請け
- **面談回数** — クライアントとの面談が何回か。1回なら即決型、3回なら大手
- **外国籍可否** — 外国籍エンジニアが参画できるか。ビザや日本語力の要件に直結する

これらを正しく拾えるよう、プロンプトに業界知識を埋め込んだ。

```
Notes for parsing:
- settlement_hours: Look for 清算時間/精算幅/稼働時間 (e.g. "140-180h" → min=140, max=180)
- interview_count: Look for 面談回数/面談N回 (e.g. "面談1回" → 1)
- foreign_nationality_ok: Look for 外国籍可/外国籍OK/外国籍不可
- contract_type: Look for SES/派遣/請負/業務委託/準委任
- business_flow: Look for 商流/エンド直/N次
- required_skills vs preferred_skills: Split skills into must-have and nice-to-have
  if the email distinguishes them. Otherwise put all in skills.
```

業界知識をコードではなくプロンプトに集約したのがポイントだ。SES業界のルールが変わったり新しいフィールドが要るとき、プロンプトを書き換えるだけで済む。コードは触らない。ドメイン知識はプロンプトに、インフラはコードに。この分離がうまく機能した。

### ClassificationHint — 分類をスキップする

メールの分類を毎回LLMに聞く必要がないケースもある。案件メール専用のメーリングリストから来たメールは、聞くまでもなく project だ。

```go
type ParseEmailInput struct {
    Subject            string `json:"subject"`
    Body               string `json:"body"`
    From               string `json:"from"`
    ClassificationHint string `json:"classification_hint,omitempty"`
}
```

`ClassificationHint` が入っていると、ClassifyEmail の LLM 呼び出しを飛ばして直接パースに入る。

```go
func (p *AnthropicProvider) ParseEmail(ctx context.Context, input ParseEmailInput) (*ParseEmailOutput, error) {
    var classification Classification

    if input.ClassificationHint != "" {
        classification = Classification(input.ClassificationHint)
    } else {
        var err error
        classification, err = p.ClassifyEmail(ctx, input.Body)
        if err != nil {
            return nil, fmt.Errorf("classify email: %w", err)
        }
    }

    prompt := BuildParseEmailPrompt(classification, input.Subject, input.From, input.Body)
    // ...
}
```

メールソースの設定で `default_classification` を指定しておけば、そのソースからのメールは分類ステップ丸ごと不要になる。LLM呼び出し1回分の時間とコストが消える。小さな最適化だが、毎日数十〜数百通を処理するなら積み重なる。

### なぜ2段階にしたか

分類と解析を分けたのは意図的だ。1段階目で project か candidate かを判定し、2段階目で専用プロンプトを使う。

1回のLLM呼び出しで両方やらせることもできた。ただ、案件メールと候補者メールでは抽出するフィールドがまるで違う。案件なら清算時間、面談回数、商流。候補者なら最寄り駅、国籍、ビザ。全フィールドをひとつのプロンプトに詰め込むと、LLMが混乱して案件メールに最寄り駅を無理やり埋めようとしたりする。

分類を先にやれば、後段のプロンプトをシンプルに保てる。プロンプトがシンプルなほどLLMの出力は安定する。

## 失敗に強くする設計

LLMを業務システムに入れるうえでいちばん大事だったのは、壊れる前提で作ること。同じ入力でも違う出力が返る。APIが突然エラーを吐く。それが日常だ。

EastFlowでは4つのレイヤーで耐障害性を確保した。

### Layer 1 — Anthropic APIのリトライ

Anthropic API は 429（レートリミット）や 529（過負荷）を返すことがある。指数バックオフでリトライする。

```go
const maxRetries = 3
backoff := 2 * time.Second

for attempt := 0; attempt <= maxRetries; attempt++ {
    // ... リクエスト送信 ...

    if resp.StatusCode == 429 || resp.StatusCode == 529 {
        if attempt < maxRetries {
            select {
            case <-ctx.Done():
                return "", ctx.Err()
            case <-time.After(backoff):
            }
            backoff *= 2 // 2s → 4s → 8s
            continue
        }
        return "", fmt.Errorf("status %d after %d retries", resp.StatusCode, maxRetries)
    }
    // ...
}
```

2秒、4秒、8秒と間隔を広げる。`ctx.Done()` を見ているので、context がキャンセルされたら即座に中断する。

### Layer 2 — パイプラインのリトライ

プロバイダーレベルとは別に、メールパイプライン側でもリトライを入れた。

```go
func (s *Service) parseEmailWithRetry(ctx context.Context, input llm.ParseEmailInput) (*llm.ParseEmailOutput, error) {
    const maxRetries = 2
    var lastErr error
    for attempt := 0; attempt <= maxRetries; attempt++ {
        if attempt > 0 {
            s.logger.Warn().Int("attempt", attempt+1).Msg("retrying LLM parse")
            time.Sleep(1 * time.Second)
        }
        llmCtx, llmCancel := context.WithTimeout(ctx, 30*time.Second)
        output, err := s.llm.ParseEmail(llmCtx, input)
        llmCancel()
        if err == nil {
            return output, nil
        }
        lastErr = err
    }
    return nil, lastErr
}
```

ChainManager の全プロバイダーが失敗した後のリトライだ。1回の `parseEmailWithRetry` の中で、最大でプロバイダー数 × Anthropicリトライ3回 × パイプラインリトライ3回のLLM呼び出しが走りうる。冗長に見えるが、レイヤーが違う障害を拾うためにそれぞれ必要だ。

- **Anthropicリトライ** — 一時的なAPI過負荷に対処
- **ChainManagerフォールバック** — 特定プロバイダーの障害に対処
- **パイプラインリトライ** — ネットワーク断やタイムアウトなど全体に影響する障害に対処

1秒のsleepと30秒のタイムアウトは、障害中にリトライでAPIをさらに圧迫しないための安全弁だ。

### Layer 3 — Graceful Degradation

全リトライが尽きても、いきなりエラーで止めない。部分的でも結果を返す。

```go
var fields map[string]any
if err := json.Unmarshal([]byte(cleaned), &fields); err != nil {
    // JSONパース失敗 → 部分的な結果を返す
    return &ParseEmailOutput{
        Classification: classification,
        Confidence:     0.5,
        RawResponse:    raw,
    }, nil  // エラーではなく低Confidenceの結果を返す
}
```

LLMが不完全なJSONを返した場合の挙動だ。フィールドが途中で切れていたり、余計なテキストが混ざっていたりする。エラーにせず、3つのことをやる。

1. 分類結果だけは保持する。案件メールらしいという情報は使える
2. Confidence を 0.5 に落とす。人間が確認すべきフラグになる
3. `RawResponse` に生のレスポンスを残す。後からデバッグや手動パースができる

60点でもいいから何か返す。業務システムではゼロか100かより、そっちの方が実用的だ。

### Layer 4 — エラーの集約

`tryChain` は全プロバイダーのエラーメッセージをまとめて返す。

```go
return fmt.Errorf("all providers failed for %s: %s",
    operation, strings.Join(errs, "; "))
```

こんなエラーが出る。`all providers failed for ParseEmail: anthropic: status 529; openai: timeout; ollama: connection refused`

どのプロバイダーがどんな理由で落ちたか一目でわかる。障害時にログを追うとき、これがあるかないかで調査速度がまるで違う。

## テスト戦略

LLMの出力は非決定的だからテストできない、とよく言われる。実際にはかなりの範囲をテストできる。ただし工夫がいる。

EastFlowでは `httptest` でLLM APIのモックサーバーを立てて、プロバイダーの実装をテストしている。

```go
func TestAnthropicProvider_ClassifyEmail(t *testing.T) {
    // Anthropic APIのモックサーバー
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        json.NewEncoder(w).Encode(anthropicResponse{
            Content: []anthropicContentBlock{
                {Type: "text", Text: `{"classification": "project", "confidence": 0.95}`},
            },
        })
    }))
    defer srv.Close()

    provider := &AnthropicProvider{
        apiKey:  "test-key",
        model:   "test-model",
        baseURL: srv.URL,
        client:  srv.Client(),
    }

    classification, err := provider.ClassifyEmail(context.Background(), "Java developer needed...")
    require.NoError(t, err)
    assert.Equal(t, ClassificationProject, classification)
}
```

テストしているのはLLMの出力品質じゃない。

1. **正常系** — 正しいJSONが返ったとき構造体にパースできるか
2. **コードフェンス** — ` ```json ... ``` ` で囲まれたレスポンスを処理できるか
3. **壊れたJSON** — Graceful Degradation が動くか
4. **サーバーエラー** — 429や529でリトライが回るか
5. **フォールバック** — プロバイダーAが落ちたときBに遷移するか
6. **BuildManager** — APIキーの有無でチェーンが正しく組まれるか

案件メールからスキルを正しく抜けるかどうかはユニットテストの範囲外だ。それはプロンプトの品質の問題で、実メールサンプルを使ったE2Eテストやプロンプト評価で見る領域になる。

ユニットテストでは、どんなレスポンスが返ってきてもシステムが壊れないことだけを保証する。この割り切りが大事だった。

## Ollama の勘所

3つのプロバイダーを実装して見えてきたのは、ローカルLLMとクラウドLLMで同じ interface を実装するにしても注意点が違うということだ。

### タイムアウト

```go
// Ollama: 600秒（10分）
client: &http.Client{Timeout: 600 * time.Second}

// Anthropic: 60秒
client: &http.Client{Timeout: 60 * time.Second}
```

Ollama はローカルのGPUでモデルを動かす。小さいモデルなら数秒だが、大きいモデルだと数分かかることがある。GPUメモリが足りずスワップが走るとさらに遅い。600秒は過剰に見えるが、実運用で99%は30秒以内に返るのにたまに3分かかるケースがあった。余裕を持たせている。

### ストリーミング

Ollama は `stream: true` でレスポンスをストリーミングで返す。部分的なJSONチャンクが次々と来るので、streaming decoder で読む。

```go
var sb strings.Builder
decoder := json.NewDecoder(resp.Body)
for decoder.More() {
    var chunk ollamaResponse
    if err := decoder.Decode(&chunk); err != nil {
        return "", fmt.Errorf("decode streaming chunk: %w", err)
    }
    sb.WriteString(chunk.Response)
    if chunk.Done {
        break
    }
}
```

各チャンクの `Response` をつなぎ合わせて最終レスポンスを組み立てる。`Done: true` が来たら完了。

Anthropic と OpenAI はノンストリーミングにした。クラウドAPIはストリーミングの方がTTFBは短いが、業務システムではレスポンス全体が必要なのでシンプルさを取った。

### JSON出力の安定性

Ollama には `format: "json"` があるので、比較的安定したJSONが返る。Anthropic と OpenAI にはそれがなく、プロンプトで指示するしかない。Function Calling や Tool Use でJSON出力を強制するAPIもあるが、プロンプトレベルで統一したかったので `extractJSON` で後処理する方式にした。

## まとめ

4日間の開発で意識したことを5つ。

**1. 壊れる前提で作る** — リトライ、フォールバック、Graceful Degradation は最初から入れる。LLM APIは外部依存であり、止まらない保証はない

**2. プロバイダー依存を排除する** — Go の interface で抽象化しておけば、プロバイダー追加は interface を実装するだけ

**3. ドメイン知識はプロンプトに、インフラはコードに** — 業界用語はプロンプトに集約し、コードはJSON入出力のパイプラインに徹する

**4. LLMに向かない処理を見極める** — マッチングのような定量比較はアルゴリズムの仕事だ

**5. テストは耐障害性に絞る** — 出力品質はプロンプトエンジニアリングの領域。ユニットテストでは、あらゆるレスポンスに対してシステムが壊れないことを確認する

---

LLMは賢いが不安定だ。その不安定さを吸収してシステムとして安定させるのが、アプリケーション側の仕事だった。MCPサーバー経由でClaude Codeから直接データを引けるようにしたことで、開発中も運用中もフローが途切れない。

コードは Go バックエンド約26,700行、TypeScript フロントエンド約14,500行。LLMパッケージだけならプロバイダー実装、マネージャー、プロンプト、テスト合わせて約1,500行。システム全体の数%だが、業務インパクトはいちばん大きい部分だ。
