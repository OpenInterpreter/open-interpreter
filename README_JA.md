<h1 align="center">● オープン インタープリタ</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm"><img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
    <br>
    <br>
    <b>自然言語で指示するだけでコードを書いて実行までやってくれる。</b><br>
    ローカルに実装したOpenAI Code Interpreterのオープンソース版。<br>
    <br><a href="https://openinterpreter.com">デスクトップアプリケーションへの早期アクセス。</a><br>
</p>

<br>

![poster](https://github.com/KillianLucas/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br>

```shell
pip install open-interpreter
```

```shell
interpreter
```

<br>

**Open Interpreter**は、言語モデルに指示し、コード（Python、Javascript、Shellなど）をローカル環境で実行するようにします。インストール後、`$ interpreter`を実行するとターミナル経由でChatGPTのようなインターフェースを介し、Open Interpreterとチャットができます。

これにより、自然言語のインターフェースを通して、パソコンの一般的な機能が操作できます。

- 写真、動画、PDFなどの作成や編集。
- Chromeブラウザの制御とリサーチ作業。
- 大規模なデータセットのプロット、クリーニング、分析。
- 等々

**⚠️ 注意：実行する前にコードを承認するよう求められます。**

<br>

## デモ

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colabでもインタラクティブなデモを利用できます：

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

## ChatGPTのコードインタープリタとの違い

GPT-4で実装されたOpenAIの[Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) は、実世界のタスクをChatGPTで操作できる素晴らしい機会を提供しています。

しかし、OpenAIのサービスはホスティングされていて、クローズドソースで、かなり制限されています：
- インターネットに接続できない。
- [プリインストールされているパッケージが限られている](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 最大アップロードは100MBで、120秒という実行時間の制限も。
- 生成されたファイルやリンクとともに状態がリセットされる。

Open Interpreterは、ローカル環境で操作することで、これらの制限を克服しています。インターネットにフルアクセスでき、時間やファイルサイズの制限を受けず、どんなパッケージやライブラリも利用できます。

Open Interpterは、GPT-4のコードインタープリタのパワーとローカル開発環境の柔軟性を組み合わせたものです。

## コマンド

### インタラクティブチャット

ターミナルでインタラクティブなチャットを開始するには、コマンドラインから`interpreter`を実行します。

```shell
interpreter
```

または、.pyファイルから`interpreter.chat()`も利用できます。

```python
interpreter.chat()
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

プログラム的チャットでOpen Interpreterは、会話の履歴を記憶しています。新しくやり直したい場合は、リセットすることができます：

```python
interpreter.reset()
```

### チャットの保存と復元

`interpreter.chat()` は、return_messages=True のときにメッセージのリストを返し、`interpreter.load(messages)` で会話を再開することができます。

```python
messages = interpreter.chat("私の名前は田中です。", return_messages=True) # 'messages'にメッセージを保存
interpreter.reset() # インタープリタをリセット（"田中"は忘れられる）

interpreter.load(messages) # 'messages'からチャットを再開（"田中"は記憶される）
```

### システムメッセージのカスタマイズ

Open Interpreterのシステムメッセージを確認し、設定することで、機能を拡張したり、権限を変更したり、またはより多くのコンテキストを与えたりすることができます。

```python
interpreter.system_message += """
シェルコマンドを「-y」フラグ付きで実行し、ユーザーが確認する必要がないようにする。
"""
print(interpreter.system_message)
```

### モデルの変更

gpt-3.5-turboの場合は、fastモードを使用する：

```python
interpreter --fast
```

プログラム的チャットでは、モデルを手動で設定する必要がある：

```python
interpreter.model = "gpt-3.5-turbo"
```

### ローカルのモデルを実行する

ⓘ **ローカルでの実行に問題ですか？** 新しい[GPUセットアップガイド](/docs/GPU.md)と[Windowsセットアップガイド](/docs/WINDOWS.md)を参考にしてください。

`Code Llama` を使用するには、コマンドラインからローカルモードで `interpreter` を実行します。

```shell
interpreter --local
```

または、Hugging FaceモデルをそのレポID（例えば "tiiuae/falcon-180B"）を使ってローカルで実行することもできます：

```shell
interpreter --model tiiuae/falcon-180B
```

### ローカルモデルのパラメータ

ローカルで実行するモデルの max_tokens と context_window (トークン単位) を簡単に変更できます。

context_windowを小さくするとRAMの使用量が減るので、GPUが失敗している場合はサイズを短くしてみることをお勧めします。

```shell
interpreter --max_tokens 2000 --context_window 16000
```

### Azureのサポート

AzureのOpenAI Serviceに接続するには、`--use-azure`フラグを渡します。

```shell
interpreter --use-azure
```

Pythonでは、次の変数を設定します：

```
interpreter.use_azure = True
interpreter.api_key = "your_openai_api_key"
interpreter.azure_api_base = "your_azure_api_base"
interpreter.azure_api_version = "your_azure_api_version"
interpreter.azure_deployment_name = "your_azure_deployment_name"
interpreter.azure_api_type = "azure"
```

### デバッグモード

コントリビューターがOpen Interpreterを調査するのを助けるために、`--debug`モードは非常に便利です。

デバッグモードは、フラグ（`interpreter --debug`）を使用するか、またはチャットの中から有効にできます：

```shell
$ interpreter
...
> %debug # <- デバッグモードを有効にする
```

### .envによる設定
Open Interpreterでは、.envファイルを使ってデフォルトの動作を設定することができます。これにより、コマンドライン引数を毎回変更することなく、Open Interpreterを柔軟に設定できるようになります。

サンプルの.env設定は次のとおりです：

```shell
INTERPRETER_CLI_AUTO_RUN=False
INTERPRETER_CLI_FAST_MODE=False
INTERPRETER_CLI_LOCAL_RUN=False
INTERPRETER_CLI_DEBUG=False
INTERPRETER_CLI_USE_AZURE=False
```

これらの値を.envファイルで変更することで、Open Interpreterのデフォルトの動作を変更できます。

## 安全に関する注意

生成されたコードはローカル環境で実行されるため、ファイルやシステム設定と相互作用する可能性があり、データ損失やセキュリティリスクなど予期せぬ結果につながる可能性があります。

**⚠️ Open Interpreterはコードを実行する前にユーザーの確認を求めます。**

この確認を回避するには、`interpreter -y` を実行するか、`interpreter.auto_run = True` を設定します。その場合：

- ファイルやシステム設定を変更するコマンドを要求するときは注意してください。
- Open Interpreter を自動運転車のように監視し、ターミナルを閉じてプロセスを終了できるように準備しておいてください。
- Google ColabやReplitのような制限された環境でOpen Interpreterを実行することを検討してください。これらの環境はより隔離されており、任意のコードの実行に関連するリスクを軽減します。

## Open Interpreterはどのように機能するのか？

Open Interpreterは、[関数が呼び出せる言語モデル](https://platform.openai.com/docs/guides/gpt/function-calling)に`exec()`関数を装備し、実行する言語（"python"や"javascript"など）とコードが渡せるようになっています。

そして、モデルからのメッセージ、コード、システムの出力をMarkdownとしてターミナルにストリーミングします。

# 貢献

貢献に興味を持っていただき、ありがとうございます！コミュニティからの参加を歓迎しています。

詳しくは、[貢献ガイドライン](/docs/contributing.md)を参照してください。

## ライセンス

Open InterpreterのライセンスはMITライセンスです。本ソフトウェアの使用、複製、変更、配布、サブライセンス、およびコピーの販売を許可します。

**注意**: このソフトウェアはOpenAIとは関係ありません。
> あなたの指先のスピードで作業するジュニアプログラマーにアクセスすることで、… 新しいワークフローを楽で効率的なものにし、プログラミングの利点を新しいオーディエンスに開放することができます。
>
> — _OpenAIのコードインタープリタリリースから_

<br>
<br>
<br>

**注意**: この翻訳は人工知能によって作成されました。誤りが含まれていることが確実です。
Open Interpreterが世界中を旅するのを助けるため、訂正を含むプルリクエストをしてください！
