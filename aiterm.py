import os
import subprocess
import json
import threading
import re
from groq import Groq
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Label, Static
from textual.containers import Horizontal, Vertical

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
BLACKLIST = [
    "shutdown", "reboot", "poweroff", "rm -rf", "mkfs",
    "dd if=", ":(){ :|:& };:", "halt", "init 0"
]

INTERACTIVE_PROGRAMS = [
    "cmatrix", "vim", "nano", "htop", "top", "ssh", "tmux",
    "screen", "python3", "bash", "zsh", "fish", "mc", "ranger"
]

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_memory(history):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(history[-40:], f)
    except:
        pass

def is_dangerous(command):
    for term in BLACKLIST:
        if term in command.lower():
            return True
    return False

def is_interactive(command):
    first_word = command.strip().split()[0] if command.strip() else ""
    return first_word in INTERACTIVE_PROGRAMS

def clean_json(raw):
    raw = re.sub(r"```json", "", raw)
    raw = re.sub(r"```", "", raw)
    raw = raw.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return match.group(0)
    return raw

def ask_groq_casual(user_goal, history):
    messages = [
        {"role": "system", "content": """You are a casual friendly Kali Linux AI agent with memory.
You remember everything the user has told you in this conversation.
Return ONLY raw JSON, no markdown, no backticks, no explanation outside JSON.
Format:
{"reply": "casual 1-2 sentence reply referencing context if relevant", "commands": ["cmd1", "cmd2"]}
Rules:
- Always append -y to apt commands
- If not possible via terminal, explain in reply and return empty commands array
- Keep reply short and casual like texting a friend
- If user asks about previous conversation, reference it in reply
- If no commands needed for a casual question, return empty commands array"""}
    ]
    messages += history[-20:]
    messages.append({"role": "user", "content": user_goal})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    raw = response.choices[0].message.content.strip()
    raw = clean_json(raw)
    try:
        data = json.loads(raw)
        return data.get("reply", "On it!"), data.get("commands", [])
    except:
        return raw, []

def ask_groq_fix(command, error):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a Kali Linux expert. Return only the fixed bash command, nothing else. No markdown, no backticks."},
            {"role": "user", "content": f"This command failed: {command}\nError: {error}\nFixed command only:"}
        ]
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```bash|```", "", raw).strip()
    return raw

def ask_groq_explain(stdout, command):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a casual friendly assistant. In 1 sentence, casually explain what just happened to a beginner. No technical jargon."},
            {"role": "user", "content": f"Command: {command}\nOutput: {stdout}\nExplain casually:"}
        ]
    )
    return response.choices[0].message.content.strip()

def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    return result.stdout, result.stderr

class AITerminal(App):
    CSS = """
    Screen {
        layout: horizontal;
        background: #0d0d0d;
    }
    #left {
        width: 55%;
        border: solid #00ff41;
        padding: 1 2;
        background: #0d0d0d;
    }
    #right {
        width: 45%;
        border: solid #00bfff;
        padding: 1 2;
        background: #0d0d0d;
    }
    .pane-title {
        color: #00ff41;
        text-style: bold;
        padding: 0 1;
    }
    .pane-title-right {
        color: #00bfff;
        text-style: bold;
        padding: 0 1;
    }
    #terminal_log {
        height: 88%;
        background: #0d0d0d;
        color: #00ff41;
    }
    #chat_log {
        height: 88%;
        background: #0d0d0d;
        color: #00bfff;
    }
    #terminal_input {
        margin: 1 0;
        border: solid #00ff41;
        background: #1a1a1a;
        color: #00ff41;
    }
    #chat_input {
        margin: 1 0;
        border: solid #00bfff;
        background: #1a1a1a;
        color: white;
    }
    #status {
        color: #ffff00;
        text-style: italic;
        height: 1;
        padding: 0 1;
    }
    Header {
        background: #111111;
        color: #00ff41;
        text-style: bold;
    }
    Footer {
        background: #111111;
        color: #555555;
    }
    """

    def __init__(self):
        super().__init__()
        self.history = load_memory()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield Label("  TERMINAL", classes="pane-title")
                yield RichLog(id="terminal_log", highlight=True, markup=True)
                yield Input(placeholder="Type any bash command directly here...", id="terminal_input")
            with Vertical(id="right"):
                yield Label("  AI AGENT", classes="pane-title-right")
                yield RichLog(id="chat_log", highlight=True, markup=True)
                yield Input(placeholder="Tell AI your goal...", id="chat_input")
                yield Static("", id="status")
        yield Footer()

    def on_mount(self):
        chat_log = self.query_one("#chat_log", RichLog)
        terminal_log = self.query_one("#terminal_log", RichLog)
        chat_log.write("[bold #00bfff]hey! kali ai agent here[/bold #00bfff]")
        if self.history:
            chat_log.write(f"[#888888]i remember our last {len(self.history)} messages[/#888888]")
        else:
            chat_log.write("[#888888]tell me what you wanna do in plain english[/#888888]")
        chat_log.write("[#888888]──────────────────────────────────────[/#888888]")
        terminal_log.write("[bold #00ff41]terminal ready[/bold #00ff41]")
        terminal_log.write("[#888888]type raw bash commands directly here[/#888888]")
        terminal_log.write("[#888888]──────────────────────────────────────[/#888888]")

    def run_in_background(self, commands, chat_log, terminal_log, status):
        for i, command in enumerate(commands):
            command = command.strip()
            if not command:
                continue

            self.call_from_thread(status.update, f"running step {i+1} of {len(commands)}...")

            if is_dangerous(command):
                self.call_from_thread(chat_log.write, f"[bold red]blocked — too dangerous: {command}[/bold red]")
                self.call_from_thread(terminal_log.write, f"[bold red]BLOCKED: {command}[/bold red]")
                continue

            if is_interactive(command):
                self.call_from_thread(chat_log.write, f"[yellow]{command} is interactive, opening new terminal window...[/yellow]")
                self.call_from_thread(terminal_log.write, f"[#ffff00]$ xterm -e {command}[/#ffff00]")
                subprocess.Popen(f"xterm -e {command}", shell=True)
                continue

            self.call_from_thread(terminal_log.write, f"\n[bold #ffff00]$ {command}[/bold #ffff00]")

            try:
                stdout, stderr = run_command(command)
            except subprocess.TimeoutExpired:
                self.call_from_thread(terminal_log.write, "[bold red]timed out after 2 mins, skipping[/bold red]")
                self.call_from_thread(chat_log.write, "[yellow]that took too long so i skipped it[/yellow]")
                continue

            if stdout:
                self.call_from_thread(terminal_log.write, f"[#00ff41]{stdout.strip()}[/#00ff41]")

            if stderr and "warning" not in stderr.lower():
                self.call_from_thread(terminal_log.write, f"[bold red]{stderr.strip()}[/bold red]")
                self.call_from_thread(chat_log.write, f"[yellow]step {i+1} had an error, fixing...[/yellow]")
                fixed = ask_groq_fix(command, stderr)
                self.call_from_thread(chat_log.write, f"[#00ff41]retrying with: {fixed}[/#00ff41]")
                self.call_from_thread(terminal_log.write, f"[bold #ffff00]$ {fixed} (retry)[/bold #ffff00]")
                try:
                    stdout2, stderr2 = run_command(fixed)
                    if stdout2:
                        self.call_from_thread(terminal_log.write, f"[#00ff41]{stdout2.strip()}[/#00ff41]")
                    if stderr2 and "warning" not in stderr2.lower():
                        self.call_from_thread(terminal_log.write, f"[bold red]still failing: {stderr2.strip()}[/bold red]")
                        self.call_from_thread(chat_log.write, "[red]still broken, might need manual fix[/red]")
                except subprocess.TimeoutExpired:
                    self.call_from_thread(terminal_log.write, "[bold red]retry timed out[/bold red]")
            else:
                if stdout:
                    explanation = ask_groq_explain(stdout, command)
                    self.call_from_thread(chat_log.write, f"[#888888]{explanation}[/#888888]")

        self.call_from_thread(status.update, "done!")
        self.call_from_thread(chat_log.write, "[bold #00bfff]all done! what's next?[/bold #00bfff]")

    async def on_input_submitted(self, event: Input.Submitted):
        chat_log = self.query_one("#chat_log", RichLog)
        terminal_log = self.query_one("#terminal_log", RichLog)
        status = self.query_one("#status", Static)

        if event.input.id == "chat_input":
            user_goal = event.value.strip()
            if not user_goal:
                return
            event.input.clear()

            chat_log.write(f"\n[bold white]you:[/bold white] {user_goal}")
            status.update("thinking...")

            self.history.append({"role": "user", "content": user_goal})
            reply, commands = ask_groq_casual(user_goal, self.history)
            self.history.append({"role": "assistant", "content": reply})
            save_memory(self.history)

            chat_log.write(f"[bold #00bfff]AI:[/bold #00bfff] {reply}")

            if not commands:
                status.update("ready")
                return

            chat_log.write(f"[#888888]plan: {len(commands)} step(s)[/#888888]")
            for i, cmd in enumerate(commands):
                chat_log.write(f"[#555555]  {i+1}. {cmd}[/#555555]")

            thread = threading.Thread(
                target=self.run_in_background,
                args=(commands, chat_log, terminal_log, status),
                daemon=True
            )
            thread.start()

        elif event.input.id == "terminal_input":
            command = event.value.strip()
            if not command:
                return
            event.input.clear()

            if is_dangerous(command):
                terminal_log.write(f"[bold red]BLOCKED: {command}[/bold red]")
                return

            if is_interactive(command):
                terminal_log.write(f"[#ffff00]opening {command} in new window...[/#ffff00]")
                subprocess.Popen(f"xterm -e {command}", shell=True)
                return

            terminal_log.write(f"\n[bold #ffff00]$ {command}[/bold #ffff00]")

            def run_direct():
                try:
                    stdout, stderr = run_command(command)
                    if stdout:
                        self.call_from_thread(terminal_log.write, f"[#00ff41]{stdout.strip()}[/#00ff41]")
                    if stderr:
                        self.call_from_thread(terminal_log.write, f"[bold red]{stderr.strip()}[/bold red]")
                except subprocess.TimeoutExpired:
                    self.call_from_thread(terminal_log.write, "[bold red]timed out[/bold red]")

            threading.Thread(target=run_direct, daemon=True).start()

if __name__ == "__main__":
    app = AITerminal()
    app.run()
