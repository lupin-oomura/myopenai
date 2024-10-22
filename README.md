
# MyOpenAI

## 概要

`myopenai`は、OpenAIのAPIを簡単に利用するためのPythonパッケージです。チャット補完、ストリーミング応答、音声認識、音声合成、画像生成など、OpenAIのさまざまな機能をシンプルなインターフェースで活用できます。

## インストール

```bash
pip install myopenai
```

## 機能

- **チャット補完**：テキストベースのチャット応答を取得。
- **ストリーミング応答**：リアルタイムでの応答をストリーミング取得。
- **音声認識**：音声データからテキストへの変換。
- **音声合成**：テキストから音声ファイルの生成。
- **画像生成**：テキストプロンプトから画像を生成。

## 使い方

### 初期化

```python
from myopenai import myopenai

# モデルを指定して初期化（例：gpt-4o）
mo = myopenai("gpt-4o")
```

### メッセージの追加と応答の取得

```python
# システムプロンプトの設定
mo.add_message("あなたはアメリカメジャーリーグのスペシャリストです。", role="system")

# ユーザーメッセージの追加
mo.add_message("大谷翔平の誕生日は？")

# 応答の取得
response = mo.run()
print(response)
```

### ストリーミング応答

リアルタイムでの応答をストリーミング取得する場合：

```python
import threading
import time

run_thread = threading.Thread(target=mo.run_stream)
run_thread.start()

while mo.is_running_or_queue():
    print(mo.get_queue(), end="", flush=True)
    time.sleep(0.1)

run_thread.join()
```

### 音声認識と音声合成

```python
# テキストを音声に変換
mo.text_to_speech("出身地について教えて", "speech_sample.mp3")

# 音声ファイルをメッセージに追加
mo.add_audio_fromfile("speech_sample.mp3")

# 音声で応答を取得
wav = mo.run_to_audio(model="gpt-4o-audio-preview")
with open("回答.wav", "wb") as f:
    f.write(wav)
```

### 画像生成

```python
mo.image_generate("もふもふのわんこ", "もふもふわんこ.png")
```

### 音声からテキストに変換

```python
text = mo.speech_to_text_from_file("speech_sample.mp3")
print(text)
```

## メソッド詳細

- **add_message(msg: str, role: str = "user")**  
  メッセージを追加します。

- **run(model: str = None) -> str**  
  チャット応答を取得します。

- **run_stream(model: str = None) -> str**  
  ストリーミングでチャット応答を取得します。

- **run_to_audio(model: str = None)**  
  音声応答を取得します。

- **text_to_speech(text: str, file_path: str, voice: str = "alloy")**  
  テキストを音声に変換し、ファイルに保存します。

- **image_generate(pmt: str, file_path: str)**  
  テキストから画像を生成し、ファイルに保存します。

## ボイスオプション

`text_to_speech`メソッドで使用できるボイスの例：
- **alloy**：男性アナウンサー風
- **nova**：女性アナウンサー風

## ライセンス

このプロジェクトのライセンスについては、`LICENSE`ファイルを参照してください。

## 作者

- **あなたの名前**
- **連絡先情報（メールやSNSなど）**

## 貢献

バグ報告や機能提案は、IssueやPull Requestを通じて受け付けています。
"# myopenai" 
