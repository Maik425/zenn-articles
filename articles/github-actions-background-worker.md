---
title: "GitHub Actionsを個人開発のバックグラウンドワーカーにしたら、月900回タダで動いてくれている"
emoji: "⚙️"
type: "tech"
topics: ["GitHubActions", "自動化", "CICD", "個人開発", "Python"]
published: true
---

## サーバーを持たずに自動化したかった

個人開発で自動化パイプラインを作っていると、定期実行の置き場に困る。

VPSを借りてcronを回す手もある。ただ月1,000円前後かかるし、OSのアップデートやディスク容量の管理もついてくる。やりたいのは「毎朝7時にスクリプトを動かす」それだけなのに、インフラのお守りまでセットになる。

GitHub Actionsのscheduleトリガーなら、cron式で定期実行ができる。リポジトリにワークフローファイルを置くだけでいい。Freeプランで月2,000分まで。サーバー管理は不要。

いま12本のワークフローが走っていて、月900回以上の実行がこの無料枠に収まっている。

## 何を動かしているか

パイプラインは4系統ある。

SNS投稿。Discordに貼ったURLを拾い、LLMでドラフトを作り、承認されたらXに投稿する。

ニュース配信。RSSフィードとGitHub Trendingから記事を集めてLLMで厳選し、DiscordとSlackに流す。

記事生成。Daily Newsの中からトピックを選んでアウトラインを作り、承認後に本文を自動生成する。

タスク通知。GitHub Issuesからオープンタスクを集計して、毎朝Discordに投げる。

全部「定期的にスクリプトを実行して外部APIを叩く」というパターン。GitHub Actionsの得意分野そのものだった。

## スケジュール設計

12本のワークフローをどの時間帯に走らせるか。ここは少し考えた。

```
06:00 JST  ニュース収集（RSS + GitHub Trending）
07:00 JST  朝のバッチ（タスク通知 + SNS投稿）
09:00 JST  週次バッチ（記事生成、月水金のみ）
毎時       承認チェック + ドラフト生成
3時間ごと  記事本文の生成
```

朝6時にニュースを集めて、7時に通知と投稿を回す。毎時の承認チェックは、Discordで絵文字を押したらなるべく早く反映したいから。記事生成は重いので3時間おきにしている。

cron式はUTC指定。JSTとのズレには気をつける必要がある。朝7時なら前日のUTC 22:00。

```yaml
on:
  schedule:
    - cron: '0 22 * * *'   # JST 07:00
```

## 3フェーズに分ける

SNS投稿パイプラインは、1つのスクリプトを3段階に分けている。

**Collect**で新しいメッセージを拾い、**Process**でLLMにドラフトを作らせ、**Post**で承認済みのものだけ投稿。

```bash
# 個別実行
python daily/x_post_pipeline.py --collect
python daily/x_post_pipeline.py --process
python daily/x_post_pipeline.py --post

# まとめて実行（朝のバッチ）
python daily/x_post_pipeline.py --all
```

なぜ分けるか。毎時の定期実行ではCollect + Processだけ走らせて、投稿は朝のバッチでまとめる、という使い分けができるから。ワークフローのcron式を変えるだけで組み替えが効く。

```yaml
# periodic-checker.yml（毎時）
- run: python daily/x_post_pipeline.py --collect --process

# daily-morning.yml（毎朝7時）
- run: python daily/x_post_pipeline.py --all
```

## 状態ファイルの永続化

GitHub Actionsは毎回クリーンな環境で動くから、前の実行結果を覚えていない。

処理済みメッセージや投稿済みドラフトの情報をどこかに残さないと、同じ投稿が繰り返し出てしまう。外部DBを使えば解決するが、個人開発でDBサーバーを維持するのは本末転倒。

そこでJSONファイルをgitにコミットする方式にした。

```json
{
  "pending_drafts": [...],
  "posted_drafts": ["3e4a11c6-...", "e5999479-..."],
  "processed_message_ids": ["1470711089...", "1470630739..."]
}
```

ワークフローの最後にこのファイルをコミットし、次の実行時にpullで最新を取得する。

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

`if: always()`がポイントで、スクリプトが途中でコケても状態だけは保存される。これがないと、失敗した処理が次の実行でまた走って二重投稿になりかねない。

## push競合との戦い

毎時のチェッカーと朝のバッチが同時に走ると、両方が状態ファイルを更新してpushしようとする。先にpushした方は通るが、後発はreject。

3回リトライで`git pull --rebase`を挟んでいるのはこの対策。1回目のpushが失敗しても、rebaseで先行分を取り込んで再pushできる。

さらにワークフローレベルでも排他制御をかけている。

```yaml
concurrency:
  group: state-commit
  cancel-in-progress: false
```

同じグループ内のジョブは同時に1つしか走らない。`cancel-in-progress: false`にしてあるから、後発は先行の完了を待ってから動く。キャンセルはしない。

## [skip ci]で無限ループを防ぐ

状態ファイルをgit commitすると、mainにpushされる。GitHub Actionsはmainへのpushでワークフローをトリガーするから、何も考えずにいると無限ループになる。

コミットメッセージに`[skip ci]`を入れて回避している。

```bash
git commit -m "chore: update pipeline state [skip ci]"
```

これを忘れると大変なことになる。テスト中にうっかり付け忘れて、ワークフローが延々と自分自身をトリガーし続けたことがある。

## 冪等性を確保する

同じ実行が2回走っても結果が変わらないようにしている。

投稿フェーズでは、投稿直前に状態ファイルを再読み込みして、他のプロセスが先に投稿していないか確認する。

```python
def _is_already_posted(self, draft_id: str) -> bool:
    """投稿済みかチェック（並行実行対策）"""
    try:
        with open(self.state_file, 'r') as f:
            latest = json.load(f)
        return draft_id in set(latest.get('posted_drafts', []))
    except (json.JSONDecodeError, OSError):
        pass
    return False
```

Collectフェーズでも`processed_message_ids`で処理済みメッセージをスキップする。`--all`を2回連続で叩いても二重投稿にはならない。

## 失敗に強くする

ワークフロー内のステップには優先度がある。タスク通知が失敗しても、SNS投稿まで巻き添えにしたくない。

```yaml
- name: Run Task Summary
  continue-on-error: true
  run: python daily/task_summary.py

- name: Run X Post Pipeline
  run: python daily/x_post_pipeline.py --all
```

`continue-on-error: true`を付けたステップは、失敗しても後続が走る。読み取り専用の処理や、落ちても影響の小さいステップ向け。

一方で状態を変更するステップには付けない。エラーを見逃すと状態がおかしくなる。

ログは毎回アーティファクトとして残している。

```yaml
- name: Upload logs
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: pipeline-logs-${{ github.run_number }}
    path: logs/
    retention-days: 7
```

問題が起きたらGitHub上でログを直接確認できる。7日で自動削除されるからストレージも圧迫しない。

## 各パイプラインの状態を分離する

SNS投稿、記事生成、ニュース収集。それぞれが独立した状態ファイルを持っている。

```
config/
  pipeline_state.json          # SNS投稿（16KB）
  article_pipeline_state.json  # 記事生成（26KB）
  news_history.json            # ニュース重複排除
```

1つのファイルに全部入れると、どのパイプラインの変更か区別がつかない。分けておけば、片方が壊れてももう片方には影響しない。

ニュース履歴は7日で古いエントリを自動削除する。放っておいても膨らまない。

## Freeプランの上限と課金ライン

GitHub ActionsのFreeプランは、プライベートリポジトリで月2,000分まで。パブリックリポジトリなら無制限で使える。ストレージは500MB、同時実行ジョブは20本が上限。

超えるとどうなるか。Linux 2コアランナーで1分あたり$0.006、Windowsなら$0.010、macOSだと$0.062。Linuxしか使わない個人開発なら、仮に500分超過しても$3程度。課金が始まる前にGitHubから警告が来るので、気づかず請求されるリスクは低い。

注意したいのが分の丸め方。ジョブごとに端数を切り上げるルールになっている。30秒で終わるジョブでも1分としてカウントされる。毎時走る軽いチェッカーが実質30秒でも、課金上は月730分。ここは意外と見落としやすい。

## 月900回の実行コスト

ワークフローの実行頻度と、ジョブあたりの所要時間を整理するとこうなる。

```
daily-morning:       30回/月 × 約3.5分 =  105分
daily-news:          30回/月 × 約2.5分 =   75分
weekly-pipeline:     12回/月 × 約15分  =  180分
periodic-checker:   730回/月 × 約1.5分 = 1,095分
──────────────────────────────────────────
合計:               約800回/月           約1,460分
```

全体の75%を毎時のperiodic-checkerが食っている。スクリプト自体は数十秒で終わるが、checkout・pipインストール・SOPS復号・git操作のオーバーヘッドで毎回1分ほどかかる。

Freeプランの2,000分に対して約1,460分。残り540分、27%の余裕。ワークフローを1〜2本足してもまだ収まる。

ただ、毎時走らせなくていいチェッカーもある。承認チェックは2〜3時間おきでも運用上は困らないし、記事生成のチェックも同様。近いうちにperiodic-checkerの間隔を広げる予定で、そうすれば月の使用量は1,000分を切る。無料枠の半分以下になる計算。

## ワークフロー追加が楽

新しいパイプラインを作るときは、既存のワークフローからコピーすれば大枠ができる。SOPSの復号、Python環境のセットアップ、状態ファイルのコミット。この3つはどのワークフローにも入っていて、テンプレのようになっている。

```yaml
env:
  PYTHON_VERSION: '3.11'
  WORKING_DIR: '_automation'
  TZ: 'Asia/Tokyo'
  SOPS_VERSION: '3.8.1'
```

環境変数も統一してあるから、コピー時に書き換える箇所が少ない。シークレットの追加もいらない。SOPSで復号すれば全部の設定が手に入る。

12本に増えても管理できているのは、このパターン化のおかげだと思う。

## 向いていないこと

リアルタイム性が求められる処理には向かない。scheduleは数分ズレることがある。毎時0分に設定しても、実際には0〜5分くらいの幅が出る。

長時間走る処理も要注意。Freeプランのジョブタイムアウトは6時間。LLMのAPI呼び出しが多い処理だと1回数分かかるが、10分を超えるものは今のところない。

秘密の扱いにも気をつけている。GitHub Actionsの環境変数やSecretsに入れた値はログにマスクされるが、不用意にechoすると漏れる可能性がある。状態ファイルにシークレットを書き込まないこと。これは守っている。

## 設計で意識したこと

うまく回っている理由を振り返ると、3つに集約される。

まずフェーズを分けたこと。Collect、Process、Postを独立させたおかげで、実行タイミングの組み替えが効く。朝に全部回すか、毎時少しずつ回すか。cron式を書き換えるだけ。

次に状態を外部に逃がさなかったこと。JSONファイルをgitにコミットするのは素朴だが、DB管理が不要で、git logで変更履歴も追える。個人開発ならこれで十分回る。

最後にパターンの統一。12本のワークフローが同じ構成要素を使い回している。新規追加はコピーで済むし、問題の切り分けもしやすい。

## 技術スタック

- **定期実行** GitHub Actions（scheduleトリガー）
- **言語** Python 3.11
- **状態管理** JSONファイル + git commit
- **シークレット** SOPS + age
- **外部API** Discord Bot, X API, Anthropic Claude, DeepL, Slack
- **排他制御** concurrency group + git pull --rebase リトライ

## この構成が向いている人

VPSやDBサーバーを持ちたくないけど、定期実行はしたい。外部APIを叩くスクリプトを毎時や毎日回したい。そんな個人開発者には、GitHub Actionsをバックグラウンドワーカーにする設計は合うと思う。

サーバーレスのFunction（Lambda、Cloud Functions）でも同じことはできる。でもGitHub Actionsならリポジトリの中で完結する。コードと実行環境とログが同じ場所にある。その手軽さが、個人開発には一番効く。
