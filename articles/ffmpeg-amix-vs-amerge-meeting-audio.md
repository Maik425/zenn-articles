---
title: "会議録音の文字起こし精度が上がらない原因はffmpegのamixだった"
emoji: "🎙️"
type: "tech"
topics: ["ffmpeg", "AssemblyAI", "音声処理", "文字起こし", "自動化"]
published: true
---

## 会議録音の文字起こしが読めない

会議議事録の自動化パイプラインを運用していて、不思議な現象に遭遇した。

**文字起こし（AssemblyAI）は解読困難なのに、議事録（Claude生成）は正確**。

```
# 文字起こし結果（一部）
"あのーえーとですねーあのーそれでーえーとー..."
"トリゲーさんがですねーあのー..."（正しくは「鳥飼さん」）
```

LLMが文脈から復元してくれているおかげで議事録は使えていたが、文字起こし自体の品質が低いのは気持ち悪い。原因を調べたら、ffmpegの音声ミックス方法に問題があった。

## 問題の構成

パイプラインはこうなっている。

1. Cap.soで画面録画（マイク音声＋システム音声を別トラックで保存）
2. ffmpegで2つの音声を結合
3. AssemblyAIで文字起こし
4. Claude Haikuで議事録生成

問題は2番目のffmpegの処理だった。

## 元の実装：amix

```bash
ffmpeg -y -i "audio-input.ogg" -i "system_audio.ogg" \
  -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest[out]" \
  -map "[out]" -ac 1 -ar 16000 -f wav output.wav
```

この実装には3つの問題があった。

### 1. エコーの二重化

マイク入力には自分の声だけでなく、スピーカーから漏れる相手の声も入っている。そこにシステム音声（相手の声のクリーンな録音）をミックスすると、相手の声が二重になる。

これが文字起こしのノイズになっていた。

### 2. amixの音量正規化

amixはデフォルトで各入力を `1/入力数` に下げる。2入力なら各0.5倍。全体の音量が下がり、小声の発言が潰れていた。

### 3. 不要なダウンサンプリング

`-ac 1 -ar 16000` でモノラル16kHzに変換していた。AssemblyAIは高品質な音声をそのまま受け付けるので、わざわざ劣化させる意味がなかった。

## 改善後：amerge

```bash
ffmpeg -y -i "audio-input.ogg" -i "system_audio.ogg" \
  -filter_complex "[0:a][1:a]amerge=inputs=2[out]" \
  -map "[out]" -ac 2 -f wav output.wav
```

amixからamergeに変えた。違いはこうなる。

| 項目 | amix | amerge |
|------|------|--------|
| 出力 | モノラル（混合） | ステレオ（左右分離） |
| 音量 | 自動正規化（下がる） | そのまま |
| 用途 | BGM合成など | マルチトラック録音 |

amergeは2つの音声を混ぜずに、左右のチャンネルに振り分ける。

- 左ch = マイク（自分の声）
- 右ch = システム音声（相手の声）

これでエコーの二重化が解消された。さらにAssemblyAIの話者分離がチャンネル情報を使えるようになり、精度が上がった。

## 追加の改善

amergeだけでは完全ではなかった。追加で4つの改善を入れた。

### 無音区間の除去

```bash
ffmpeg -y -i input.wav \
  -af "silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-40dB" \
  output_cleaned.wav
```

21分の音声が14分になった。7分の無音が除去された。

AssemblyAIは無音区間でハルシネーションを起こす傾向がある。存在しない発言を生成してしまう。事前に無音を除去することで、これが大幅に減った。

### 語彙ブースト

固有名詞や技術用語を登録しておくと認識精度が上がる。

```json
{
  "word_boost": ["高野", "永野", "鳥飼", "EastFlow", "JUnit"],
  "custom_spelling": {
    "鳥飼": ["トリゲー", "トリゲ"],
    "柴村": ["足場村", "しばむら"]
  }
}
```

`custom_spelling`で誤認識パターンを正しい表記に変換できる。「トリゲー」と認識されていたのが「鳥飼」になった。

### 話者数の事前指定

参加者数がわかっているなら指定した方がいい。

```python
config = aai.TranscriptionConfig(
    speaker_labels=True,
    speakers_expected=5  # 参加者数
)
```

未指定だと7人と誤認識していたのが、5人指定で正確になった。

### 繰り返しフレーズの後処理

AssemblyAIが無音やノイズ区間で同じフレーズを繰り返し生成する問題があった。

```python
# 単一utterance内の繰り返し圧縮
text = re.sub(r'(.{10,}?)\1{2,}', r'\1', text)

# 連続utterance間の完全一致除去
if current_text == previous_text:
    continue
```

137件のutteranceが90件に減った。

## 改善結果

| 指標 | 改善前 | 改善後 |
|------|--------|--------|
| 話者数 | 7（誤認識） | 5（正確） |
| utterance数 | 137 | 90 |
| 文字数 | 11,295 | 4,218 |
| 固有名詞 | トリゲー | 鳥飼 |

文字数が減ったのは繰り返しや無音ハルシネーションが除去されたため。情報量は維持されている。

## amix vs amerge の使い分け

- **amix**: 複数音源を1つの音として聞かせたい場合（BGM + ナレーションなど）
- **amerge**: 複数音源を分離したまま保持したい場合（マルチトラック録音など）

会議録音のように話者を分離したいケースではamergeが適している。

## 残る課題

- 会議後半で音声品質が下がると、ハルシネーションが完全には除去できない
- 話者が重なる場面では文の途中で話者が切り替わり、断片化する

これらはLLM側（議事録生成）で吸収されるので、実用上は問題ない。文字起こしの品質を上げれば、LLM側の負担も減るという話。

## 参考リンク

- [ffmpeg amix documentation](https://ffmpeg.org/ffmpeg-filters.html#amix)
- [ffmpeg amerge documentation](https://ffmpeg.org/ffmpeg-filters.html#amerge-1)
- [AssemblyAI Speaker Diarization](https://www.assemblyai.com/docs/speech-to-text/speaker-diarization)
- [AssemblyAI Custom Vocabulary](https://www.assemblyai.com/docs/speech-to-text/custom-vocabulary)
