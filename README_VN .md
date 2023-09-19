<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/>
    </a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="README_IN.md"><img src="https://img.shields.io/badge/Document-Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License"/>
    <br><br>
    <b>Mô hình ngôn ngữ thực thi mã trên máy tính của bạn.</b><br>
    Một dự án mã nguồn mở, chạy cục bộ của Trình biên dịch mã của OpenAI.<br>
    <br><a href="https://openinterpreter.com">Nhận quyền truy cập sớm vào ứng dụng ở đây.</a><br>
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

**Open Interpreter** cho phép LLM chạy mã (Python, Javascript, Shell, v.v.) trong môi trường cục bộ. Bạn có thể trò chuyện với Open Interpreter thông qua giao diện tương tự ChatGPT trong terminal của mình bằng cách chạy `$ open-interpreter` sau khi cài đặt.

Ứng dụng này cung cấp giao diện ngôn ngữ tự nhiên cho các khả năng có mục đích chung của máy tính của bạn:

- Tạo và chỉnh sửa ảnh, video, PDF, v.v.
- Điều khiển trình duyệt Chrome để thực hiện nghiên cứu
- Xử lí, trực quan hóa và phân tích các tập dữ liệu lớn
- ...vân vân và mây mây :P

**⚠️ Lưu ý: Bạn sẽ được yêu cầu phê duyệt mã trước khi thực thi.**

<br>

## Demo

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Bản demo tương tác cũng có sẵn trên Google Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## Hướng dẫn nhanh

```shell
pip install open-interpreter
```

### Terminal

Sau khi cài đặt, chỉ cần chạy `interpreter`:

```shell
interpreter
```

### Với Python

```python
import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # Thực thi lệnh
interpreter.chat() # Bắt đầu hội thoại
```

## So sánh với trình thông dịch mã của ChatGPT

[Trình thông dịch Mã](https://openai.com/blog/chatgpt-plugins#code-interpreter) của OpenAI với GPT-4 đã tạo ra một cơ hội tuyệt vời để giải quyết các tác vụ thực tế với ChatGPT.

Tuy nhiên, dịch vụ của OpenAI là 1 dịch vụ mã nguồn đóng được cung cấp qua internet,  và bị hạn chế khá nhiều:

- Không thể truy cập internet
- [Số lượng gói cài đặt bị giới hạn](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- Dữ liệu tối đa khi tải lên chỉ đạt 100 MB, giới hạn thời gian chạy là 120.0 giây.
- Trạng thái hoạt động sẽ bị xóa (cùng với mọi tệp hoặc liên kết được tạo) khi môi trường tắt đi

---

Open Interpreter vượt qua những hạn chế này bằng cách chạy trên môi trường cục bộ của bạn. Nó có toàn quyền truy cập vào internet, không bị giới hạn bởi thời gian hoặc kích thước tệp và có thể sử dụng bất kỳ gói hoặc thư viện nào.

Điều này kết hợp sức mạnh của GPT-4 với tính linh hoạt của IDE của bạn.

## Câu lệnh

### Trò chuyện

Để bắt đầu 1 cuộc trò chuyện, hãy chạy câu lệnh `interpreter` trên command line:

```shell
interpreter
```

hoặc `interpreter.chat()` từ file .py:

```python
interpreter.chat()
```

### Trò chuyện thông qua lập trình

Để trò chuyện chính xác hơn, bạn có thể truyền tin nhắn vào `.chat(message)`:\

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Xuất ra kết quả ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

### Bắt đầu cuộc trò chuyện mới

Trong Python, Open Interpreter lưu trữ lịch sử cuộc hội thoại của bạn. Sử dụng câu lệnh sau để đặt lại cuộc trò chuyện

```python
interpreter.reset()
```

### Lưu trữ và khôi phục cuộc trò chuyện

`interpreter.chat()` trả về danh sách các tin nhắn khi return_messages = True, lệnh này hỗ trợ người dùng quay trở lại 1 cuộc hội thoại với `interpreter.load(messages)`:

```python
messages = interpreter.chat("My name is Killian.", return_messages=True) # Lưu tin nhắn vào 'messages'
interpreter.reset() # Đặt lại interpreter ("Killian" sẽ bị bỏ đi)

interpreter.load(messages) # Trở về cuộc trò chuyện từ 'messages' ("Killian" sẽ được khôi phục)
```

### Chỉnh sửa tin nhắn hệ thống

Bạn có thể kiểm tra và cấu hình thông báo hệ thống của Open Interpreter để mở rộng chức năng, sửa đổi quyền hoặc cung cấp thêm ngữ cảnh.

```python
interpreter.system_message += """
Chạy các lệnh shell với -y để người dùng không phải xác nhận nhiều lần."""
print(interpreter.system_message)
```

### Thay đổi model

Với `gpt-3.5-turbo`, sử dụng fast mode:

```shell
interpreter --fast
```

Trong Python,  bạn sẽ cần thiết lập mô hình theo cách thủ công:

```python
interpreter.model = "gpt-3.5-turbo"
```

### Chạy Open Interpreter trên môi trường cục bộ

ⓘ**Gặp vấn đề trong việc chạy cục bộ?** Hãy đọc [hướng dẫn thiết lập GPU](./docs/GPU.md) và [hướng dẫn thiết lập trên Windows](./docs/WINDOWS.md).

Hãy chạy `interpreter` ở chế độ cục bộ từ command để sử dụng `Code Llama`:
```shell
interpreter --local
```

hoặc chạy bất cứ model Hugging Face nào **trong môi trường cục bộ** bằng repo ID (vd: "tiiuae/falcon-180B"):

```shell
interpreter --model tiiuae/falcon-180B
```

#### Các tham số của model cục bộ
Bạn có thể dễ dàng sửa đổi `max_tokens` và `context_window` (trong token) của các mô hình đang chạy cục bộ.

Phạm vi ngữ cảnh nhỏ hơn sẽ tốn ít RAM hơn, vì vậy chúng tôi khuyên bạn nên thử phạm vi ngữ cảnh nhỏ hơn nếu GPU bị lỗi.

```shell
interpreter --max_tokens 2000 --context_window 16000
```

### Hỗ trợ Azure

Để kết nối với Azure, `--use-azure` sẽ hướng dẫn bạn thiết lập:

```shell
interpreter --use-azure
```

Trong Python, hãy cài đặt các biến sau:

```
interpreter.use_azure = True
interpreter.api_key = "your_openai_api_key"
interpreter.azure_api_base = "your_azure_api_base"
interpreter.azure_api_version = "your_azure_api_version"
interpreter.azure_deployment_name = "your_azure_deployment_name"
interpreter.azure_api_type = "azure"
```

### Chế độ debug

Để hỗ trợ những người đóng góp kiểm tra Open Interpreter, chế độ `--debug` rất dài dòng.
Bạn có thể kích hoạt chế độ debug bằng cách sử dụng (`interpreter --debug`) hoặc giữa cuộc trò chuyện:

```shell
$ interpreter
...
> %debug true <- Bật chế độ debug

> %debug false <- Tắt chế độ debug
```

### Chế độ tương tác

Trong chế độ tương tác, bạn có thể sử dụng các lệnh bên dưới để nâng cao trải nghiệm sử dụng. Dưới đây là danh sách các lệnh có sẵn:

**Lệnh có sẵn:**  
 • `%debug [true/false]`: Chuyển sang chế độ debug. %debug true kích hoạt chế độ debug, %debug false thoát chế độ debug.
 • `%reset`: Đặt lại phiên hội thoại hiện tại.  
 • `%undo`: Xóa các tin nhắn trước đó và phản hồi của Open Interpreter khỏi lịch sử tin nhắn.  
 • `%save_message [path]`: Lưu tin nhắn vào một đường dẫn JSON được chỉ định. Nếu không có đường dẫn
được cung cấp, đường dẫn sẽ được mặc định là 'messages.json'.
 • `%load_message [path]`: Tải tin nhắn từ một đường dẫn JSON được chỉ định. Nếu không có đường dẫn
được cung cấp, đường dẫn sẽ được mặc định là 'messages.json'.
 • `%help`: Hiển thị tin nhắn hỗ trợ người dùng.

Hãy thoải mái thử những dòng lệnh trên và để lại phản hồi cho chúng mình :3 !

### Cài đặt với .env

Open Interpreter cho phép bạn đặt hành vi mặc định bằng tệp .env, hỗ trợ việc cấu hình Open Interpreter một cách linh hoạt mà không cần thay đổi các đối số dòng lệnh mỗi lần thực thi.

Đây là ví dụ:

```
INTERPRETER_CLI_AUTO_RUN=False
INTERPRETER_CLI_FAST_MODE=False
INTERPRETER_CLI_LOCAL_RUN=False
INTERPRETER_CLI_DEBUG=False
INTERPRETER_CLI_USE_AZURE=False
```
Bạn có thể sửa đổi các giá trị này trong tệp .env để thay đổi hành vi mặc định của Open Interpreter.

## An toàn khi sử dụng

Since generated code is executed in your local environment, it can interact with your files and system settings, potentially leading to unexpected outcomes like data loss or security risks.

Code được tạo ra sẽ thực thi trong môi trường cục bộ của bạn nên nó có thể tương tác với các tệp và cài đặt hệ thống của bạn, điều này có thể dẫn đến kết quả không mong muốn như mất dữ liệu hoặc rủi ro bảo mật.

**⚠️ Open Interpreter sẽ cần sự xác nhận của người dùng trước khi thực thi mã.**

Hãy chạy `interpreter -y` hoặc đặt `interpreter.auto_run = True` để bỏ qua, trong trường hợp đó:

- Hãy thận trọng khi yêu cầu các lệnh sửa đổi tập tin hoặc cài đặt hệ thống.
- Xem Open Interpreter giống như một chiếc xe tự lái và sẵn sàng kết thúc tiến trình bằng cách đóng Terminal.
- Hãy Cân nhắc việc chạy Open Interpreter trong môi trường bị hạn chế như Google Colab hoặc Replit. Những môi trường này biệt lập hơn, giảm thiểu rủi ro liên quan đến việc thực thi mã tùy ý.

## Cơ chế hoạt động?

Open Interpreter trang bị một [mô hình ngôn ngữ gọi hàm](https://platform.openai.com/docs/guides/gpt/function-calling) với hàm `exec()` chấp nhận `ngôn ngữ` (như " Python" hoặc "JavaScript") và `code` để chạy.

Sau đó, chúng tôi truyền các thông báo, mã của mô hình và kết quả xuất ra của hệ thống của bạn tới Terminal dưới dạng Markdown.

# Đóng góp vào dự án

Cảm ơn vì đã quan tâm đóng góp! Chúng tôi hoan nghênh sự tham gia của bạn.

Xem hướng dẫn đóng góp tại [đây](./CONTRIBUTING.md) để biết thêm chi tiết về cách tham gia.

## Giấy phép
Open Interpreter được cấp phép theo Giấy phép MIT. Bạn được phép sử dụng, sao chép, sửa đổi, phân phối, cấp phép lại và bán các bản sao của phần mềm

**Lưu ý**: Phần mềm này không liên kết với OpenAI.

> Được tiếp cận với một Junior năng suất trong tầm tay bạn ... có thể khiến quy trình công việc mới trở nên dễ dàng và hiệu quả, đồng thời lan tỏa những lợi ích của lập trình cho mọi người.
>
> — _Bản phát hành trình thông dịch mã của OpenAI_

<br>


