<h1 align="center">● オープン インタープリタ</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm"><img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
<br>
    <b>コンピュータ上でコードを実行する言語モデル。</b><br>
    OpenAIのコードインタープリタのオープンソースで、ローカルに実行される実装。<br>
    <br><a href="https://openinterpreter.com">デスクトップアプリケーションの早期アクセスを取得する。</a><br>
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

**Open Interpreter**は、LLMを使用してコード（Python、Javascript、Shellなど）をローカルで実行できます。インストール後に`$ interpreter`を実行することで、ターミナルでChatGPTのようなインターフェースを介してOpen Interpreterとチャットできます。

これにより、コンピュータの一般的な目的の機能に自然言語のインターフェースを提供できます。

- 写真、動画、PDFなどの作成や編集。
- Chromeブラウザの制御とリサーチ実行。
- 大規模なデータセットのプロット、クリーニング、分析。
- ...等。

**⚠️ 注意：実行する前にコードを承認するように求められます。**

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

インストール後、`interpreter`を実行するだけ：

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("AAPLとMETAの正規化された株価をプロットする") # 一つのコマンドを実行
interpreter.chat() # インタラクティブなチャットを開始
```

## ChatGPTのコードインタープリタとの比較

OpenAIがGPT-4で[Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter)をリリースすることで、ChatGPTで実際のタスクを達成する素晴らしい機会が提供されました。

しかし、OpenAIのサービスはホスティングされ、クローズドソースで、かつ大きな制限があります：
- インターネットアクセス不可。
- [インストールされているパッケージのセットが限定されている](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 100 MBの最大アップロード、120.0秒のランタイム制限。
- 環境が終了すると状態がクリアされます。

Open Interpreterは、ローカル環境で実行することでこれらの制約を克服します。インターネットに完全にアクセスでき、時間やファイルサイズに制限されず、任意のパッケージやライブラリを使用することができます。

GPT-4のCode Interpreterの力と、ローカルの開発環境の柔軟性を組み合わせることができます。

## コマンド

### インタラクティブチャット

ターミナルでインタラクティブなチャットを開始するには、コマンドラインから`interpreter`を実行します。

```shell
interpreter
```

または、.pyファイルから`interpreter.chat()`を使用します。

```python
interpreter.chat()
```

### プログラムチャット

より精確な制御のために、メッセージを直接`.chat(message)`に渡すことができます。

```python
interpreter.chat("/videos内のすべての動画に字幕を追加する。")

# ... ターミナルに出力をストリームし、タスクを完了 ...

interpreter.chat("これは素晴らしいですが、字幕を大きくできますか？")

# ...
```

### 新しいチャットを開始

Pythonでは、Open Interpreterは会話の履歴を覚えています。新鮮な気持ちで始めたい場合は、リセットできます：

```python
interpreter.reset()
```

### チャットの保存と復元

`interpreter.chat()` は、return_messages=True のときにメッセージのリストを返します。これを使用して、`interpreter.load(messages)` で会話を再開することができます。

```python
messages = interpreter.chat("私の名前はKillianです。", return_messages=True) # 'messages'にメッセージを保存
interpreter.reset() # インタープリタをリセット（"Killian"は忘れられる）

interpreter.load(messages) # 'messages'からチャットを再開（"Killian"は覚えられる）
```

### システムメッセージのカスタマイズ

Open Interpreterのシステムメッセージを調査し、機能を拡張、権限を変更、またはより多くのコンテキストを提供するために設定できます。

```python
interpreter.system_message += """
ユーザーがそれらを確認する必要がないように、-yでシェルコマンドを実行します。
"""
print(interpreter.system_message)
```

### モデルの変更

ⓘ **ローカルでの実行に問題がありますか？** 新しい[GPUセットアップガイド](/docs/GPU.md)と[Windowsセットアップガイド](/docs/WINDOWS.md)を読んでください。

`Code Llama` を使用するには、コマンドラインからローカルモードで `interpreter` を実行します。

```shell
interpreter --local
```

`gpt-3.5-turbo`の場合は、fastモードを使用します。

```shell
interpreter --fast
```

Pythonでは、手動でモデルを設定する必要があります。

```python
interpreter.model = "gpt-3.5-turbo"
```

### Azureサポート

Azureデプロイメントに接続するには、`--use-azure`フラグでこれを設定します。

```
interpreter --use-azure
```

Pythonでは、次の変数を設定します：

```
interpreter.use_azure = True
interpreter.api_key = "あなたの_openai_api_key"
interpreter.azure_api_base = "あなたの_azure_api_base"
interpreter.azure_api_version = "あなたの_azure_api_version"
interpreter.azure_deployment_name = "あなたの_azure_deployment_name"
interpreter.azure_api_type = "azure"
```

### デバッグモード

寄稿者がOpen Interpreterを調査するのを助けるために、`--debug`モードは非常に詳細です。

フラグ（`interpreter --debug`）を使用してデバッグモードを有効にするか、チャット中に有効にできます：

```
$ interpreter
...
> %debug # <- デバッグモードをオンにする
```

### .envでの設定
Open Interpreterは、.envファイルを使用してデフォルトの動作を設定することを許可しています。これにより、毎回コマンドライン引数を変更することなく、インタープリタを設定する柔軟な方法が提供されます。

サンプルの.env設定は次のとおりです：

```
INTERPRETER_CLI_AUTO_RUN=False
INTERPRETER_CLI_FAST_MODE=False
INTERPRETER_CLI_LOCAL_RUN=False
INTERPRETER_CLI_DEBUG=False
INTERPRETER_CLI_USE_AZURE=False
```

これらの値を.envファイルで変更して、Open Interpreterのデフォルトの動作を変更できます。

## 安全に関する注意

生成されたコードはローカル環境で実行されるため、ファイルやシステム設定と対話することができ、データロスやセキュリティリスクなどの予期しない結果が生じる可能性があります。

**⚠️ Open Interpreterはコードを実行する前にユーザーの確認を求めます。**

確認を回避する

ために `interpreter -y` を実行するか、`interpreter.auto_run = True` を設定できます。その場合：

- ファイルやシステム設定を変更するコマンドを要求するときは注意してください。
- Open Interpreterを自動運転車のように注意深く見て、ターミナルを閉じることでプロセスを終了する準備をしてください。
- Google ColabやReplitのような制限された環境でOpen Interpreterを実行することを検討してください。これらの環境はより孤立しており、任意のコードを実行することに関連するリスクを減少させます。

## それはどのように動作するのか？

Open Interpreterは、`exec()`関数を備えた[関数呼び出し言語モデル](https://platform.openai.com/docs/guides/gpt/function-calling)を装備しており、実行する`language`（"python"や"javascript"など）と`code`を受け入れます。

その後、モデルのメッセージ、コード、およびシステムの出力をMarkdownとしてターミナルにストリームします。

# 貢献

貢献に興味を持っていただき、ありがとうございます！コミュニティからの関与を歓迎しています。

詳しくは、[貢献ガイドライン](/docs/contributing.md)を参照してください。

## ライセンス

Open InterpreterはMITライセンスの下でライセンスされています。ソフトウェアの使用、コピー、変更、配布、サブライセンス、および販売のコピーが許可されています。

**注意**: このソフトウェアはOpenAIとは関連していません。
> あなたの指先の速さで動く初級プログラマーにアクセスできることは... 新しいワークフローを努力なく効率的にすることができ、プログラミングの恩恵を新しい観客に開くことができます。
>
> — _OpenAIのコードインタープリタリリース_

<br>
<br>
<br>

**注意**: この翻訳は人工知能によって作成されました。誤りが含まれていることが確実です。
Open Interpreterが世界中を旅するのを助けるため、訂正を含むプルリクエストをしてください！
