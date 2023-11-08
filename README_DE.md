<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white">
    </a>
    <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"></a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
    <br><br>
    <b>Lassen Sie Sprachmodelle Code auf Ihrem Computer ausführen.</b><br>
    Eine Open-Source, lokal laufende Implementierung von OpenAIs Code-Interpreter.<br>
    <br><a href="https://openinterpreter.com">Erhalten Sie frühen Zugang zur Desktop-Anwendung.</a><br>
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

**Open Interpreter** ermöglicht es LLMs (Language Models), Code (Python, Javascript, Shell und mehr) lokal auszuführen. Sie können mit Open Interpreter über eine ChatGPT-ähnliche Schnittstelle in Ihrem Terminal chatten, indem Sie $ interpreter nach der Installation ausführen.

Dies bietet eine natürliche Sprachschnittstelle zu den allgemeinen Fähigkeiten Ihres Computers:

- Erstellen und bearbeiten Sie Fotos, Videos, PDFs usw.
- Steuern Sie einen Chrome-Browser, um Forschungen durchzuführen
- Darstellen, bereinigen und analysieren Sie große Datensätze
- ...usw.

**⚠️ Hinweis: Sie werden aufgefordert, Code zu genehmigen, bevor er ausgeführt wird.**

<br>

## Demo

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Eine interaktive Demo ist auch auf Google Colab verfügbar:

[![In Colab öffnen](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## Schnellstart

```shell
pip install open-interpreter
```

### Terminal

Nach der Installation führen Sie einfach `interpreter` aus:

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("Stellen Sie AAPL und METAs normalisierte Aktienpreise dar") # Führt einen einzelnen Befehl aus
interpreter.chat() # Startet einen interaktiven Chat
```

## Vergleich zu ChatGPTs Code Interpreter

OpenAIs Veröffentlichung des [Code Interpreters](https://openai.com/blog/chatgpt-plugins#code-interpreter) mit GPT-4 bietet eine fantastische Möglichkeit, reale Aufgaben mit ChatGPT zu erledigen.

Allerdings ist OpenAIs Dienst gehostet, Closed-Source und stark eingeschränkt:
- Kein Internetzugang.
- [Begrenzte Anzahl vorinstallierter Pakete](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- 100 MB maximale Uploadgröße, 120.0 Sekunden Laufzeitlimit.
- Der Zustand wird gelöscht (zusammen mit allen generierten Dateien oder Links), wenn die Umgebung abstirbt.

---

Open Interpreter überwindet diese Einschränkungen, indem es in Ihrer lokalen Umgebung läuft. Es hat vollen Zugang zum Internet, ist nicht durch Zeit oder Dateigröße eingeschränkt und kann jedes Paket oder jede Bibliothek nutzen.

Dies kombiniert die Kraft von GPT-4s Code Interpreter mit der Flexibilität Ihrer lokalen Maschine.

## Befehle

**Update:** Das Generator-Update (0.1.5) hat das Streaming eingeführt:

```python
nachricht = "Unter welchem Betriebssystem sind wir?"

for chunk in interpreter.chat(nachricht, display=False, stream=True):
  print(chunk)
```

### Interaktiver Chat

Um einen interaktiven Chat in deinem Terminal zu starten, führe entweder `interpreter` von der Kommandozeile aus:

```shell
interpreter
```

Oder `interpreter.chat()` aus einer .py-Datei:

```python
interpreter.chat()
```

**Du kannst auch jeden Abschnitt streamen:**

```python
nachricht = "Unter welchem Betriebssystem sind wir?"

for chunk in interpreter.chat(nachricht, display=False, stream=True):
  print(chunk)
```

### Programmatischer Chat

Für eine genauere Steuerung kannst du Nachrichten direkt an `.chat(nachricht)` senden:

```python
interpreter.chat("Füge Untertitel zu allen Videos in /videos hinzu.")

# ... Streamt die Ausgabe in dein Terminal, führt die Aufgabe aus ...

interpreter.chat("Die sehen toll aus, aber kannst du die Untertitel größer machen?")

# ...
```

### Starte einen neuen Chat

In Python merkt sich Open Interpreter den Gesprächsverlauf. Wenn du von vorne beginnen möchtest, kannst du ihn zurücksetzen:

```python
interpreter.reset()
```

### Speichern und Wiederherstellen von Chats

`interpreter.chat()` gibt eine Liste von Nachrichten zurück, die verwendet werden kann, um ein Gespräch mit `interpreter.messages = nachrichten` fortzusetzen:

```python
nachrichten = interpreter.chat("Mein Name ist Killian.") # Speichere Nachrichten in 'nachrichten'
interpreter.reset() # Setze den Interpreter zurück ("Killian" wird vergessen)

interpreter.messages = nachrichten # Setze den Chat von 'nachrichten' fort ("Killian" wird erinnert)
```

### Anpassen der Systemnachricht

Du kannst die Systemnachricht von Open Interpreter überprüfen und konfigurieren, um die Funktionalität zu erweitern, Berechtigungen zu ändern oder ihm mehr Kontext zu geben.

```python
interpreter.system_message += """
Führe Shell-Befehle mit -y aus, damit der Benutzer sie nicht bestätigen muss.
"""
print(interpreter.system_message)
```

### Ändere dein Sprachmodell

Open Interpreter verwendet [LiteLLM](https://docs.litellm.ai/docs/providers/) um eine Verbindung zu gehosteten Sprachmodellen herzustellen.

Du kannst das Modell ändern, indem du den Modell-Parameter einstellst:

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

In Python, setze das Modell auf dem Objekt:

```python
interpreter.model = "gpt-3.5-turbo"
```

[Finde hier die passende "Modell"-Zeichenkette für dein Sprachmodell.](https://docs.litellm.ai/docs/providers/)

### Open Interpreter lokal ausführen

Open Interpreter verwendet [LM Studio](https://lmstudio.ai/) um eine Verbindung zu lokalen Sprachmodellen herzustellen (experimentell).

Führe einfach `interpreter` im lokalen Modus von der Kommandozeile aus:

```shell
interpreter --local
```

**Du musst LM Studio im Hintergrund laufen haben.**

1. Lade [https://lmstudio.ai/](https://lmstudio.ai/) herunter und starte es.
2. Wähle ein Modell aus und klicke auf **↓ Download**.
3. Klicke auf den **↔️**-Button links (unter 💬).
4. Wähle dein Modell oben aus und klicke auf **Start Server**.

Sobald der Server läuft, kannst du deine Unterhaltung mit Open Interpreter beginnen.

(Wenn du den Befehl `interpreter --local` ausführst, werden die oben genannten Schritte angezeigt.)

> **Hinweis:** Der lokale Modus setzt dein `context_window` auf 3000 und deine `max_tokens` auf 1000. Wenn dein Modell andere Anforderungen hat, stelle diese Parameter manuell ein (siehe unten).

#### Kontextfenster, Maximale Tokens

Du kannst die `max_tokens` und das `context_window` (in Token) von lokal laufenden Modellen ändern.

Für den lokalen Modus wird ein kleineres Kontextfenster weniger RAM verwenden, daher empfehlen wir, ein viel kürzeres Fenster (~1000) zu probieren, wenn es fehlschlägt oder wenn es langsam ist. Stelle sicher, dass `max_tokens` kleiner als `context_window` ist.

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```


### Debug-Modus

Um Mitwirkenden die Überprüfung von Open Interpreter zu erleichtern, ist der `--debug` Modus sehr ausführlich.

Du kannst den Debug-Modus aktivieren, indem du den entsprechenden Flag verwendest (`interpreter --debug`), oder mitten im Chat:

```shell
$ interpreter
...
> %debug true <- Aktiviert den Debug-Modus

> %debug false <- Deaktiviert den Debug-Modus
```

### Befehle im Interaktiven Modus

Im interaktiven Modus kannst du die untenstehenden Befehle nutzen, um deine Erfahrung zu verbessern. Hier ist eine Liste der verfügbaren Befehle:

**Verfügbare Befehle:**

- `%debug [true/false]`: Schaltet den Debug-Modus um. Ohne Argumente oder mit `true` 
  wird in den Debug-Modus gewechselt. Mit `false` wird der Debug-Modus beendet.
- `%reset`: Setzt das aktuelle Gespräch der Sitzung zurück.
- `%undo`: Entfernt die vorherige Nutzernachricht und die Antwort der KI aus dem Nachrichtenverlauf.
- `%save_message [Pfad]`: Speichert Nachrichten in einem spezifizierten JSON-Pfad. Wenn kein Pfad angegeben wird, wird standardmäßig `messages.json` verwendet.
- `%load_message [Pfad]`: Lädt Nachrichten von einem spezifizierten JSON-Pfad. Wenn kein Pfad angegeben wird, wird standardmäßig `messages.json` verwendet.
- `%tokens [Eingabeaufforderung]`: (_Experimentell_) Berechnet die Tokens, die mit der nächsten Eingabeaufforderung als Kontext gesendet werden und schätzt deren Kosten. Optional werden die Tokens und die geschätzten Kosten einer `Eingabeaufforderung` berechnet, falls eine angegeben wird. Verlässt sich auf [LiteLLMs `cost_per_token()` Methode](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) für geschätzte Kosten.
- `%help`: Zeigt die Hilfe-Nachricht an.

### Konfiguration

Open Interpreter ermöglicht es dir, Standardverhaltensweisen mit einer `config.yaml`-Datei festzulegen.

Dies bietet eine flexible Möglichkeit, den Interpreter zu konfigurieren, ohne jedes Mal die Kommandozeilenargumente zu ändern.

Führe den folgenden Befehl aus, um die Konfigurationsdatei zu öffnen:

```
interpreter --config
```

#### Mehrere Konfigurationsdateien

Open Interpreter unterstützt mehrere `config.yaml`-Dateien, was es dir ermöglicht, einfach zwischen Konfigurationen zu wechseln über das `--config_file` Argument.

**Hinweis**: `--config_file` akzeptiert entweder einen Dateinamen oder einen Dateipfad. Dateinamen verwenden das Standardkonfigurationsverzeichnis, während Dateipfade den angegebenen Pfad verwenden.

Um eine neue Konfiguration zu erstellen oder zu bearbeiten, führe aus:

```
interpreter --config --config_file $config_path
```

Um Open Interpreter zu veranlassen, eine spezifische Konfigurationsdatei zu laden, führe aus:

```
interpreter --config_file $config_path
```

**Hinweis**: Ersetze `$config_path` durch den Namen oder Pfad deiner Konfigurationsdatei.

##### CLI-Beispiel

1. Erstelle eine neue `config.turbo.yaml`-Datei
   ```
   interpreter --config --config_file config.turbo.yaml
   ```
2. Bearbeite die `config.turbo.yaml`-Datei, um `model` auf `gpt-3.5-turbo` zu setzen
3. Führe Open Interpreter mit der `config.turbo.yaml`-Konfiguration aus
   ```
   interpreter --config_file config.turbo.yaml
   ```

##### Python-Beispiel

Du kannst auch Konfigurationsdateien laden, wenn du Open Interpreter aus Python-Skripten aufrufst:

```python
import os
import interpreter

currentPath = os.path.dirname(os.path.abspath(__file__))
config_path=os.path.join(currentPath, './config.test.yaml')

interpreter.extend_config(config_path=config_path)

message = "Unter welchem Betriebssystem sind wir?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

## Beispiel FastAPI-Server

Das Generator-Update ermöglicht es, Open Interpreter über HTTP REST-Endpunkte zu steuern:

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
            yield f"data: {result}nn"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return interpreter.messages
```

```shell
pip install fastapi uvicorn
uvicorn server:app --reload
```

## Sicherheitshinweis

Da generierter Code in deiner lokalen Umgebung ausgeführt wird, kann er mit deinen Dateien und Systemeinstellungen interagieren, was potenziell zu unerwarteten Ergebnissen wie Datenverlust oder Sicherheitsrisiken führen kann.

**⚠️ Open Interpreter wird um Nutzerbestätigung bitten, bevor Code ausgeführt wird.**

Du kannst `interpreter -y` ausführen oder `interpreter.auto_run = True` setzen, um diese Bestätigung zu umgehen, in diesem Fall:

- Sei vorsichtig bei Befehlsanfragen, die Dateien oder Systemeinstellungen ändern.
- Beobachte Open Interpreter wie ein selbstfahrendes Auto und sei bereit, den Prozess zu beenden, indem du dein Terminal schließt.
- Betrachte die Ausführung von Open Interpreter in einer eingeschränkten Umgebung wie Google Colab oder Replit. Diese Umgebungen sind isolierter und reduzieren das Risiko der Ausführung willkürlichen Codes.

Es gibt **experimentelle** Unterstützung für einen [Sicherheitsmodus](docs/SAFE_MODE.md), um einige Risiken zu mindern.

## Wie funktioniert es?

Open Interpreter rüstet ein [funktionsaufrufendes Sprachmodell](https://platform.openai.com/docs/guides/gpt/function-calling) mit einer `exec()`-Funktion aus, die eine `language` (wie "Python" oder "JavaScript") und auszuführenden `code` akzeptiert.

Wir streamen dann die Nachrichten des Modells, Code und die Ausgaben deines Systems zum Terminal als Markdown.

# Mitwirken

Danke für dein Interesse an der Mitarbeit! Wir begrüßen die Beteiligung der Gemeinschaft.

Bitte sieh dir unsere [Richtlinien für Mitwirkende](CONTRIBUTING.md) für weitere Details an, wie du dich einbringen kannst.

## Lizenz

Open Interpreter ist unter der MIT-Lizenz lizenziert. Du darfst die Software verwenden, kopieren, modifizieren, verteilen, unterlizenzieren und Kopien der Software verkaufen.

**Hinweis**: Diese Software ist nicht mit OpenAI affiliiert.

> Zugriff auf einen Junior-Programmierer zu haben, der mit der Geschwindigkeit deiner Fingerspitzen arbeitet ... kann neue Arbeitsabläufe mühelos und effizient machen sowie das Programmieren einem neuen Publikum öffnen.
>
> — _OpenAIs Code Interpreter Release_

<br>


