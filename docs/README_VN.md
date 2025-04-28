<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="README_ES.md"> <img src="https://img.shields.io/badge/Español-white.svg" alt="ES doc"/></a>
    <a href="docs/README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="docs/README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="README_UK.md"><img src="https://img.shields.io/badge/Українська-white.svg" alt="UK doc"/></a>
    <a href="docs/README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <a href="../LICENSE"><img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/></a>
    <br>
    <br><a href="https://openinterpreter.com">Quyền truy cập sớm dành cho ứng dung trên máy tính</a>‎ ‎ |‎ ‎ <b><a href="https://docs.openinterpreter.com/">Tài liệu tham khảo</a></b><br>
</p>

<br>

<img alt="local_explorer" src="https://github.com/OpenInterpreter/open-interpreter/assets/63927363/d941c3b4-b5ad-4642-992c-40edf31e2e7a">

<br>

```shell
pip install open-interpreter
```

> Không cài đặt được? Hãy đọc [hướng dẫn setup](https://docs.openinterpreter.com/getting-started/setup).

```shell
interpreter
```

<br>

**Open Interpreter** sẽ giúp LLMs chạy code (Python, Javascript, Shell,...) trên máy tính local của bạn. Bạn có thể nói chuyện với Open Interpreter thông qua giao diện giống với ChatGPT ngay trên terminal của bạn bằng cách chạy lệnh `$ interpreter` sau khi cài đặt thành công.

Các tính năng chung giao diện ngôn ngữ tự nhiên mang lại

- Tạo và chỉnh sửa ảnh, videos, PDF,...
- Điều khiển trình duyệt Chrome để tiến hành nghiên cứu
- Vẽ, làm sạch và phân tích các tập dữ liệu lớn (large datasets)
- ...và nhiều hơn thế nữa.

**⚠️ Lưu ý: Bạn sẽ được yêu cầu phê duyệt code trước khi chạy.**

<br>

## Demo

https://github.com/OpenInterpreter/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Bản demo có sẵn trên Google Colab:

[![Mở trong Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### Đi kèm với ứng dụng demo qua tương tác giọng nói, lấy cảm hứng từ _Cô ấy_:

[![Mở trong Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## Hướng dẫn khởi dộng nhanh

```shell
pip install open-interpreter
```

### Terminal

Sau khi cài đặt, chạy lệnh `interpreter`:

```shell
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # Chạy trên 1 dòng lệnh
interpreter.chat() # Khởi động chat có khả năng tương tác
```

### GitHub Codespaces

Nhấn phím `,` trên trang GitHub của repo này để tạo codespace. Sau một lát, bạn sẽ nhận được môi trường máy ảo cloud được cài đặt sẵn với open-interpreter. Sau đó, bạn có thể bắt đầu tương tác trực tiếp với nó và thoải mái thực thi các lệnh mà không lo hư hỏng hệ thống.

## So sánh Code Interpreter của ChatGPT

Bản phát hành của OpenAI [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) sử dụng GPT-4 tăng khả năng hoàn thiện vấn đề thực tiễn với ChatGPT.

Tuy nhiên, dịch vụ của OpenAI được lưu trữ, mã nguồn đóng, và rất hạn chế:

- Không có truy cập Internet.
- [Số lượng gói cài đặt hỗ trỡ có sẵn giới hạn](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- Tốc độ upload tối đa 100 MB, timeout giới hạn 120.0 giây .
- Tin nhắn kèm với các file và liên kết được tạo trước đó sẽ bị xóa khi đóng môi trường lại.

---

Open Interpreter khắc phục những hạn chế này bằng cách chạy local trong môi trường máy tính của bạn. Nó có toàn quyền truy cập vào Internet, không bị hạn chế về thời gian hoặc kích thước file và có thể sử dụng bất kỳ gói hoặc thư viện nào.

Đây là sự kết hợp sức mạnh của mã nguồn của GPT-4 với tính linh hoạt của môi trường phát triển local của bạn.

## Các lệnh

**Update:** Cập nhật trình tạo lệnh (0.1.5) giới thiệu tính năng streaming:

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### Trò chuyện tương tác

Để tạo một cuộc trò chuyện tương tác từ terminal của bạn, chạy `interpreter` bằng dòng lệnh:

```shell
interpreter
```

hoặc `interpreter.chat()` từ file .py :

```python
interpreter.chat()
```

**Bạn cũng có thể streaming từng chunk:**

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### Lập trình cuộc trò chuyện

Để kiểm soát tốt hơn, bạn có thể gửi tin nhắn trực tiếp qua `.chat(message)`:

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Stream dữ liệu output đến terminal của bạn và hoàn thành tác vụ ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

### Tạo một cuộc trò chuyện mới:

Trong Python, Open Interpreter ghi nhớ lịch sử hội thoại, nếu muốn bắt đầu lại từ đầu, bạn có thể reset:

```python
interpreter.messages = []
```

### Lưu và khôi phục cuộc trò chuyện

`interpreter.chat()` trả về danh sách tin nhắn, có thể được sử dụng để tiếp tục cuộc trò chuyện với `interpreter.messages = messages`:

```python
messages = interpreter.chat("My name is Hung.") # Lưu tin nhắn tới 'messages'
interpreter.messages = [] # Khởi động lại trình phiên dịch ("Hung" sẽ bị lãng quên)

interpreter.messages = messages # Tiếp tục cuộc trò chuyện từ 'messages' ("Hung" sẽ được ghi nhớ)
```

### Cá nhân hoá tin nhắn từ hệ thống

Bạn có thể kiếm tra và điều chỉnh tin nhắn hệ thống từ Open Interpreter để mở rộng chức năng, thay đổi quyền, hoặc tạo ra nhiều ngữ cảnh hơn.

```python
interpreter.system_message += """
Run shell commands with -y so the user doesn't have to confirm them.
"""
print(interpreter.system_message)
```

### Thay đổi mô hình ngôn ngữ (Language Model)

Open Interpreter sử dụng mô hình [LiteLLM](https://docs.litellm.ai/docs/providers/) để kết nối tới các mô hình ngôn ngữ đang được host.

Bạn có thể thay đổi mô hình ngôn ngữ bằng cách thay đổi tham số model:

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

Ở trong Python, đổi model bằng cách thay đổi đối tượng:

```python
interpreter.llm.model = "gpt-3.5-turbo"
```

[Tìm tên chuỗi "model" phù hợp cho mô hình ngôn ngữ của bạn ở đây.](https://docs.litellm.ai/docs/providers/)

### Chạy Open Interpreter trên local

#### Terminal

Open Interpreter có thể sử dụng máy chủ tương thích với OpenAI để chạy các mô hình local. (LM Studio, jan.ai, ollama, v.v.)

Chỉ cần chạy `interpreter` với URL api_base của máy chủ suy luận của bạn (đối với LM studio mặc định là `http://localhost:1234/v1`):

```shell
interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"
```

Ngoài ra, bạn có thể sử dụng Llamafile mà không cần cài đặt bất kỳ phần mềm bên thứ ba nào bằng cách chạy:

```shell
interpreter --local
```

Để được hướng dẫn chi tiết hơn, hãy xem [video này của Mike Bird](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)

**Để chạy LM Studio ở chế độ background.**

1. Tải [https://lmstudio.ai/](https://lmstudio.ai/) và khởi động.
2. Chọn một mô hình rồi nhấn **↓ Download**.
3. Nhấn vào nút **↔️** ở bên trái (dưới 💬).
4. Chọn mô hình của bạn ở phía trên, rồi nhấn chạy **Start Server**.

Một khi server chạy, bạn có thể bắt đầu trò chuyện với Open Interpreter.

> **Lưu ý:** Chế độ local chỉnh `context_window` của bạn tới 3000, và `max_tokens` của bạn tới 600. Nếu mô hình của bạn có các yêu cầu khác, thì hãy chỉnh các tham số thủ công (xem bên dưới).

#### Python

Our Python package gives you more control over each setting. To replicate and connect to LM Studio, use these settings:

```python
from interpreter import interpreter

interpreter.offline = True # Tắt các tính năng online như Open Procedures
interpreter.llm.model = "openai/x" # Cài đặt OI gửi tin nhắn trong format của OpenAI
interpreter.llm.api_key = "fake_key" # LiteLLM dùng để tương tác với LM Studio, bắt buộc phải có
interpreter.llm.api_base = "http://localhost:1234/v1" # Endpoint của sever OpenAI bất kỳ nào đó

interpreter.chat()
```

#### Cửa sổ ngữ cảnh (Context Window), lượng token tối đa (Max Tokens)

Bạn có thể thay đổi `max_tokens` và `context_window` trong các model chạy trên local.

Ở chế độ local, các cửa sổ ngữ cảnh sẽ tiêu ít RAM hơn, vậy nên chúng tôi khuyến khích dùng cửa sổ nhỏ hơn (~1000) nếu như nó chạy không ổn định / hoặc nếu nó chậm. Hãy đảm bảo rằng `max_tokens` ít hơn `context_window`.

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### Chế độ verbose

Để giúp đóng góp kiểm tra Open Interpreter, thì chế độ `--verbose` hơi dài dòng.

Bạn có thể khởi động chế độ verbose bằng cách sử dụng cờ (`interpreter --verbose`), hoặc mid-chat:

```shell
$ interpreter
...
> %verbose true <- Khởi động chế độ verbose

> %verbose false <- Tắt chế độ verbose
```

### Các lệnh trong chế độ tương tác

Trong chế độ tương tác, bạn có thể sử dụng những dòng lệnh sau để cải thiện trải nghiệm của mình. Đây là danh sách các dòng lệnh có sẵn:

**Các lệnh có sẵn:**

- `%verbose [true/false]`: Bật chế độ verbose. Có hoặc không có `true` sẽ đều khởi động chế độ verbose. Với `false` thì nó tắt chế độ verbose.
- `%reset`: Khởi động lại toàn bộ phiên trò chuyện hiện tại.
- `%undo`: Xóa tin nhắn của người dùng trước đó và phản hồi của AI khỏi lịch sử tin nhắn.
- `%tokens [prompt]`: (_Experimental_) Tính toán các token sẽ được gửi cùng với lời nhắc tiếp theo dưới dạng ngữ cảnh và chi phí. Tùy chọn tính toán token và chí phí ước tính của một `prompt` nếu được cung cấp. Dựa vào [hàm `cost_per_token()` của mô hình LiteLLM](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) để tính toán.
- `%help`: Hiện lên trợ giúp cho cuộc trò chuyện.

### Cấu hình / Profiles

Open Interpreter cho phép bạn thiết lập các hành vi mặc định bằng cách sử dụng các file `yaml`.

Đây là cách linh hoạt để cấu hình trình thông dịch mà không cần thay đổi dòng lệnh mỗi lần.

Chạy lệnh sau để mở thư mục profile:

```
interpreter --profiles
```

Bạn có thể thêm tập tin `yaml` vào đó. Cấu hình mặc định có tên là `default.yaml`.

#### Multiple Profiles

Open Interpreter hỗ trợ nhiều file `yaml`, cho phép bạn dễ dàng chuyển đổi giữa các cấu hình:

```
interpreter --profile my_profile.yaml
```

## Máy chủ FastAPI mẫu

Bản cập nhật generator cho phép điều khiển Open Interpreter thông qua các endpoint HTTP REST:

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

Bạn cũng có thể khởi động một máy chủ giống hệt máy chủ ở trên bằng cách chạy `interpreter.server()`.

## Android

Bạn có thể tìm thấy hướng dẫn từng bước để cài đặt Open Interpreter trên thiết bị Android của mình trong [repo open-interpreter-termux](https://github.com/MikeBirdTech/open-interpreter-termux).

## Lưu ý an toàn

Vì code tạo được thực thi trong môi trường local của bạn nên nó có thể tương tác với các file và cài đặt hệ thống của bạn, có khả năng dẫn đến các kết quả không mong muốn như mất dữ liệu hoặc rủi ro bảo mật.

**⚠️ Open Interpreter sẽ yêu cầu xác nhận của người dùng trước khi chạy code.**

Bạn có thể chạy `interpreter -y` hoặc đặt `interpreter.auto_run = True` để bỏ qua xác nhận này, trong trường hợp đó:

- Hãy thận trọng khi yêu cầu các lệnh sửa đổi file hoặc cài đặt hệ thống.
- Theo dõi Open Interpreter giống như một chiếc ô tô tự lái và sẵn sàng kết thúc process bằng cách đóng terminal của bạn.
- Cân nhắc việc chạy Open Interpreter trong môi trường bị hạn chế như Google Colab hoặc Replit. Những môi trường này biệt lập hơn, giảm thiểu rủi ro khi chạy code.

Đây là hỗ trợ **thử nghiệm** cho [chế độ an toàn](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/SAFE_MODE.md) giúp giảm thiểu rủi ro.

## Cách thức hoạt động

Open Interpreter sử dụng [mô hình ngôn ngữ gọi hàm (function-calling language model)](https://platform.openai.com/docs/guides/gpt/function-calling) với một hàm `exec()`, chấp nhận một `language` (như "Python" hoặc "JavaScript") và `code` để chạy.

Sau đó, chúng tôi stream tin nhắn, code của mô hình và kết quả output của hệ thống của bạn đến terminal dưới dạng Markdown.

# Truy cập tài liệu offline

Toàn bộ [tài liệu](https://docs.openinterpreter.com/) có thể được truy cập mà không cần kết nối internet.

[Node](https://nodejs.org/en) cần phải được cài đặt:

- Phiên bản 18.17.0 hoặc bất kỳ phiên bản 18.x.x nào mới hơn.
- Phiên bản 20.3.0 hoặc bất kỳ phiên bản 20.x.x nào sau này.
- Bất kỳ phiên bản nào bắt đầu từ 21.0.0 trở đi, không có giới hạn phiên bản mới nhất có thể dùng.

Cài đặt [Mintlify](https://mintlify.com/):

```bash
npm i -g mintlify@latest
```

Thay đổi vào thư mục docs và chạy lệnh:

```bash
# Giả sử bạn đang ở thư mục root của dự án
cd ./docs

# Chạy server tài liệu trên local
mintlify dev
```

Một cửa sổ trình duyệt mới sẽ mở ra. Tài liệu sẽ có tại [http://localhost:3000](http://localhost:3000) cho tới khi nào local server vẫn chạy.

# Đóng góp

Cảm ơn bạn đã quan tâm đóng góp! Chúng tôi hoan nghênh sự tham gia của cộng đồng.

Vui lòng xem [Hướng dẫn đóng góp](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/CONTRIBUTING.md) để biết thêm chi tiết cách tham gia.

# Kế hoạch tương lai (Roadmap)

Hãy xem qua [roadmap của chúng tôi](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/ROADMAP.md) để biết thêm về kế hoạch Open Interpreter trong tương lai.

**Lưu ý**: Phần mềm này không liên kết với OpenAI.

![thumbnail-ncu](https://github.com/OpenInterpreter/open-interpreter/assets/63927363/1b19a5db-b486-41fd-a7a1-fe2028031686)

> Having access to a junior programmer working at the speed of your fingertips ... can make new workflows effortless and efficient, as well as open the benefits of programming to new audiences.
>
> — _OpenAI's Code Interpreter Release_
> Ý nghĩa câu trên có thể hiểu là: Hãy xem AI như một lập trình viên làm việc nhanh chóng và AI sẽ giúp bạn lập trình hiệu quả hơn rất nhiếu.

<br>
