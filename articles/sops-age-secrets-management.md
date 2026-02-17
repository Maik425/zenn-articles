---
title: "個人開発のシークレット管理、SOPS + age にしたら全部解決した"
emoji: "🔐"
type: "tech"
topics: ["SOPS", "age", "シークレット管理", "GitHubActions", "セキュリティ"]
published: true
---

## APIキーの置き場所に困る

個人開発で自動化パイプラインを作っていると、APIキーがどんどん増える。

X API、Discord Bot Token、Anthropic APIキー、GitHub PAT、DeepL、Slack。1つのプロジェクトで6種類以上になった。ローカルなら`.env`に書いておけばいい。ではGitHub Actionsで定期実行するときはどうするか。

全部をGitHub Secretsに個別登録する手もある。ただ6つ、7つと増えてくると、ワークフローのenv定義が膨れ上がっていく。ローカルの`.env`との二重管理になって、片方だけ更新し忘れる。APIキー以外にもDiscordのチャンネルIDやリアクション絵文字の設定など、隠したい値はいくらでもあった。

暗号化した設定ファイルをgitにコミットして、必要なときだけ復号する。この方針でSOPS + ageを入れた。

## SOPSとageの組み合わせ

SOPSはMozillaが開発したシークレット管理ツールで、YAMLやJSONの値だけを暗号化する。キー名はそのまま残るから、diffが読めるし構造も把握できる。

暗号化のバックエンドにはAWS KMS、GCP KMS、Azure Key Vault、PGPなどがある。ただ個人開発でクラウドKMSは大げさだし、月額料金もかかる。

そこでageにした。PGPの代替として作られた軽量な暗号化ツールで、鍵の生成はコマンド1つ。外部サービスへの依存がない。SOPSがageをバックエンドとしてサポートしているので、この2つの組み合わせなら外部KMSなしでファイル暗号化が完結する。

## 仕組みの全体像

やっていることは単純で、1つのYAMLにすべてのシークレットを書き、SOPSでageの公開鍵を使って暗号化し、gitにコミットする。使うときは秘密鍵で復号して読み込む。

ローカルでは秘密鍵ファイルを環境変数で指定。GitHub Actionsでは秘密鍵をGitHub Secretsに1つだけ登録して、ワークフロー内で復号する。

GitHubに預けるシークレットは秘密鍵1つだけ。残りは全部暗号化ファイルの中にある。

## 鍵の生成とセットアップ

まずageの鍵ペアを作る。

```bash
age-keygen -o keys.txt
```

`keys.txt`に秘密鍵と公開鍵の両方が出力される。公開鍵は`age1...`で始まる文字列。

次にSOPSの設定ファイルを置く。

```yaml
# .sops.yaml
creation_rules:
  - path_regex: config/secrets\.yaml$
    age: >-
      age1m06m09n7szh...（公開鍵）
```

`.sops.yaml`はgitにコミットしていい。公開鍵は暗号化にしか使えないからリポジトリに入れても問題ない。

秘密鍵の`keys.txt`は`.gitignore`に入れる。ここだけは絶対に守る。

## シークレットファイルの構造

暗号化前のYAMLはこんな形になっている。

```yaml
discord:
  bot_token: "xxxx"
  guild_id: "xxxx"
  source_channels:
    - id: "xxxx"
      name: "tech-news"

llm:
  provider: "anthropic"
  api_key: "xxxx"
  model: "claude-3-haiku-20240307"

x_api:
  consumer_key: "xxxx"
  consumer_secret: "xxxx"
  access_token: "xxxx"
  access_token_secret: "xxxx"
```

APIキーだけでなく、チャンネルID、モデル名、リアクション絵文字の定義まで1ファイルに集約してある。環境ごとに変わる値は全部ここ。

SOPSで暗号化すると値だけが`ENC[AES256_GCM,...]`に置き換わる。キー名が残るので、暗号化したままでも何が入っているか把握できる。

## 暗号化と復号

```bash
# 暗号化
sops -e config/secrets.yaml > config/secrets.enc.yaml

# 復号
SOPS_AGE_KEY_FILE=keys.txt sops -d config/secrets.enc.yaml > config/secrets.yaml

# 直接編集（復号→エディタ→再暗号化を自動でやってくれる）
sops config/secrets.enc.yaml
```

地味に便利なのが`sops config/secrets.enc.yaml`の直接編集。復号してエディタが開き、保存すれば自動で再暗号化してくれる。APIキーの差し替えがワンコマンドで済む。

## Pythonからの読み込み

復号したあとは普通のYAMLとして読むだけ。

```python
def load_secrets():
    secrets_path = CONFIG_DIR / "secrets.yaml"
    if secrets_path.exists():
        with open(secrets_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return None
```

各クライアントにはファクトリ関数を持たせて、起動時に必要なキーが揃っているかチェックしている。

```python
def get_x_config():
    secrets = load_secrets()
    if not secrets or 'x_api' not in secrets:
        raise ValueError("X API設定が見つかりません。config/secrets.yamlを確認してください。")

    x_config = secrets['x_api']
    required_keys = ['consumer_key', 'consumer_secret', 'access_token', 'access_token_secret']
    missing = [k for k in required_keys if not x_config.get(k)]
    if missing:
        raise ValueError(f"必要なキーが不足しています: {', '.join(missing)}")
    ...
```

エラーメッセージにはファイルパスだけ出して、シークレットの値がログに漏れないようにしてある。

## GitHub Actionsとの統合

ここが一番効いた。

12本のワークフローが同じパターンでシークレットを扱っている。

```yaml
env:
  SOPS_VERSION: "3.8.1"

steps:
  - name: Install SOPS
    run: |
      curl -LO https://github.com/getsops/sops/releases/download/v${{ env.SOPS_VERSION }}/sops-v${{ env.SOPS_VERSION }}.linux.amd64
      chmod +x sops-v${{ env.SOPS_VERSION }}.linux.amd64
      sudo mv sops-v${{ env.SOPS_VERSION }}.linux.amd64 /usr/local/bin/sops

  - name: Decrypt secrets
    env:
      SOPS_AGE_KEY: ${{ secrets.AGE_SECRET_KEY }}
    run: |
      sops -d config/secrets.enc.yaml > config/secrets.yaml
```

GitHub Secretsに登録するのは`AGE_SECRET_KEY`の1つだけ。ワークフロー内でSOPSをインストールし、暗号化ファイルを復号する。復号されたファイルはコンテナ上にしか存在せず、ジョブが終われば消える。

以前は各APIキーを個別にGitHub Secretsへ登録していた。ワークフローのenvセクションが10行を超え、どのシークレットがどのジョブで必要なのか把握しきれなくなっていた。いまはSOPSの2ステップだけで済む。APIキーが増えてもワークフローを触る必要がない。

## 状態ファイルの永続化

パイプラインはJSONで状態を持っている。処理済みメッセージのID、保留中のドラフト、最終実行時刻の3つ。GitHub Actionsは毎回クリーンな環境で動くから、この状態をどこかに残さないといけない。

結局gitにコミットする方式にした。

```yaml
- name: Commit state changes
  if: always()
  run: |
    git add config/pipeline_state.json || true
    git diff --staged --quiet && echo "No changes" && exit 0
    git commit -m "chore: update pipeline state [skip ci]"
    for i in 1 2 3; do
      git push && exit 0
      git pull --rebase
      sleep 2
    done
```

`if: always()`をつけているから、パイプラインが途中で失敗しても状態は保存される。`[skip ci]`でコミットによるワークフローの再トリガーを防いでいる。3回リトライは、複数ワークフローが同時に走ったときのpush競合への対策。

完璧なやり方ではないが、個人開発ならこれで十分回る。

## ローカル実行との使い分け

ローカルではファイルベースで秘密鍵を渡す。

```bash
export SOPS_AGE_KEY_FILE="keys.txt"
sops -d config/secrets.enc.yaml > config/secrets.yaml
python daily/x_post_pipeline.py --process
```

GitHub Actionsでは環境変数に秘密鍵の中身を直接入れる。

```yaml
env:
  SOPS_AGE_KEY: ${{ secrets.AGE_SECRET_KEY }}
```

SOPSは`SOPS_AGE_KEY_FILE`と`SOPS_AGE_KEY`の両方に対応していて、実行環境に応じて切り替わる。コード側を変える必要はない。

## やってみて良かったこと

一番大きいのはシークレットの一元管理。APIキーを変えたいときは`sops config/secrets.enc.yaml`で編集してコミットすれば終わる。ローカルもCIも同じファイルを見るので、片方だけ古いまま、という事故がなくなった。

ワークフローの追加も楽になった。新しいパイプラインを作るとき、SOPSの復号ステップをコピーすればシークレットの準備は完了する。GitHub Secretsに新しいキーを足す作業がいらない。

もう一つ、暗号化ファイルのdiffが読めること。`git log -p`でどのキーが変わったか確認できる。値そのものはわからないが、いつ何が変更されたかの履歴は残る。

## 注意点

ageの鍵には有効期限がない。定期的に鍵を回す仕組みは自分で作るしかない。個人開発では気にしていないが、チームで使うなら鍵のローテーション方針を先に決めておいたほうがいい。

GitHub Secretsの`AGE_SECRET_KEY`が漏れると、暗号化ファイルを全部復号できてしまう点にも注意がいる。シークレットが1つに集約されている分、その1つの扱いは厳重にしないといけない。

あとはSOPSのインストールがワークフローのたびに走ること。1秒程度だから実害はないが、気になるならキャッシュもできる。

## 技術スタック

- **暗号化** SOPS 3.8.1 + age
- **設定形式** YAML
- **CI/CD** GitHub Actions（12ワークフロー）
- **言語** Python（yaml.safe_load で読み込み）
- **鍵管理** ローカル: keys.txt / CI: GitHub Secrets

## この構成が向いている人

外部KMSに依存したくない。AWSもGCPも使っていない。でもAPIキーを平文でリポジトリに置きたくはない。そういう個人開発者やスモールチームには、SOPS + ageはちょうどいい選択肢だと思う。

セットアップは30分もかからない。`age-keygen`で鍵を作り、`.sops.yaml`を書き、暗号化する。GitHub Secretsに秘密鍵を登録すれば、あとは回る。
