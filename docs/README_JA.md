<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="../README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/>
    <br>
    <br>
    <b>自然言語で指示するだけでコードを書いて実行までしてくれる。</b><br>
    ローカルに実装したOpenAI Code Interpreterのオープンソース版。<br>
    <br><a href="https://openinterpreter.com">デスクトップアプリへの早期アクセス</a>‎ ‎ |‎ ‎ <a href="https://docs.openinterpreter.com/">ドキュメント</a><br>
</p>

<br>

![poster](https://github.com/KillianLucas/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br>

**Update:** ● 0.1.12 アップデートで `interpreter --vision` 機能が導入されました。([ドキュメント](https://docs.openinterpreter.com/usage/terminal/vision))

<br>

```shell
pip install open-interpreter
```

```shell
interpreter
```

<br>

**Open Interpreter**は、言語モデルに指示し、コード（Python、Javascript、Shell など）をローカル環境で実行できるようにします。インストール後、`$ interpreter` を実行するとターミナル経由で ChatGPT のようなインターフェースを介し、Open Interpreter とチャットができます。

これにより、自然言語のインターフェースを通して、パソコンの一般的な機能が操作できます。

- 写真、動画、PDF などの作成や編集
- Chrome ブラウザの制御とリサーチ作業
- 大規模なデータセットのプロット、クリーニング、分析
- 等々

**⚠️ 注意: 実行する前にコードを承認するよう求められます。**

<br>

## デモ

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab でも対話形式のデモを利用できます:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### 音声インターフェースの実装例 (_Her_ からインスピレーションを得たもの):

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## クイックスタート

```shell
pip install open-interpreter
```

### ターミナル

インストール後、`interpreter` を実行するだけです:

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("AAPLとMETAの株価グラフを描いてください") # コマンドを実行
interpreter.chat() # 対話形式のチャットを開始
```

## ChatGPT の Code Interpreter との違い

GPT-4 で実装された OpenAI の [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) は、実世界のタスクを ChatGPT で操作できる素晴らしい機会を提供しています。

しかし、OpenAI のサービスはホスティングされていてるクローズドな環境で、かなり制限がされています:

- インターネットに接続できない。
- [プリインストールされているパッケージが限られている](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 最大アップロードは 100MB で、120 秒という実行時間の制限も。
- 生成されたファイルやリンクとともに状態がリセットされる。

---

Open Interpreter は、ローカル環境で操作することで、これらの制限を克服しています。インターネットにフルアクセスでき、時間やファイルサイズの制限を受けず、どんなパッケージやライブラリも利用できます。

Open Interpter は、GPT-4 Code Interpreter のパワーとローカル開発環境の柔軟性を組み合わせたものです。

## コマンド

**更新:** アップデート(0.1.5)でストリーミング機能が導入されました:

```python
message = "どのオペレーティングシステムを使用していますか？"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 対話型チャット

ターミナルで対話形式のチャットを開始するには、コマンドラインから `interpreter` を実行します。

```shell
interpreter
```

または、.py ファイルから `interpreter.chat()` も利用できます。

```python
interpreter.chat()
```

**ストリーミングすることでchunk毎に処理することも可能です:**

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### プログラム的なチャット

より精確な制御のために、メッセージを直接`.chat(message)`に渡すことができます。

```python
interpreter.chat("/videos フォルダにあるすべての動画に字幕を追加する。")

# ... ターミナルに出力をストリームし、タスクを完了 ...

interpreter.chat("ついでに、字幕を大きくできますか？")

# ...
```

### 新しいチャットを開始

プログラム的チャットで Open Interpreter は、会話の履歴を記憶しています。新しくやり直したい場合は、リセットすることができます:

```python
interpreter.reset()
```

### チャットの保存と復元

`interpreter.chat()` はメッセージのリストを返し, `interpreter.messages = messages` のように使用することで会話を再開することが可能です:

```python
messages = interpreter.chat("私の名前は田中です。") # 'messages'にメッセージを保存
interpreter.reset() # インタープリタをリセット（"田中"は忘れられる）

interpreter.messages = messages # 'messages'からチャットを再開（"田中"は記憶される）
```

### システムメッセージのカスタマイズ

Open Interpreter のシステムメッセージを確認し、設定することで、機能を拡張したり、権限を変更したり、またはより多くのコンテキストを与えたりすることができます。

```python
interpreter.system_message += """
シェルコマンドを '-y' フラグ付きで実行し、ユーザーが確認する必要がないようにする。
"""
print(interpreter.system_message)
```

### モデルの変更

Open Interpreter は、ホストされた言語モデルへの接続に [LiteLLM](https://docs.litellm.ai/docs/providers/) を使用しています。

model パラメータを設定することで、モデルを変更することが可能です:

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

Pythonでは、オブジェクト上でモデルを設定します:

```python
interpreter.model = "gpt-3.5-turbo"
```

[適切な "model" の値はこちらから検索してください。](https://docs.litellm.ai/docs/providers/)

### ローカルのモデルを実行する

Open Interpreter は、ローカルの言語モデルへの接続に [LM Studio](https://lmstudio.ai/) を実験的に使用しています。

コマンドラインから `interpreter` をローカルモードで実行するだけです:

```shell
interpreter --local
```

**バックグラウンドでLM Studioを実行する必要があります。**

1. [https://lmstudio.ai/](https://lmstudio.ai/)からダウンロードして起動します。
2. モデルを選択し、**↓ ダウンロード** をクリックします。
3. 左側の **↔️** ボタン（💬の下）をクリックします。
4. 上部でモデルを選択し、**サーバーを起動** をクリックします。

サーバーが稼働を開始したら、Open Interpreter との会話を開始できます。

（`interpreter --local` コマンドを実行した際にも、上記の手順が表示されます。）

> **注意:** ローカルモードでは、`context_window` を3000に、`max_tokens` を1000に設定します。モデルによって異なる要件がある場合、これらのパラメータを手動で設定してください（下記参照）。

#### コンテキストウィンドウ、最大トークン数

ローカルで実行しているモデルの `max_tokens` と `context_window`（トークン単位）を変更することができます。

ローカルモードでは、小さいコンテキストウィンドウはRAMを少なく使用するので、失敗する場合や遅い場合は、より短いウィンドウ（〜1000）を試すことをお勧めします。`max_tokens` が `context_window` より小さいことを確認してください。

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### デバッグモード

コントリビューターが Open Interpreter を調査するのを助けるために、`--debug` モードは非常に便利です。

デバッグモードは、フラグ（`interpreter --debug`）を使用するか、またはチャットの中から有効にできます:

```shell
$ interpreter
...
> %debug true # <- デバッグモードを有効にする

> %debug false # <- デバッグモードを無効にする
```

### 対話モードのコマンド

対話モードでは、以下のコマンドを使用して操作を便利にすることができます。利用可能なコマンドのリストは以下の通りです:

**利用可能なコマンド:**

- `%debug [true/false]`: デバッグモードを切り替えます。引数なしまたは `true` でデバッグモードに入ります。`false` でデバッグモードを終了します。
- `%reset`: 現在のセッションの会話をリセットします。
- `%undo`: メッセージ履歴から前のユーザーメッセージとAIの応答を削除します。
- `%save_message [path]`: メッセージを指定したJSONパスに保存します。パスが指定されていない場合、デフォルトは `messages.json` になります。
- `%load_message [path]`: 指定したJSONパスからメッセージを読み込みます。パスが指定されていない場合、デフォルトは `messages.json` になります。
- `%tokens [prompt]`: (_実験的_) 次のプロンプトのコンテキストとして送信されるトークンを計算し、そのコストを見積もります。オプションで、`prompt` が提供された場合のトークンと見積もりコストを計算します。見積もりコストは [LiteLLMの `cost_per_token()` メソッド](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token)に依存します。
- `%help`: ヘルプメッセージを表示します。

### 設定

Open Interpreterでは、`config.yaml` ファイルを使用してデフォルトの動作を設定することができます。

これにより、毎回コマンドライン引数を変更することなく柔軟に設定することができます。

以下のコマンドを実行して設定ファイルを開きます:

```
interpreter --config
```

#### 設定ファイルの複数利用

Open Interpreter は複数の `config.yaml` ファイルをサポートしており、`--config_file` 引数を通じて簡単に設定を切り替えることができます。

**注意**: `--config_file` はファイル名またはファイルパスを受け入れます。ファイル名はデフォルトの設定ディレクトリを使用し、ファイルパスは指定されたパスを使用します。

新しい設定を作成または編集するには、次のコマンドを実行します:

```
interpreter --config --config_file $config_path
```

特定の設定ファイルをロードして Open Interpreter を実行するには、次のコマンドを実行します:

```
interpreter --config_file $config_path
```

**注意**: `$config_path` をあなたの設定ファイルの名前またはパスに置き換えてください。

##### 対話モードでの使用例

1. 新しい `config.turbo.yaml` ファイルを作成します
   ```
   interpreter --config --config_file config.turbo.yaml
   ```
2. `config.turbo.yaml` ファイルを編集して、`model` を `gpt-3.5-turbo` に設定します
3. `config.turbo.yaml` 設定で、Open Interpreter を実行します
   ```
   interpreter --config_file config.turbo.yaml
   ```

##### Pythonでの使用例

Python のスクリプトから Open Interpreter を呼び出すときにも設定ファイルをロードできます:

```python
import os
import interpreter

currentPath = os.path.dirname(os.path.abspath(__file__))
config_path=os.path.join(currentPath, './config.test.yaml')

interpreter.extend_config(config_path=config_path)

message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

## FastAPIサーバーのサンプル

アップデートにより Open Interpreter は、HTTP RESTエンドポイントを介して制御できるようになりました:

```python
# server.py

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import interpreter

app = FastAPI()

@app.get("/chat")
def chat_endpoint(message: str):
    def event_stream():
        for result in interpreter.chat(message, stream=True):
            yield f"data: {result}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return interpreter.messages
```

```shell
pip install fastapi uvicorn
uvicorn server:app --reload
```

## 安全に関する注意

生成されたコードはローカル環境で実行されるため、ファイルやシステム設定と相互作用する可能性があり、データ損失やセキュリティリスクなど予期せぬ結果につながる可能性があります。

**⚠️ Open Interpreter はコードを実行する前にユーザーの確認を求めます。**

この確認を回避するには、`interpreter -y` を実行するか、`interpreter.auto_run = True` を設定します。その場合:

- ファイルやシステム設定を変更するコマンドを要求するときは注意してください。
- Open Interpreter を自動運転車のように監視し、ターミナルを閉じてプロセスを終了できるように準備しておいてください。
- Google Colab や Replit のような制限された環境で Open Interpreter を実行することを検討してください。これらの環境はより隔離されており、任意のコードの実行に関連するリスクを軽減します。

一部のリスクを軽減するための[セーフモード](docs/SAFE_MODE.md)と呼ばれる **実験的な** サポートがあります。

## Open Interpreter はどのように機能するのか？

Open Interpreter は、[関数が呼び出せる言語モデル](https://platform.openai.com/docs/guides/gpt/function-calling)に `exec()` 関数を装備し、実行する言語（"python"や"javascript"など）とコードが渡せるようになっています。

そして、モデルからのメッセージ、コード、システムの出力を Markdown としてターミナルにストリーミングします。

# 貢献

貢献に興味を持っていただき、ありがとうございます！コミュニティからの参加を歓迎しています。

詳しくは、[貢献ガイドライン](CONTRIBUTING.md)を参照してください。

# ロードマップ

Open Interpreter の未来を一足先に見るために、[私たちのロードマップ](https://github.com/KillianLucas/open-interpreter/blob/main/docs/ROADMAP.md)をご覧ください。

**注意**: このソフトウェアは OpenAI とは関連していません。

> あなたの指先のスピードで作業するジュニアプログラマーにアクセスすることで、… 新しいワークフローを楽で効率的なものにし、プログラミングの利点を新しいオーディエンスに開放することができます。
>
> — _OpenAI Code Interpreter リリース_

<br>
