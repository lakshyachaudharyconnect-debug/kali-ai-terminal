# Kali AI Terminal
## Introduction
Kali AI Terminal is an AI-powered terminal for Kali Linux with a two-pane UI.

### Badges
[![Open Source](https://img.shields.io/badge/Open%20Source-Yes-green)](https://github.com/offensive-security/kali-linux-ai-terminal)
[![Built With Python](https://img.shields.io/badge/Built%20With-Python-blue)](https://www.python.org/)
[![Kali Linux](https://img.shields.io/badge/OS-Kali%20Linux-red)](https://www.kali.org/)

## Features
* Two-pane UI: left pane for direct bash commands, right pane for AI chat
* AI planning and execution of commands using Groq API with LLaMA 3.3 70B model
* Safety filter to block dangerous commands
* Auto-fixing of errors
* Built with Python and Textual library

## Installation
1. Clone the repository: git clone https://github.com/offensive-security/kali-linux-ai-terminal.git
2. Create a virtual environment: python3 -m venv venv
3. Activate the virtual environment: source venv/bin/activate
4. Install requirements: pip install -r requirements.txt
5. Set GROQ_API_KEY environment variable: export GROQ_API_KEY=your-api-key

## Usage
1. Run the application: python app.py
2. Type bash commands in the left pane or tell the AI your goal in the right pane

## Note
This is an open-source project built by a college freshman. Contributions are welcome!
