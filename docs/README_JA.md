<h1 align="center">● オープン インタープリタ</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
      <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
    <a href="../README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"></a>
    <a href="README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
    <br>
    <br>
    <b>自然言語で指示するだけでコードを書いて実行までやってくれる。</b><br>
    ローカルに実装したOpenAI Code Interpreterのオープンソース版。<br>
    <br><a href="https://openinterpreter.com">デスクトップアプリケーションへの早期アクセス。</a>‎ ‎ |‎ ‎ <b><a href="https://docs.openinterpreter.com/">新しいドキュメントを読む</a></b><br>
</p>

<br>

![poster](https://github.com/KillianLucas/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br>

**Update:** ● 0.1.12 サポート `interpreter --vision` ([ドキュメント](https://docs.openinterpreter.com/usage/terminal/vision))

<br>

```shell
pip install open-interpreter
```

```shell
interpreter
```

<br>

**Open Interpreter**は、言語モデルに指示し、コード（Python、Javascript、Shell など）をローカル環境で実行するようにします。インストール後、`$ interpreter`を実行するとターミナル経由で ChatGPT のようなインターフェースを介し、Open Interpreter とチャットができます。

これにより、自然言語のインターフェースを通して、パソコンの一般的な機能が操作できます。

- 写真、動画、PDF などの作成や編集。
- Chrome ブラウザの制御とリサーチ作業。
- 大規模なデータセットのプロット、クリーニング、分析。
- 等々

**⚠️ 注意：実行する前にコードを承認するよう求められます。**

<br>

## デモ

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab でもインタラクティブなデモを利用できます：

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## クイックスタート

```shell
pip install open-interpreter
```

### ターミナル

インストール後、`interpreter`を実行するだけです：

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("AAPLとMETAの株価グラフを描いてください") # 一つのコマンドを実行
interpreter.chat() # インタラクティブなチャットを開始
```

## ChatGPT のコードインタープリタとの違い

GPT-4 で実装された OpenAI の[Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) は、実世界のタスクを ChatGPT で操作できる素晴らしい機会を提供しています。

しかし、OpenAI のサービスはホスティングされていて、クローズドソースで、かなり制限されています：

- インターネットに接続できない。
- [プリインストールされているパッケージが限られている](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 最大アップロードは 100MB で、120 秒という実行時間の制限も。
- 生成されたファイルやリンクとともに状態がリセットされる。

Open Interpreter は、ローカル環境で操作することで、これらの制限を克服しています。インターネットにフルアクセスでき、時間やファイルサイズの制限を受けず、どんなパッケージやライブラリも利用できます。

Open Interpter は、GPT-4 のコードインタープリタのパワーとローカル開発環境の柔軟性を組み合わせたものです。

## コマンド

**Update:** ジェネレーターアップデート(0.1.5) でストリーミングが導入されました:

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### インタラクティブチャット

ターミナルでインタラクティブなチャットを開始するには、コマンドラインから`interpreter`を実行します。

```shell
interpreter
```

または、.py ファイルから`interpreter.chat()`も利用できます。

```python
interpreter.chat()
```

**また、各チャンクをストリーミングすることもできます:**

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### プログラム的なチャット

より精確な制御のために、メッセージを直接`.chat(message)`に渡すことができます。

```python
interpreter.chat("/videosフォルダにあるすべての動画に字幕を追加する。")

# ... ターミナルに出力をストリームし、タスクを完了 ...

interpreter.chat("ついでに、字幕を大きくできますか？")

# ...
```

### 新しいチャットを開始

プログラム的チャットで Open Interpreter は、会話の履歴を記憶しています。新しくやり直したい場合は、リセットすることができます：

```python
interpreter.reset()
```

### チャットの保存と復元

'interpreter.chat()' は 'interpreter.messages = messages' で会話を再開するために使用できるメッセージのリストを返します:

```python
messages = interpreter.chat("私の名前は田中です。") # 'messages'にメッセージを保存
interpreter.reset() # インタープリタをリセット（"田中"は忘れられる）

interpreter.messages = messages # 'messages'からチャットを再開（"田中"は記憶される）
```

### システムメッセージのカスタマイズ

Open Interpreter のシステムメッセージを確認し、設定することで、機能を拡張したり、権限を変更したり、またはより多くのコンテキストを与えたりすることができます。

```python
interpreter.system_message += """
シェルコマンドを「-y」フラグ付きで実行し、ユーザーが確認する必要がないようにする。
"""
print(interpreter.system_message)
```

### モデルの変更

Open Interpreter は [LiteLLM](https://docs.litellm.ai/docs/providers/) を使用してホスト言語モデルに接続します。

モデルを変更するには、model パラメーターを設定します:

```python
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

プログラム的チャットでは、モデルを手動で設定する必要がある：

```python
interpreter.model = "gpt-3.5-turbo"
```

["model" の言語モデル文字列を見つける](https://docs.litellm.ai/docs/providers/)


### ローカルのモデルを実行する

Open Interpreter は[LM Studio](https://lmstudio.ai/) を使用してローカル言語モデルに接続します(実験的)。

コマンドラインからローカルモードで 'interpreter' を実行するだけです。

```shell
interpreter --local
```

**LMStudio をバックグラウンドで実行する必要があります。**

1. ダウンロード [https://lmstudio.ai/](https://lmstudio.ai/)
2. model を選択し **↓ Download** をクリック
3. 左の **↔️** ボタンをクリック (下に 💬).
4. 上部でモデルを選択し、**Start Server** をクリック

サーバーが起動したら、Open Interpreter との会話を開始できます。

(コマンド `interpreter --local` を実行すると、上記の手順が表示されます。)

> **Note:** ローカルモードの `context_window` は 3000 で設定されます, そして `max_tokens` は 1000 です。 
モデルの要件が異なる場合は、これらのパラメーターを手動で設定します (以下を参照)


#### Context Window, Max Tokens

ローカルで実行するモデルの max_tokens と context_window (トークン単位) を簡単に変更できます。

context_window を小さくすると RAM の使用量が減るので、GPU が失敗している場合はサイズを短くしてみることをお勧めします。

ローカルモードでは、 context_window が小さいほど RAM の使用量が少なくなります。失敗している場合、短いウィンドウ (~1000) を試すことをお勧めします。 / 遅い場合は `max_tokens` が `context_window` より小さいことを確認してください。

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### デバッグモード

コントリビューターが Open Interpreter を調査するのを助けるために、`--debug`モードは非常に便利です。

デバッグモードは、フラグ（`interpreter --debug`）を使用するか、またはチャットの中から有効にできます：

```shell
$ interpreter
...
> %debug true # <- デバッグモードを有効にする

> %debug false # <- デバッグモードを有効にする
```


### インタラクティブ モード コマンド

インタラクティブモードでは、以下のコマンドを使用してエクスペリエンスを向上させることができます。使用可能なコマンドの一覧を次に示します:

**使用可能なコマンド:**

- `%debug [true/false]`: Toggle debug mode. Without arguments or with `true` it
  enters debug mode. With `false` it exits debug mode.
^ `%debug [true/false]`: デバッグモードを切り替えます。引数なしまたは `true` の場合
  デバッグモードに入ります。 `false` の場合、デバッグモードを終了します。
- `%reset`: 現在のセッションの対話をリセットします。
- `%undo`: メッセージ履歴から前のユーザー メッセージと AI の応答を削除します。
- `%save_message [path]`: 指定した JSON パスにメッセージを保存します。パスが指定されていない場合、既定値は `messages.json` です。
- `%load_message [path]`: 指定した JSON パスからメッセージを読み込みます。パスが指定されていない場合、既定値は `messages.json` です。
- `%tokens [prompt]`: (_Experimental_) 次のプロンプトをコンテキストとして送信されるトークンを計算し、そのコストを見積もります。必要に応じて、トークンと 'プロンプト' の推定コストを計算します(指定されている場合)。[LiteLLMの`cost_per_token()`メソッド](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) を使用してコストを見積もります。
- `%help`: ヘルプメッセージを表示します。

### Configuration

Open Interpreter は `config.yaml` ファイルを使用してデフォルトの動作を設定できます。

これにより、コマンドライン引数を毎回変更することなく、インタープリターを柔軟に構成できます。

次のコマンドを実行して構成ファイルを開きます:

```
interpreter --config
```

#### Multiple Configuration Files

Open Interpreter は複数の `config.yaml` ファイルをサポートしているため、`--config_file` 引数を使用して構成を簡単に切り替えることができます。

**Note**: `--config_file` はファイル名またはファイル パスのいずれかを受け入れます。ファイル名にはデフォルトの構成ディレクトリが使用され、ファイル パスには指定されたパスが使用されます。

新しい構成を作成または編集するには、次を実行します:

```
interpreter --config --config_file $config_path
```

Open Interpreter に特定の構成ファイルをロードさせるには、次のコマンドを実行します:

```
interpreter --config_file $config_path
```

**Note**: `$config_path` を構成ファイルの名前または構成ファイルへのパスに置き換えます。

##### CLI Example

1. 新しい `config.turbo.yaml` ファイルを作成します
   ```
   interpreter --config --config_file config.turbo.yaml
   ```
2. `config.turbo.yaml` ファイルを編集して、`model` を `gpt-3.5-turbo` に設定します。
3. `config.turbo.yaml` 設定を使用して Open Interpreter を実行する
   ```
   interpreter --config_file config.turbo.yaml
   ```

##### Python Example


Python スクリプトから Open Interpreter を呼び出すときに構成ファイルをロードすることもできます:

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

## FastAPI サーバー サンプル

ジェネレーターの更新により、Open Interpreter を HTTP REST エンドポイント経由で制御できるようになります:

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

この確認を回避するには、`interpreter -y` を実行するか、`interpreter.auto_run = True` を設定します。その場合：

- ファイルやシステム設定を変更するコマンドを要求するときは注意してください。
- Open Interpreter を自動運転車のように監視し、ターミナルを閉じてプロセスを終了できるように準備しておいてください。
- Google Colab や Replit のような制限された環境で Open Interpreter を実行することを検討してください。これらの環境はより隔離されており、任意のコードの実行に関連するリスクを軽減します。

## Open Interpreter はどのように機能するのか？

Open Interpreter は、[関数が呼び出せる言語モデル](https://platform.openai.com/docs/guides/gpt/function-calling)に`exec()`関数を装備し、実行する言語（"python"や"javascript"など）とコードが渡せるようになっています。

そして、モデルからのメッセージ、コード、システムの出力を Markdown としてターミナルにストリーミングします。

# 貢献

貢献に興味を持っていただき、ありがとうございます！コミュニティからの参加を歓迎しています。

詳しくは、[貢献ガイドライン](CONTRIBUTING.md)を参照してください。

# Roadmap

Open Interpreter の将来をプレビューするには、[ロードマップ](https://github.com/KillianLucas/open-interpreter/blob/main/docs/ROADMAP.md) にアクセスしてください。


## ライセンス

Open Interpreter のライセンスは MIT ライセンスです。本ソフトウェアの使用、複製、変更、配布、サブライセンス、およびコピーの販売を許可します。

**注意**: このソフトウェアは OpenAI とは関係ありません。

> あなたの指先のスピードで作業するジュニアプログラマーにアクセスすることで、… 新しいワークフローを楽で効率的なものにし、プログラミングの利点を新しいオーディエンスに開放することができます。
>
> — _OpenAI のコードインタープリタリリースから_

<br>
<br>
<br>

**注意**: この翻訳は人工知能によって作成されました。誤りが含まれていることが確実です。
Open Interpreter が世界中を旅するのを助けるため、訂正を含むプルリクエストをしてください！
**注意**: 不足した部分を追記しましたが、誤りがあると思います。
