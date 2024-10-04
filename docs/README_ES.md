<h1 align="center">● Intérprete Abierto</h1>

<p align="center">
    <a href="https://discord.gg/Hvz9Axh84z">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/></a>
    <a href="../README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="README_ZH.md"> <img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="README_UK.md"><img src="https://img.shields.io/badge/Українська-white.svg" alt="UK doc"/></a>
    <a href="README_IN.md"> <img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <a href="../LICENSE"><img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/></a>
    <br>
    <br>
    <br><a href="https://0ggfznkwh4j.typeform.com/to/G21i9lJ2">Obtenga acceso temprano a la aplicación de escritorio</a>‎ ‎ |‎ ‎ <a href="https://docs.openinterpreter.com/">Documentación</a><br>
</p>

<br>

![poster](https://github.com/OpenInterpreter/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br>
<p align="center">
<strong>La Nueva Actualización del Computador</strong> presenta <strong><code>--os</code></strong> y una nueva <strong>API de Computadora</strong>. <a href="https://changes.openinterpreter.com/log/the-new-computer-update">Lea más →</a>
</p>
<br>

```shell
pip install open-interpreter
```

> ¿No funciona? Lea nuestra [guía de configuración](https://docs.openinterpreter.com/getting-started/setup).

```shell
interpreter
```

<br>

**Intérprete Abierto** permite a los LLMs ejecutar código (Python, JavaScript, Shell, etc.) localmente. Puede chatear con Intérprete Abierto a través de una interfaz de chat como ChatGPT en su terminal después de instalar.

Esto proporciona una interfaz de lenguaje natural para las capacidades generales de su computadora:

- Crear y editar fotos, videos, PDF, etc.
- Controlar un navegador de Chrome para realizar investigaciones
- Graficar, limpiar y analizar conjuntos de datos grandes
- ... etc.

**⚠️ Nota: Se le pedirá que apruebe el código antes de ejecutarlo.**

<br>

## Demo

https://github.com/OpenInterpreter/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### También hay disponible una demo interactiva en Google Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### Además, hay un ejemplo de interfaz de voz inspirada en _Her_:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## Inicio Rápido

```shell
pip install open-interpreter
```

### Terminal

Después de la instalación, simplemente ejecute `interpreter`:

```shell
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # Ejecuta un comando sencillo
interpreter.chat() # Inicia una sesión de chat interactiva
```

### GitHub Codespaces

Presione la tecla `,` en la página de GitHub de este repositorio para crear un espacio de códigos. Después de un momento, recibirá un entorno de máquina virtual en la nube con Interprete Abierto pre-instalado. Puede entonces empezar a interactuar con él directamente y confirmar su ejecución de comandos del sistema sin preocuparse por dañar el sistema.

## Comparación con el Intérprete de Código de ChatGPT

El lanzamiento de [Intérprete de Código](https://openai.com/blog/chatgpt-plugins#code-interpreter) de OpenAI con GPT-4 presenta una oportunidad fantástica para realizar tareas del mundo real con ChatGPT.

Sin embargo, el servicio de OpenAI está alojado, su codigo es cerrado y está fuertemente restringido:

- No hay acceso a Internet.
- [Conjunto limitado de paquetes preinstalados](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- Límite de 100 MB de carga, límite de tiempo de 120.0 segundos.
- El estado se elimina (junto con cualquier archivo generado o enlace) cuando el entorno se cierra.

---

Intérprete Abierto supera estas limitaciones al ejecutarse en su entorno local. Tiene acceso completo a Internet, no está restringido por tiempo o tamaño de archivo y puede utilizar cualquier paquete o libreria.

Esto combina el poder del Intérprete de Código de GPT-4 con la flexibilidad de su entorno de desarrollo local.

## Comandos

**Actualización:** La Actualización del Generador (0.1.5) introdujo streaming:

```python
message = "¿Qué sistema operativo estamos utilizando?"

for chunk in interpreter.chat(message, display=False, stream=True):
    print(chunk)
```

### Chat Interactivo

Para iniciar una sesión de chat interactiva en su terminal, puede ejecutar `interpreter` desde la línea de comandos:

```shell
interpreter
```

O `interpreter.chat()` desde un archivo `.py`:

```python
interpreter.chat()
```

**Puede también transmitir cada trozo:**

```python
message = "¿Qué sistema operativo estamos utilizando?"

for chunk in interpreter.chat(message, display=False, stream=True):
    print(chunk)
```

### Chat Programático

Para un control más preciso, puede pasar mensajes directamente a `.chat(message)`:

```python
interpreter.chat("Añade subtítulos a todos los videos en /videos.")

# ... Transmite salida a su terminal, completa tarea ...

interpreter.chat("Estos se ven bien, pero ¿pueden hacer los subtítulos más grandes?")

# ...
```

### Iniciar un nuevo chat

En Python, Intérprete Abierto recuerda el historial de conversación. Si desea empezar de nuevo, puede resetearlo:

```python
interpreter.messages = []
```

### Guardar y Restaurar Chats

`interpreter.chat()` devuelve una lista de mensajes, que puede utilizar para reanudar una conversación con `interpreter.messages = messages`:

```python
messages = interpreter.chat("Mi nombre es Killian.") # Guarda mensajes en 'messages'
interpreter.messages = [] # Resetear Intérprete ("Killian" será olvidado)

interpreter.messages = messages # Reanuda chat desde 'messages' ("Killian" será recordado)
```

### Personalizar el Mensaje del Sistema

Puede inspeccionar y configurar el mensaje del sistema de Intérprete Abierto para extender su funcionalidad, modificar permisos o darle más contexto.

```python
interpreter.system_message += """
Ejecute comandos de shell con -y para que el usuario no tenga que confirmarlos.
"""
print(interpreter.system_message)
```

### Cambiar el Modelo de Lenguaje

Intérprete Abierto utiliza [LiteLLM](https://docs.litellm.ai/docs/providers/) para conectarse a modelos de lenguaje hospedados.

Puede cambiar el modelo estableciendo el parámetro de modelo:

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

En Python, establezca el modelo en el objeto:

```python
interpreter.llm.model = "gpt-3.5-turbo"
```

[Encuentre la cadena adecuada para su modelo de lenguaje aquí.](https://docs.litellm.ai/docs/providers/)

### Ejecutar Intérprete Abierto localmente

#### Terminal

Intérprete Abierto puede utilizar un servidor de OpenAI compatible para ejecutar modelos localmente. (LM Studio, jan.ai, ollama, etc.)

Simplemente ejecute `interpreter` con la URL de base de API de su servidor de inferencia (por defecto, `http://localhost:1234/v1` para LM Studio):

```shell
interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"
```

O puede utilizar Llamafile sin instalar software adicional simplemente ejecutando:

```shell
interpreter --local
```

Para una guía mas detallada, consulte [este video de Mike Bird](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)

**Cómo ejecutar LM Studio en segundo plano.**

1. Descargue [https://lmstudio.ai/](https://lmstudio.ai/) luego ejecutelo.
2. Seleccione un modelo, luego haga clic **↓ Descargar**.
3. Haga clic en el botón **↔️** en la izquierda (debajo de 💬).
4. Seleccione su modelo en la parte superior, luego haga clic **Iniciar Servidor**.

Una vez que el servidor esté funcionando, puede empezar su conversación con Intérprete Abierto.

> **Nota:** El modo local establece su `context_window` en 3000 y su `max_tokens` en 1000. Si su modelo tiene requisitos diferentes, ajuste estos parámetros manualmente (ver a continuación).

#### Python

Nuestro paquete de Python le da más control sobre cada ajuste. Para replicar y conectarse a LM Studio, utilice estos ajustes:

```python
from interpreter import interpreter

interpreter.offline = True # Desactiva las características en línea como Procedimientos Abiertos
interpreter.llm.model = "openai/x" # Indica a OI que envíe mensajes en el formato de OpenAI
interpreter.llm.api_key = "fake_key" # LiteLLM, que utilizamos para hablar con LM Studio, requiere esto
interpreter.llm.api_base = "http://localhost:1234/v1" # Apunta esto a cualquier servidor compatible con OpenAI

interpreter.chat()
```

#### Ventana de Contexto, Tokens Máximos

Puede modificar los `max_tokens` y `context_window` (en tokens) de los modelos locales.

Para el modo local, ventanas de contexto más cortas utilizarán menos RAM, así que recomendamos intentar una ventana mucho más corta (~1000) si falla o si es lenta. Asegúrese de que `max_tokens` sea menor que `context_window`.

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### Modo Detallado

Para ayudarle a inspeccionar Intérprete Abierto, tenemos un modo `--verbose` para depuración.

Puede activar el modo detallado utilizando el parámetro (`interpreter --verbose`), o en plena sesión:

```shell
$ interpreter
...
> %verbose true <- Activa el modo detallado

> %verbose false <- Desactiva el modo verbose
```

### Comandos de Modo Interactivo

En el modo interactivo, puede utilizar los siguientes comandos para mejorar su experiencia. Aquí hay una lista de comandos disponibles:

**Comandos Disponibles:**

- `%verbose [true/false]`: Activa o desactiva el modo detallado. Sin parámetros o con `true` entra en modo detallado.
  Con `false` sale del modo verbose.
- `%reset`: Reinicia la sesión actual de conversación.
- `%undo`: Elimina el mensaje de usuario previo y la respuesta del AI del historial de mensajes.
- `%tokens [prompt]`: (_Experimental_) Calcula los tokens que se enviarán con el próximo prompt como contexto y estima su costo. Opcionalmente, calcule los tokens y el costo estimado de un `prompt` si se proporciona. Depende de [LiteLLM's `cost_per_token()` method](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) para costos estimados.
- `%help`: Muestra el mensaje de ayuda.

### Configuración / Perfiles

Intérprete Abierto permite establecer comportamientos predeterminados utilizando archivos `yaml`.

Esto proporciona una forma flexible de configurar el intérprete sin cambiar los argumentos de línea de comandos cada vez.

Ejecutar el siguiente comando para abrir el directorio de perfiles:

```
interpreter --profiles
```

Puede agregar archivos `yaml` allí. El perfil predeterminado se llama `default.yaml`.

#### Perfiles Múltiples

Intérprete Abierto admite múltiples archivos `yaml`, lo que permite cambiar fácilmente entre configuraciones:

```
interpreter --profile my_profile.yaml
```

## Servidor de FastAPI de ejemplo

El generador actualiza permite controlar Intérprete Abierto a través de puntos de conexión HTTP REST:

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

Puede iniciar un servidor idéntico al anterior simplemente ejecutando `interpreter.server()`.

## Android

La guía paso a paso para instalar Intérprete Abierto en su dispositivo Android se encuentra en el [repo de open-interpreter-termux](https://github.com/MikeBirdTech/open-interpreter-termux).

## Aviso de Seguridad

Ya que el código generado se ejecuta en su entorno local, puede interactuar con sus archivos y configuraciones del sistema, lo que puede llevar a resultados inesperados como pérdida de datos o riesgos de seguridad.

**⚠️ Intérprete Abierto le pedirá que apruebe el código antes de ejecutarlo.**

Puede ejecutar `interpreter -y` o establecer `interpreter.auto_run = True` para evitar esta confirmación, en cuyo caso:

- Sea cuidadoso al solicitar comandos que modifican archivos o configuraciones del sistema.
- Vigile Intérprete Abierto como si fuera un coche autónomo y esté preparado para terminar el proceso cerrando su terminal.
- Considere ejecutar Intérprete Abierto en un entorno restringido como Google Colab o Replit. Estos entornos son más aislados, reduciendo los riesgos de ejecutar código arbitrario.

Hay soporte **experimental** para un [modo seguro](docs/SAFE_MODE.md) para ayudar a mitigar algunos riesgos.

## ¿Cómo Funciona?

Intérprete Abierto equipa un [modelo de lenguaje de llamada a funciones](https://platform.openai.com/docs/guides/gpt/function-calling) con una función `exec()`, que acepta un `lenguaje` (como "Python" o "JavaScript") y `código` para ejecutar.

Luego, transmite los mensajes del modelo, el código y las salidas del sistema a la terminal como Markdown.

# Acceso a la Documentación Offline

La documentación completa está disponible en línea sin necesidad de conexión a Internet.

[Node](https://nodejs.org/en) es un requisito previo:

- Versión 18.17.0 o cualquier versión posterior 18.x.x.
- Versión 20.3.0 o cualquier versión posterior 20.x.x.
- Cualquier versión a partir de 21.0.0 sin límite superior especificado.

Instale [Mintlify](https://mintlify.com/):

```bash
npm i -g mintlify@latest
```

Cambia a la carpeta de documentos y ejecuta el comando apropiado:

```bash
# Suponiendo que estás en la carpeta raíz del proyecto
cd ./docs

# Ejecute el servidor de documentación
mintlify dev
```

Una nueva ventana del navegador debería abrirse. La documentación estará disponible en [http://localhost:3000](http://localhost:3000) mientras el servidor de documentación esté funcionando.

# Contribuyendo

¡Gracias por su interés en contribuir! Damos la bienvenida a la implicación de la comunidad.

Por favor, consulte nuestras [directrices de contribución](docs/CONTRIBUTING.md) para obtener más detalles sobre cómo involucrarse.

# Roadmap

Visite [nuestro roadmap](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/ROADMAP.md) para ver el futuro de Intérprete Abierto.

**Nota:** Este software no está afiliado con OpenAI.

![thumbnail-ncu](https://github.com/OpenInterpreter/open-interpreter/assets/63927363/1b19a5db-b486-41fd-a7a1-fe2028031686)

> Tener acceso a un programador junior trabajando a la velocidad de su dedos... puede hacer que los nuevos flujos de trabajo sean sencillos y eficientes, además de abrir los beneficios de la programación a nuevas audiencias.
>
> — _Lanzamiento del intérprete de código de OpenAI_

<br>
