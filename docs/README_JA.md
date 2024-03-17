
<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/Hvz9Axh84z">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="docs/README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="docs/README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="docs/README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/>
    <br>
    <br>
    <strong>言語モデルにコードを実行させよう</strong><br>
    <br><a href="https://openinterpreter.com">デスクトップアプリへの早期アクセスを取得</a>‎ ‎ |‎ ‎ <a href="https://docs.openinterpreter.com/">ドキュメント</a><br>
</p>

<br>

![poster](https://github.com/KillianLucas/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br> 
<p align="center">
<strong>ニューコンピューターアップデート</strong>で<strong><code>--os</code></strong>と新しい<strong>コンピューターAPI</strong>が導入されました。<a href="https://changes.openinterpreter.com/log/the-new-computer-update">続きを読む→</a>
</p>
<br>

```shell
pip install open-interpreter  
```

> うまくいかない場合は[セットアップガイド](https://docs.openinterpreter.com/getting-started/setup)をご覧ください。

```shell
interpreter
```

<br>

**Open Interpreter**を使うと、LLMがローカル環境でコード(Python、JavaScript、シェルスクリプトなど)を実行できるようになります。インストール後に`$ interpreter`を実行すると、ターミナル内のChatGPTのようなインターフェースを通じてOpen Interpreterとチャットできます。

これにより、コンピューターの汎用的な機能に自然言語でアクセスできるようになります:

- 写真、動画、PDF等の作成・編集
- Chromeブラウザーを操作して調査を実行
- 大規模なデータセットのプロット、クリーニング、分析
- ...など

**⚠️ 注意: コードを実行する前にユーザーの承認が求められます。**

<br>

## デモ

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### インタラクティブなデモもGoogle Colabで利用可能です:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)  

#### 映画「Her」からインスパイアされた音声インターフェースの例もあります:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## クイックスタート

```shell
pip install open-interpreter
```

### ターミナル

インストール後、`interpreter`を実行するだけです:

```shell  
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("AAPLとMETAの正規化された株価をプロット") # 単一のコマンドを実行
interpreter.chat() # インタラクティブなチャットを開始
```

## ChatGPTのコードインタープリターとの比較

OpenAIがGPT-4で[Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter)をリリースしたことで、ChatGPTを使って現実世界のタスクを達成する素晴らしい機会が訪れました。

しかし、OpenAIのサービスはホスト型で、クローズドソースであり、大きく制限されています:

- インターネットアクセス不可。
- [事前インストールされたパッケージが限定的](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。  
- 最大アップロード容量100MB、実行時間制限120.0秒。
- 環境が終了すると、状態(生成されたファイルやリンクを含む)がクリアされる。

---

Open Interpreterは、ローカル環境で実行することでこれらの制限を克服します。インターネットにフルアクセスでき、時間やファイルサイズの制限がなく、あらゆるパッケージやライブラリを利用できます。

これにより、GPT-4のコードインタープリターのパワーとローカル開発環境の柔軟性が組み合わされます。

## コマンド

**アップデート:** ジェネレーターアップデート(0.1.5)でストリーミングが導入されました:

```python
message = "現在使用しているOSは何ですか?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```  

### インタラクティブチャット

ターミナルでインタラクティブチャットを開始するには、コマンドラインから`interpreter`を実行します:

```shell
interpreter  
```

または、Pythonファイルから`interpreter.chat()`を実行します:

```python
interpreter.chat()
```

**各チャンクをストリーミングすることもできます:**

```python
message = "現在使用しているOSは何ですか?" 

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### プログラム的なチャット

より正確な制御が必要な場合は、メッセージを直接`.chat(message)`に渡すことができます:

```python
interpreter.chat("/videosにあるすべての動画に字幕を追加して。")

# ... ターミナルに出力をストリーミングし、タスクを完了 ...

interpreter.chat("良い感じだけど、字幕をもう少し大きくできる?") 

# ...
```

### 新しいチャットを開始

Pythonでは、Open Interpreterは会話履歴を記憶します。新しく開始したい場合は、リセットできます:

```python
interpreter.messages = []  
```

### チャットの保存と復元

`interpreter.chat()`はメッセージのリストを返します。これを使って`interpreter.messages = messages`で会話を再開できます:

```python
messages = interpreter.chat("私の名前はKillianです。") # メッセージを'messages'に保存
interpreter.messages = [] # インタープリターをリセット("Killian"は忘れられる)

interpreter.messages = messages # 'messages'からチャットを再開("Killian"は記憶される)  
```

### システムメッセージのカスタマイズ

Open Interpreterのシステムメッセージを確認・設定して、機能を拡張したり、権限を変更したり、より多くのコンテキストを与えることができます。

```python
interpreter.system_message += """  
ユーザーが確認しなくても良いように、シェルコマンドを-yオプション付きで実行してください。
"""
print(interpreter.system_message)
```

### 言語モデルの変更

Open Interpreterは[LiteLLM](https://docs.litellm.ai/docs/providers/)を使ってホスト型の言語モデルに接続します。 

モデルパラメーターを設定することで、モデルを変更できます:

```shell
interpreter --model gpt-3.5-turbo  
interpreter --model claude-2
interpreter --model command-nightly
```

Pythonでは、オブジェクトにモデルを設定します:

```python 
interpreter.llm.model = "gpt-3.5-turbo"
```

[適切な"model"文字列はこちらで確認できます。](https://docs.litellm.ai/docs/providers/)

### Open Interpreterをローカルで実行

#### ターミナル

Open InterpreterはOpenAI互換のサーバーを使ってモデルをローカルで実行できます。(LM Studio、jan.ai、ollamaなど)

推論サーバーのapi_base URLを指定して`interpreter`を実行するだけです(LM Studioのデフォルトは`http://localhost:1234/v1`):

```shell
interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"  
```

あるいは、サードパーティ製ソフトウェアをインストールせずにLlamafileを使う方法もあります:

```shell
interpreter --local
```

詳しいガイドは[Mike Birdのこの動画](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)をご覧ください。

**LM Studioをバックグラウンドで実行する方法**

1. [https://lmstudio.ai/](https://lmstudio.ai/)からダウンロードして起動。
2. モデルを選択し、**↓ Download**をクリック。
3. 左側(💬の下)にある**↔️**ボタンをクリック。
4. 上部でモデルを選択し、**Start Server**をクリック。

サーバーが起動したら、Open Interpreterとの会話を開始できます。 

> **注意:** ローカルモードでは`context_window`が3000に、`max_tokens`が1000に設定されます。モデルの要件が異なる場合は、これらのパラメーターを手動で設定してください(下記参照)。

#### Python

Pythonパッケージを使うと、各設定をより細かく制御できます。LM Studioを複製して接続するには、以下の設定を使用します:

```python
from interpreter import interpreter

interpreter.offline = True # Open Proceduresなどのオンライン機能を無効化
interpreter.llm.model = "openai/x" # OIにOpenAIのフォーマットでメッセージを送るよう指示
interpreter.llm.api_key = "fake_key" # LM Studioとの通信に使用するLiteLLMにはこれが必要
interpreter.llm.api_base = "http://localhost:1234/v1" # OpenAI互換のサーバーを指定

interpreter.chat()  
```

#### コンテキストウィンドウ、最大トークン数

ローカルで実行するモデルの`max_tokens`と`context_window`(トークン単位)を変更できます。

ローカルモードでは、コンテキストウィンドウが小さいほどRAMの使用量が少なくなります。失敗する場合や遅い場合は、もっと短いウィンドウ(~1000)を試してみることをおすすめします。`max_tokens`が`context_window`より小さいことを確認してください。

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### 詳細モード

Open Interpreterを調べるために、デバッグ用の`--verbose`モードを用意しています。

詳細モードは、フラグ(`interpreter --verbose`)を使うか、チャット中に有効にできます:

```shell  
$ interpreter
... 
> %verbose true <- 詳細モードをオン

> %verbose false <- 詳細モードをオフ  
```

### インタラクティブモードのコマンド

インタラクティブモードでは、以下のコマンドを使って操作性を向上できます。利用可能なコマンドの一覧:

**利用可能なコマンド:**

- `%verbose [true/false]`: 詳細モードの切り替え。引数なしまたは`true`で詳細モードに入ります。`false`で詳細モードを終了します。
- `%reset`: 現在のセッションの会話をリセットします。
- `%undo`: 直前のユーザーメッセージとAIの応答をメッセージ履歴から削除します。
- `%tokens [prompt]`: (_実験的_) 次のプロンプトとともにコンテキストとして送信されるトークンを計算し、そのコストを見積もります。オプションで、`prompt`が指定された場合はそのトークンとコストを計算します。見積もりコストには[LiteLLMの`cost_per_token()`メソッド](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token)を使用します。
- `%help`: ヘルプメッセージを表示します。

### 設定 / プロファイル

Open Interpreterでは、`yaml`ファイルを使ってデフォルトの動作を設定できます。

これにより、コマンドライン引数を毎回変更することなく、柔軟にインタープリターの設定ができます。

以下のコマンドを実行して、プロファイルディレクトリを開きます:

```
interpreter --profiles  
```

そこに`yaml`ファイルを追加できます。デフォルトのプロファイルは`default.yaml`という名前です。

#### 複数のプロファイル

Open Interpreterは複数の`yaml`ファイルをサポートしているので、設定を簡単に切り替えることができます:

```
interpreter --profile my_profile.yaml
```

## FastAPIサーバーのサンプル

ジェネレーターアップデートにより、Open InterpreterをHTTP RESTエンドポイントから制御できるようになりました:

```python
# server.py

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from interpreter import interpreter

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

また、`interpreter.server()`を実行するだけで、上記と同一のサーバーを起動することもできます。

## Android

AndroidデバイスへのOpen Interpreterのインストール方法については、[open-interpreter-termuxリポジトリ](https://github.com/MikeBirdTech/open-interpreter-termux)のステップバイステップガイドをご覧ください。

## 安全性に関する注意

生成されたコードはローカル環境で実行されるため、ファイルやシステム設定と相互作用し、データ損失やセキュリティリスクなどの予期しない結果につながる可能性があります。 

**⚠️ Open Interpreterはコードを実行する前にユーザーの確認を求めます。**

`interpreter -y`を実行するか、`interpreter.auto_run = True`を設定すると、この確認をバイパスできます。その場合:

- ファイルやシステム設定を変更するコマンドを要求する際は注意してください。
- Open Interpreterを自動運転車のように監視し、ターミナルを閉じてプロセスを終了する準備をしてください。  
- Google ColabやReplitのような制限された環境でOpen Interpreterを実行することを検討してください。これらの環境はより隔離されており、任意のコードを実行するリスクを軽減します。

リスクを軽減するための[セーフモード](docs/SAFE_MODE.md)の**実験的**サポートがあります。

## 動作原理

Open Interpreterは、`language`(PythonやJavaScriptなど)と実行する`code`を受け取る`exec()`関数を備えた[関数呼び出し言語モデル](https://platform.openai.com/docs/guides/gpt/function-calling)を装備しています。

そして、モデルのメッセージ、コード、システムの出力をマークダウンとしてターミナルにストリーミングします。

# 貢献

ご協力いただきありがとうございます!コミュニティからの関与を歓迎します。

関わり方の詳細については、[貢献ガイドライン](docs/CONTRIBUTING.md)をご覧ください。 

# ロードマップ

Open Interpreterの未来を見るには、[ロードマップ](https://github.com/KillianLucas/open-interpreter/blob/main/docs/ROADMAP.md)をご覧ください。

**注意**: このソフトウェアはOpenAIと提携していません。

![thumbnail-ncu](https://github.com/KillianLucas/open-interpreter/assets/63927363/1b19a5db-b486-41fd-a7a1-fe2028031686)

> 指先の速さで動くジュニアプログラマーにアクセスできることで、新しいワークフローが楽に効率的になり、プログラミングの恩恵が新しい聴衆にもたらされる可能性があります。
>  
> - _OpenAIのCode Interpreterリリースより_

<br>
