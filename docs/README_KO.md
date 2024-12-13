<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/Hvz9Axh84z">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="docs/README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="docs/README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="docs/README_ES.md"> <img src="https://img.shields.io/badge/Español-white.svg" alt="ES doc"/></a>
    <a href="docs/README_UK.md"><img src="https://img.shields.io/badge/Українська-white.svg" alt="UK doc"/></a>
    <a href="docs/README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <a href="LICENSE"><img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/></a>
    <br>
    <br><a href="https://0ggfznkwh4j.typeform.com/to/G21i9lJ2">데스크톱 앱 얼리 액세스 신청하기</a>‎ ‎ |‎ ‎ <a href="https://docs.openinterpreter.com/">문서</a><br>
</p>

<br>

<img alt="local_explorer" src="https://github.com/OpenInterpreter/open-interpreter/assets/63927363/d941c3b4-b5ad-4642-992c-40edf31e2e7a">

<br>
</p>
<br>

```shell
pip install open-interpreter
```

> 설치가 안 되시나요? [설치 가이드](https://docs.openinterpreter.com/getting-started/setup)를 확인해보세요.

```shell
interpreter
```

<br>

**Open Interpreter**는 LLM이 로컬에서 코드(Python, Javascript, Shell 등)를 실행할 수 있게 해줍니다. 설치 후 `$ interpreter`를 실행하면 터미널에서 ChatGPT와 유사한 인터페이스를 통해 Open Interpreter와 대화할 수 있습니다.

이를 통해 컴퓨터의 일반적인 기능에 대한 자연어 인터페이스를 제공합니다.

- 사진, 비디오, PDF 등의 생성 및 편집
- Chrome 브라우저를 제어하여 리서치 수행
- 대규모 데이터셋의 시각화, 정제 및 분석
- 기타 등등

**⚠️ 주의: 코드를 실행하기 전에 사용자의 승인을 요청합니다.**

<br>

## 데모

https://github.com/OpenInterpreter/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab에서도 대화형 데모를 이용할 수 있습니다.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### 영화 *Her*에서 영감을 받은 음성 인터페이스 예제도 있습니다.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## 빠른 시작

```shell
pip install open-interpreter
```

### 터미널

설치 후, `interpreter` 를 실행합니다.

```shell
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("AAPL과 META의 정규화된 주가를 그래프로 그려주세요") # 단일 명령 실행
interpreter.chat() # 대화형 채팅 시작
```

### GitHub Codespaces

이 저장소의 GitHub 페이지에서 `,` 키를 눌러 코드스페이스를 생성하세요. 잠시 후 open-interpreter가 사전 설치된 클라우드 가상 머신 환경이 제공됩니다. 시스템 손상 걱정 없이 바로 상호작용을 시작하고 시스템 명령 실행을 자유롭게 확인할 수 있습니다.

## ChatGPT의 Code Interpreter와 비교

OpenAI가 GPT-4와 함께 출시한 [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter)는 ChatGPT로 실제 작업을 수행할 수 있는 훌륭한 기회를 제공합니다.

하지만 OpenAI의 서비스는 호스팅되어 있고, 폐쇄적이며, 다음과 같은 엄격한 제한이 있습니다.

- 인터넷 접근 불가
- [사전 설치된 패키지가 제한적](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)
- 최대 업로드 100MB, 실행 시간 120초 제한
- 환경이 종료되면 생성된 파일이나 링크와 함께 상태가 초기화됨

---

Open Interpreter는 로컬 환경에서 실행함으로써 이러한 제한을 극복합니다. 인터넷에 완전히 접근할 수 있고, 시간이나 파일 크기의 제한 없이 어떤 패키지나 라이브러리도 사용할 수 있습니다.

이는 GPT-4 Code Interpreter의 강력함과 로컬 개발 환경의 유연성을 결합한 것입니다.

## 명령어

**업데이트:** Generator 업데이트(0.1.5)로 스트리밍 기능이 도입되었습니다.

```python
message = "어떤 운영체제를 사용하고 있나요?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 대화형 채팅

터미널에서 대화형 채팅을 시작하려면, 명령줄에서 `interpreter` 실행

```shell
interpreter
```

또는 .py 파일에서 `interpreter.chat()` 실행

```python
interpreter.chat()
```

**각 청크를 스트리밍할 수도 있습니다.**

```python
message = "어떤 운영체제를 사용하고 있나요?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 프로그래밍적 채팅

더 정확한 제어를 위해 메시지를 직접 `.chat(message)`로 전달할 수 있습니다.

```python
interpreter.chat("/videos 폴더의 모든 비디오에 자막을 추가해주세요.")

# ... 터미널에 출력을 스트리밍하고 작업 완료 ...

interpreter.chat("잘 됐네요. 근데 자막을 좀 더 크게 만들 수 있나요?")

# ...
```

### 새로운 채팅 시작

Python에서 Open Interpreter는 대화 기록을 저장합니다. 처음부터 다시 시작하려면 다음과 같이 초기화할 수 있습니다.

```python
interpreter.messages = []
```

### 채팅 저장 및 복원

`interpreter.chat()`은 메시지 리스트를 반환하며, `interpreter.messages = messages`로 대화를 재개할 수 있습니다.

```python
messages = interpreter.chat("제 이름은 김철수입니다.") # 메시지를 'messages'에 저장
interpreter.messages = [] # 인터프리터 초기화("김철수"가 잊혀짐)

interpreter.messages = messages # 'messages'에서 채팅 재개("김철수"를 기억함)
```

### 시스템 메시지 커스터마이징

Open Interpreter의 시스템 메시지를 확인하고 설정하여 기능을 확장하거나, 권한을 수정하거나, 더 많은 컨텍스트를 제공할 수 있습니다.

```python
interpreter.system_message += """
쉘 명령어를 -y 플래그와 함께 실행하여 사용자가 확인할 필요가 없도록 합니다.
"""
print(interpreter.system_message)
```

### 언어 모델 변경

Open Interpreter는 [LiteLLM](https://docs.litellm.ai/docs/providers/)을 사용하여 호스팅된 언어 모델에 연결합니다.

모델 매개변수를 설정하여 모델을 변경할 수 있습니다.

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

Python에서는 객체에서 모델을 설정합니다.

```python
interpreter.llm.model = "gpt-3.5-turbo"
```

[적절한 "model" 문자열은 여기에서 찾아보세요.](https://docs.litellm.ai/docs/providers/)

### Open Interpreter를 로컬에서 실행하기

#### 터미널

Open Interpreter는 OpenAI 호환 서버를 사용하여 모델을 로컬에서 실행할 수 있습니다(LM Studio, jan.ai, ollama 등).

추론 서버의 api_base URL을 지정하여 `interpreter`를 실행하기만 하면 됩니다(LM Studio의 경우 기본값은 `http://localhost:1234/v1` 입니다.)

```shell
interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"
```

또는 서드파티 소프트웨어 설치 없이 Llamafile을 사용할 수 있습니다.

```shell
interpreter --local
```

더 자세한 가이드는 [Mike Bird의 이 영상](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)을 참고하세요.

**LM Studio를 백그라운드에서 실행하는 방법**

1. [https://lmstudio.ai/](https://lmstudio.ai/)에서 다운로드하고 실행합니다.
2. 모델을 선택하고 **↓ 다운로드**를 클릭합니다.
3. 왼쪽의 **↔️** 버튼(💬 아래)을 클릭합니다.
4. 상단에서 모델을 선택하고 **서버 시작**을 클릭합니다.

서버가 실행되면 Open Interpreter와 대화를 시작할 수 있습니다.

> **주의:** 로컬 모드에서는 `context_window`를 3000으로, `max_tokens`를 1000으로 설정합니다. 모델에 따라 다른 요구사항이 있다면 이러한 파라미터를 수동으로 설정하세요(아래 참조).

#### Python

Python 패키지는 각 설정에 대해 더 많은 제어를 제공합니다. LM Studio에 연결하려면 다음 설정을 사용하세요.

```python
from interpreter import interpreter

interpreter.offline = True # 온라인 기능(Open Procedures 등) 비활성화
interpreter.llm.model = "openai/x" # OI에게 OpenAI 형식으로 메시지를 보내도록 지시
interpreter.llm.api_key = "fake_key" # LM Studio와 통신하는 데 사용하는 LiteLLM에 필요
interpreter.llm.api_base = "http://localhost:1234/v1" # OpenAI 호환 서버를 가리킴

interpreter.chat()
```

#### 컨텍스트 윈도우, 최대 토큰 수

로컬에서 실행 중인 모델의 `max_tokens`와 `context_window`(토큰 단위)를 변경할 수 있습니다.

로컬 모드에서는 작은 컨텍스트 윈도우가 RAM을 적게 사용하므로, 실패하거나 느린 경우 더 짧은 윈도우(~1000)를 시도해보세요. `max_tokens`가 `context_window`보다 작은지 확인하세요.

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### 상세 모드

Open Interpreter 검사를 돕기 위해 디버깅용 `--verbose` 모드가 있습니다.

플래그(`interpreter --verbose`)를 사용하거나 채팅 중에 활성화할 수 있습니다.

```shell
$ interpreter
...
> %verbose true <- 상세 모드 켜기
> %verbose false <- 상세 모드 끄기
```

### 대화형 모드 명령어

대화형 모드에서는 다음 명령어들로 사용 경험을 향상시킬 수 있습니다. 사용 가능한 명령어 목록은 다음과 같습니다.

**사용 가능한 명령어:**

- `%verbose [true/false]`: 상세 모드를 전환합니다. 인수 없이 또는 `true`로 상세 모드에 진입합니다. `false`로 상세 모드를 종료합니다.
- `%reset`: 현재 세션의 대화를 초기화합니다.
- `%undo`: 메시지 기록에서 이전 사용자 메시지와 AI의 응답을 제거합니다.
- `%tokens [prompt]`: (_실험적_) 다음 프롬프트로 전송될 토큰을 계산하고 비용을 추정합니다. 선택적으로 `prompt`가 제공된 경우 해당 프롬프트의 토큰과 추정 비용을 계산합니다. 추정 비용은 [LiteLLM의 `cost_per_token()` 메서드](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token)에 의존합니다.
- `%help`: 도움말 메시지를 표시합니다.

### 설정 / 프로필

Open Interpreter는 `yaml` 파일을 사용하여 기본 동작을 설정할 수 있습니다.

이를 통해 매번 명령줄 인수를 변경하지 않고도 유연하게 인터프리터를 구성할 수 있습니다.

다음 명령어를 실행하여 프로필 디렉토리를 엽니다:

```
interpreter --profiles
```

여기에 `yaml` 파일을 추가할 수 있습니다. 기본 프로필 이름은 `default.yaml`입니다.

#### 다중 프로필

Open Interpreter는 여러 `yaml` 파일을 지원하여 쉽게 구성을 전환할 수 있습니다:

```
interpreter --profile my_profile.yaml
```

## FastAPI 서버 예제

Generator 업데이트로 Open Interpreter를 HTTP REST 엔드포인트로 제어할 수 있게 되었습니다.

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

`interpreter.server()`를 실행하여 위와 동일한 서버를 시작할 수도 있습니다.

## Android

Android 기기에 Open Interpreter를 설치하는 단계별 가이드는 [open-interpreter-termux 저장소](https://github.com/MikeBirdTech/open-interpreter-termux)에서 확인할 수 있습니다.

## 안전 주의사항

생성된 코드는 로컬 환경에서 실행되므로 파일 및 시스템 설정과 상호작용하여 데이터 손실이나 보안 위험과 같은 예기치 않은 결과를 초래할 수 있습니다.

**⚠️ Open Interpreter는 코드를 실행하기 전에 사용자의 승인을 요청합니다.**

`interpreter -y`를 실행하거나 `interpreter.auto_run = True`를 설정하여 이 확인을 건너뛸 수 있습니다. 이 경우,

- 파일이나 시스템 설정을 수정하는 명령을 실행할 때 주의하세요.
- 자율주행 자동차를 지켜보듯이 Open Interpreter를 주시하고, 터미널을 닫아 프로세스를 종료할 준비를 하세요.
- Google Colab이나 Replit과 같은 제한된 환경에서 Open Interpreter를 실행하는 것을 고려하세요. 이러한 환경은 더 격리되어 있어 임의 코드 실행의 위험을 줄일 수 있습니다.

일부 위험을 완화하기 위한 [안전 모드](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/SAFE_MODE.md)에 대한 **실험적** 지원이 있습니다.

## 작동 방식

Open Interpreter는 [함수 호출 가능한 언어 모델](https://platform.openai.com/docs/guides/gpt/function-calling)에 `exec()` 함수를 제공하여 실행할 `언어`("Python"이나 "JavaScript" 등)와 `코드`를 받습니다.

그런 다음 모델의 메시지, 코드, 시스템 출력을 Markdown 형식으로 터미널에 스트리밍합니다.

# 오프라인에서 문서 접근하기

전체 [문서](https://docs.openinterpreter.com/)는 인터넷 연결 없이도 이용할 수 있습니다.

[Node](https://nodejs.org/en)가 선행 요구사항입니다.

- 버전 18.17.0 또는 이후 18.x.x 버전
- 버전 20.3.0 또는 이후 20.x.x 버전
- 21.0.0부터 시작하는 모든 버전(상한선 없음)

[Mintlify](https://mintlify.com/) 설치한 다음,

```bash
npm i -g mintlify@latest
```

docs 디렉토리로 이동하여 적절한 명령어를 실행합니다.

```bash
# 프로젝트 루트 디렉토리에 있다고 가정
cd ./docs

# 문서 서버 실행
mintlify dev
```

새 브라우저 창이 열립니다. 문서 서버가 실행되는 동안 [http://localhost:3000](http://localhost:3000)에서 문서에 접근할 수 있습니다.

# 기여하기

프로젝트에 관심을 가져주셔서 감사합니다! 커뮤니티의 참여를 환영합니다.

기여 방법에 대한 자세한 내용은 [기여 가이드라인](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/CONTRIBUTING.md)을 참조하세요.

# 로드맵

[우리의 로드맵](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/ROADMAP.md)에서 Open Interpreter의 미래를 미리 볼 수 있습니다.

**참고**: 이 소프트웨어는 OpenAI와 관련이 없습니다.

![thumbnail-ncu](https://github.com/OpenInterpreter/open-interpreter/assets/63927363/1b19a5db-b486-41fd-a7a1-fe2028031686)

> 마치 손끝에서 움직이는 주니어 프로그래머를 두는 것과 같은 이 경험은... 새로운 작업 흐름을 쉽고 효율적으로 만들어주며, 프로그래밍의 장점을 더 넓은 대중에게 전달할 수 있게 합니다.
>
> — _OpenAI의 Code Interpreter 릴리즈_

<br>
