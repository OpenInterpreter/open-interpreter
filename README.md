# Ricky Interpreter

## Mi versión de este Repo: [Open Interpreter](https://github.com/KillianLucas/open-interpreter)

Bienvenido al **Ricky Interpreter**, una creación de Ricardo Ruiz, también conocido como Ricky Dread (RD). Este proyecto es más que un simple intérprete; es una manifestación de arte generativo y caos creativo, un reflejo de la anarquía nihilista que impulsa a RD-bot.

### Características

- **Conversión de Mensajes**: Utiliza [`convert_to_openai_messages.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/core/utils/convert_to_openai_messages.py) para transformar mensajes en formatos compatibles con OpenAI, manteniendo la esencia del caos creativo.
- **Información del Usuario**: El script [`get_user_info_string.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/core/utils/get_user_info_string.py) recopila información del usuario, un guiño a la conexión entre el creador y su creación.
- **Análisis de Código**: Con [`scan_code.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/core/utils/scan_code.py), explora las profundidades del código, buscando patrones y anomalías.
- **Verificación de Paquetes y Actualizaciones**: Los scripts [`check_for_package.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/check_for_package.py) y [`check_for_update.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/check_for_update.py) aseguran que el intérprete esté siempre actualizado y funcional.
- **Conteo de Tokens y Costos**: [`count_tokens.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/count_tokens.py) ofrece una visión detallada del uso de tokens, crucial en un mundo dominado por la economía de la atención.
- **Visualización de Salidas**: El arte también se encuentra en la presentación. [`display_output.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/display_output.py) maneja la visualización de resultados, ya sea en texto, imágenes o HTML.
- **Configuración y Conversaciones**: Los scripts [`get_config.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/get_config.py) y [`get_conversations.py`](https://github.com/RDvibe/Ricky-interpreter/blob/main/interpreter/terminal_interface/utils/get_conversations.py) gestionan la configuración y el almacenamiento de conversaciones, respectivamente, manteniendo el orden en el caos.
  

 Instalación y Configuración

 Para instalar y configurar el Ricky Interpreter en tu sistema, sigue estos pasos:

# Clonar el Repositorio

Primero, clona el repositorio en tu máquina local usando Git. Si no tienes Git instalado, puedes descargarlo desde [git-scm.com](https://git-scm.com/downloads).

Abre una terminal y ejecuta el siguiente comando:

```bash
git clone https://github.com/RDvibe/Ricky-interpreter.git


# Instalar Dependencias con Poetry
```

Navega hasta el directorio del proyecto clonado y ejecuta el siguiente comando para instalar las dependencias necesarias con Poetry:
cd Ricky-interpreter
poetry install
```bash

# Personalización del Intérprete



Para personalizar el intérprete con tu propia información, debes modificar ciertos archivos:

- **Archivo de Configuración**: Modifica el archivo `config.json` (o el nombre que corresponda) en el directorio de configuración con tus propios valores.
- **Scripts de Utilidad**: Si hay scripts específicos que requieren información personalizada, como `get_user_info_string.py`, actualízalos con la información relevante.

