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

Bitte sieh dir unsere [Richtlinien für Mitwirkende](docs/CONTRIBUTING.md) für weitere Details an, wie du dich einbringen kannst.

## Lizenz

Open Interpreter ist unter der MIT-Lizenz lizenziert. Du darfst die Software verwenden, kopieren, modifizieren, verteilen, unterlizenzieren und Kopien der Software verkaufen.

**Hinweis**: Diese Software ist nicht mit OpenAI affiliiert.

> Zugriff auf einen Junior-Programmierer zu haben, der mit der Geschwindigkeit deiner Fingerspitzen arbeitet ... kann neue Arbeitsabläufe mühelos und effizient machen sowie das Programmieren einem neuen Publikum öffnen.
>
> — _OpenAIs Code Interpreter Release_

<br>
