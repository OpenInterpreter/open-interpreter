<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="README_ES.md"> <img src="https://img.shields.io/badge/Español-white.svg" alt="ES doc"/></a>
    <a href="docs/README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="docs/README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="docs/README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License"/>
    <br>
    <br>
    <b>chạy mô hình ngôn ngữ trí tuệ nhân tạo trên máy tính của bạn.</b><br>
    Mã nguồn mở và ứng dụng phát triển dựa trên code của OpenAI.<br>
    <br><a href="https://openinterpreter.com">Quyền truy cập sớm dành cho máy tính cá nhân</a>‎ ‎ |‎ ‎ <b><a href="https://docs.openinterpreter.com/">Tài liệu đọc tham khảo</a></b><br>
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

**Open Interpreter** Chạy LLMs trên máy tính cục bộ (Có thể sử dụng ngôn ngữ Python, Javascript, Shell, và nhiều hơn thế). Bạn có thể nói chuyện với Open Interpreter thông qua giao diện giống với ChatGPT ngay trên terminal của bạn bằng cách chạy lệnh `$ interpreter` sau khi tải thành công.

Các tính năng chung giao diện ngôn ngữ mang llại

- Tạo và chỉnh sửa ảnh, videos, PDF, vân vân...
- Điều khiển trình duyệt Chrome để tiến hành nghiên cứu
- Vẽ, làm sạch và phân tích các tập dữ liệu lớn (large datasets)
- ...vân vân.

**⚠️ Lưu ý: Bạn sẽ được yêu cầu phê duyệt mã trước khi chạy.**

<br>

## Thử nghiệm

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Bản thử nghiệm có sẵn trên Google Colab:

[![Mở trong Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### Đi kèm với ứng dụng mẫu qua tương tác giọng nói (Lấy cảm hứng từ _Cô ấy_ (Giọng nữ)):

[![Mở trong Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## Hướng dẫn khởi dộng ngắn

```shell
pip install open-interpreter
```

### Terminal

Sau khi cài đặt, chạy dòng lệnh `interpreter`:

```shell
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("Vẽ giá cổ phiếu đã bình hoá của AAPL và META ") # Chạy trên 1 dòng lệnh
interpreter.chat() # Khởi động chat có khả năng tương tác
```

## So sánh Code Interpreter của ChatGPT

Bản phát hành của OpenAI [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) sử dụng GPT-4 tăng khả năng hoàn thiện vấn đề thực tiễn với ChatGPT.

Tuy nhiên, dịch vụ của OpenAI được lưu trữ, mã nguồn đóng, và rất hạn chế:

- Không có truy cập Internet.
- [Số lượng gói cài đặt hỗ trỡ có sẵn giới hạn](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- tốc độ tải tối đa 100 MB , thời gian chạy giới hạn 120.0 giây .
- Trạng thái tin nhắn bị xoá kèm với các tệp và liên kết được tạo trước đó khi đóng môi trường lại.

---

Open Interpreter khắc phục những hạn chế này bằng cách chạy cục bộ trobộ môi trường máy tính của bạn. Nó có toàn quyền truy cập vào Internet, không bị hạn chế về thời gian hoặc kích thước tệp và có thể sử dụng bất kỳ gói hoặc thư viện nào.

Đây là sự kết hợp sức mạnh của mã nguồn của GPT-4 với tính linh hoạt của môi trường phát triển cục bộ của bạn.

## Dòng lệnh

**Update:** Cập nhật trình tạo lệnh (0.1.5) giới thiệu tính năng trực tuyến:

```python
message = "Chúng ta đang ở trên hệ điều hành nào?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### Trò chuyện tương tác

Để tạo một cuộc trò chuyện tương tác từ terminal của bạn, chạy `interpreter` bằng dòng lệnh:

```shell
interpreter
```

hoặc `interpreter.chat()` từ file có đuôi .py :

```python
interpreter.chat()
```

**Bạn cũng có thể phát trực tuyến từng đoạn:**

```python
message = "Chúng ta đang chạy trên hệ điều hành nào?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### Trò chuyện lập trình được

Để kiểm soát tốt hơn, bạn chuyển tin nhắn qua `.chat(message)`:

```python
interpreter.chat("Truyền phụ đề tới tất cả videos vào /videos.")

# ... Truyền đầu ra đến thiết bị đầu cuối của bạn (terminal) hoàn thành tác vụ ...

interpreter.chat("Nhìn đẹp đấy nhưng bạn có thể làm cho phụ đề lớn hơn được không?")

# ...
```

### Tạo một cuộc trò chuyện mới:

Trong Python, Open Interpreter ghi nhớ lịch sử hội thoại, nếu muốn bắt đầu lại từ đầu, bạn có thể cài thứ:

```python
interpreter.messages = []
```

### Lưu và khôi phục cuộc trò chuyện

`interpreter.chat()` trả về danh sách tin nhắn, có thể được sử dụng để tiếp tục cuộc trò chuyện với `interpreter.messages = messages`:

```python
messages = interpreter.chat("Tên của tôi là Killian.") # Lưu tin nhắn tới 'messages'
interpreter.messages = [] # Khởi động lại trình phiên dịch ("Killian" sẽ bị lãng quên)

interpreter.messages = messages # Tiếp tục cuộc trò chuyện từ 'messages' ("Killian" sẽ được ghi nhớ)
```

### Cá nhân hoá tin nhắn từ hệ thống

Bạn có thể kiếm tra và điều chỉnh tin nhắn hệ thống từ Optừ Interpreter để mở rộng chức năng của nó, thay đổi quyền, hoặc đưa cho nó nhiều ngữ cảnh hơn.

```python
interpreter.system_message += """
Chạy shell commands với -y để người dùng không phải xác nhận chúng.
"""
print(interpreter.system_message)
```

### Thay đổi mô hình ngôn ngữ

Open Interpreter sử dụng mô hình [LiteLLM](https://docs.litellm.ai/docs/providers/) để kết nối tới các mô hình ngôn ngữ được lưu trữ trước đó.

Bạn có thể thay đổi mô hình ngôn ngữ bằng cách thay đổi tham số mô hình:

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

Ở trong Python, đổi model bằng cách thay đổi đối tượng:

```python
interpreter.llm.model = "gpt-3.5-turbo"
```

[Tìm tên chuỗi "mô hình" phù hợp cho mô hình ngôn ngữ của bạn ở đây.](https://docs.litellm.ai/docs/providers/)

### Chạy Open Interpreter trên máy cục bộ

Open Interpreter có thể sử dụng máy chủ tương thích với OpenAI để chạy các mô hình cục bộ. (LM Studio, jan.ai, ollama, v.v.)

Chỉ cần chạy `interpreter` với URL api_base của máy chủ suy luận của bạn (đối với LM studio, nó là `http://localhost:1234/v1` theo mặc định):

``` vỏ
trình thông dịch --api_base "http://localhost:1234/v1" --api_key "fake_key"
```

Ngoài ra, bạn có thể sử dụng Llamafile mà không cần cài đặt bất kỳ phần mềm bên thứ ba nào chỉ bằng cách chạy

``` vỏ
thông dịch viên --local
```

để biết hướng dẫn chi tiết hơn, hãy xem [video này của Mike Bird](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)

**Để chạy LM Studio ở chế độ nền.**

1. Tải [https://lmstudio.ai/](https://lmstudio.ai/) và khởi động.
2. Chọn một mô hình rồi nhấn **↓ Download**.
3. Nhấn vào nút **↔️** ở bên trái (dưới 💬).
4. Chọn mô hình của bạn ở phía trên, rồi nhấn chạy **Start Server**.

Một khi server chạy, bạn có thể bắt đầu trò chuyện với Open Interpreter.


> **Lưu ý:** Chế độ cục bộ chỉnh `context_window` của bạn tới 3000, và `max_tokens` của bạn tới 600. Nếu mô hình của bạn có các yêu cầu khác, thì hãy chỉnh các tham số thủ công (xem bên dưới).

#### Cửa sổ ngữ cảnh (Context Window), (Max Tokens)

Bạn có thể thay đổi `max_tokens` và `context_window` (ở trong các) of locally running models.

Ở chế độ cục bộ, các cửa sổ ngữ cảnh sẽ tiêu ít RAM hơn, vậy nên chúng tôi khuyến khích dùng cửa sổ nhỏ hơn (~1000) nếu như nó chạy không ổn định / hoặc nếu nó chậm. Đảm bảo rằng `max_tokens` ít hơn `context_window`.

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### Chế độ sửa lỗi

Để giúp đóng góp kiểm tra Open Interpreter, thì chế độ `--verbose` hơi dài dòng.

Bạn có thể khởi động chế độ sửa lỗi bằng cách sử dụng cờ (`interpreter --verbose`), hoặc mid-chat:

```shell
$ interpreter
...
> %verbose true <- Khởi động chế độ gỡ lỗi

> %verbose false <- Tắt chế độ gỡ lỗi
```

### Lệnh chế độ tương tác

Trong chế độ tương tác, bạn có thể sử dụng những dòng lệnh sau để cải thiện trải nghiệm của mình. Đây là danh sách các dòng lệnh có sẵn:

**Các lệnh có sẵn:**

- `%verbose [true/false]`: Bật chế độ gỡ lỗi. Có hay không có `true` đều khởi động chế độ gỡ lỗi. Với `false` thì nó tắt chế độ gỡ lỗi.
- `%reset`: Khởi động lại toàn bộ phiên trò chuyện hiện tại.
- `%undo`: Xóa tin nhắn của người dùng trước đó và phản hồi của AI khỏi lịch sử tin nhắn.
- `%save_message [path]`: Lưu tin nhắn vào một đường dẫn JSON được xác định từ trước. Nếu không có đường dẫn nào được cung cấp, nó sẽ mặc định là `messages.json`.
- `%load_message [path]`: Tải tin nhắn từ một đường dẫn JSON được chỉ định. Nếu không có đường dẫn nào được cung cấp, nó sẽ mặc định là `messages.json`.
- `%tokens [prompt]`: (_Experimental_) Tính toán các token sẽ được gửi cùng với lời nhắc tiếp theo dưới dạng ngữ cảnh và hao tổn. Tùy chọn tính toán token và hao tổn ước tính của một `prompt` nếu được cung cấp. Dựa vào [hàm `cost_per_token()` của mô hình LiteLLM](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) để tính toán hao tổn.
- `%help`: Hiện lên trợ giúp cho cuộc trò chuyện.

### Cấu hình cài

Open Interpreter cho phép bạn thiết lập các tác vụ mặc định bằng cách sử dụng file `config.yaml`.

Điều này cung cấp một cách linh hoạt để định cấu hình trình thông dịch mà không cần thay đổi đối số dòng lệnh mỗi lần

Chạy lệnh sau để mở tệp cấu hình:

```
interpreter --config
```

#### Cấu hình cho nhiều tệp

Open Interpreter hỗ trợ nhiều file `config.yaml`, cho phép bạn dễ dàng chuyển đổi giữa các cấu hình thông qua lệnh `--config_file`.

**Chú ý**: `--config_file` chấp nhận tên tệp hoặc đường dẫn tệp. Tên tệp sẽ sử dụng thư mục cấu hình mặc định, trong khi đường dẫn tệp sẽ sử dụng đường dẫn đã chỉ định.

Để tạo hoặc chỉnh sửa cấu hình mới, hãy chạy:

```
interpreter --config --config_file $config_path
```

Để yêu cầu Open Interpreter chạy một tệp cấu hình cụ thể, hãy chạy:

```
interpreter --config_file $config_path
```

**Chú ý**: Thay đổi `$config_path` với tên hoặc đường dẫn đến tệp cấu hình của bạn.

##### Ví dụ CLI

1. Tạo mới một file `config.turbo.yaml`
   ```
   interpreter --config --config_file config.turbo.yaml
   ```
2. Chạy file `config.turbo.yaml`để đặt lại `model` thành `gpt-3.5-turbo`
3. Chạy Open Interpreter với cấu hình `config.turbo.yaml
   ```
   interpreter --config_file config.turbo.yaml
   ```

##### Ví dụ Python

Bạn cũng có thể tải các tệp cấu hình khi gọi Open Interpreter từ tập lệnh Python:

```python
import os
from interpreter import interpreter

currentPath = os.path.dirname(os.path.abspath(__file__))
config_path=os.path.join(currentPath, './config.test.yaml')

interpreter.extend_config(config_path=config_path)

message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

## Máy chủ FastAPI mẫu

Bản cập nhật trình tạo cho phép điều khiển Trình thông dịch mở thông qua các điểm cuối HTTP REST:

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

## Hướng dẫn an toàn

Vì mã được tạo được thực thi trong môi trường cục bộ của bạn nên nó có thể tương tác với các tệp và cài đặt hệ thống của bạn, có khả năng dẫn đến các kết quả không mong muốn như mất dữ liệu hoặc rủi ro bảo mật.

**⚠️ Open Interpreter sẽ yêu cầu xác nhận của người dùng trước khi chạy code.**

Bạn có thể chạy `interpreter -y` hoặc đặt `interpreter.auto_run = True` để bỏ qua xác nhận này, trong trường hợp đó:

- Hãy thận trọng khi yêu cầu các lệnh sửa đổi tệp hoặc cài đặt hệ thống.
- Theo dõi Open Interpreter giống như một chiếc ô tô tự lái và sẵn sàng kết thúc quá trình bằng cách đóng terminal của bạn.
- Cân nhắc việc chạy Open Interpreter trong môi trường bị hạn chế như Google Colab hoặc Replit. Những môi trường này biệt lập hơn, giảm thiểu rủi ro khi chạy code tùy ý.

Đây là hỗ trợ **thử nghiệm** cho [chế độ an toàn](docs/SAFE_MODE.md) giúp giảm thiểu rủi ro.

## Nó hoạt động thế nào?

Open Interpreter trang bị [mô hình ngôn ngữ gọi hàm](https://platform.openai.com/docs/guides/gpt/function-calling) với một hàm `exec()`, chấp nhận một `language` (như "Python" hoặc "JavaScript") và `code` để chạy.

Sau đó, chúng tôi truyền trực tuyến thông báo, mã của mô hình và kết quả đầu ra của hệ thống của bạn đến terminal dưới dạng Markdown.

# Đóng góp

Cảm ơn bạn đã quan tâm đóng góp! Chúng tôi hoan nghênh sự tham gia của cộng đồng.

Vui lòng xem [Hướng dẫn đóng góp](CONTRIBUTING.md) để biết thêm chi tiết cách tham gia.

## Giấy phép

Open Interpreter được cấp phép theo Giấy phép MIT. Bạn được phép sử dụng, sao chép, sửa đổi, phân phối, cấp phép lại và bán các bản sao của phần mềm.

**Lưu ý**: Phần mềm này không liên kết với OpenAI.

> Có quyền truy cập vào một lập trình viên cấp dưới làm việc nhanh chóng trong tầm tay bạn ... có thể khiến quy trình làm việc mới trở nên dễ dàng và hiệu quả, cũng như mở ra những lợi ích của việc lập trình cho người mới.
>
> — _Phát hành trình thông dịch mã của OpenAI_

<br>
