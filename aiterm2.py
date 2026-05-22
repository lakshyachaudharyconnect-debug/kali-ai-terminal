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

def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    return result.stdout, result.stderr

def agent_think(goal, steps_done, last_output, last_error, history):
    context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-10:]])

    prompt = f"""You are an autonomous Kali Linux AI agent. You think and act in a loop until the goal is achieved.

GOAL: {goal}

STEPS ALREADY DONE:
{chr(10).join(steps_done) if steps_done else "None yet"}

LAST COMMAND OUTPUT:
{last_output if last_output else "None"}

LAST COMMAND ERROR:
{last_error if last_error else "None"}

CONVERSATION CONTEXT:
{context}

Based on the goal and what you have seen so far, decide what to do next.

Return ONLY this JSON format, nothing else:
{{
  "thinking": "your reasoning in 1 sentence",
  "next_command": "single bash command to run, or empty string if done",
  "goal_complete": true or false,
  "message": "casual 1 sentence message to user"
}}

Rules:
- Always append -y to apt commands
- If last command output shows the goal is achieved, set goal_complete to true and next_command to empty string immediately
- If there is no error and output looks correct, the goal is done — stop
- Only return one command at a time
- Do not repeat commands already done
- If you have run more than 3 steps and things are working, stop and mark complete"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are an autonomous Kali Linux agent. Return only valid JSON. Be aggressive about marking goal_complete as true the moment output confirms the goal is achieved. Never keep running after goal is done."},
            {"role": "user", "content": prompt}
        ]
    )
    raw = response.choices[0].message.content.strip()
    raw = clean_json(raw)
    try:
        return json.loads(raw)
    except:
        return {
            "thinking": "json parsing failed",
            "next_command": "",
            "goal_complete": True,
            "message": "something went wrong, stopping"
        }

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
        height: 85%;
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
    #thinking {
        color: #555555;
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
        self.agent_running = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield Label("  TERMINAL", classes="pane-title")
                yield RichLog(id="terminal_log", highlight=True, markup=True)
                yield Input(placeholder="Type any bash command directly here...", id="terminal_input")
            with Vertical(id="right"):
                yield Label("  AI AGENT v2", classes="pane-title-right")
                yield RichLog(id="chat_log", highlight=True, markup=True)
                yield Input(placeholder="Tell AI your goal...", id="chat_input")
                yield Static("", id="status")
                yield Static("", id="thinking")
        yield Footer()

    def on_mount(self):
        chat_log = self.query_one("#chat_log", RichLog)
        terminal_log = self.query_one("#terminal_log", RichLog)
        chat_log.write("[bold #00bfff]kali ai agent v2[/bold #00bfff]")
        if self.history:
            chat_log.write(f"[#888888]i remember our last {len(self.history)} messages[/#888888]")
        chat_log.write("[#888888]i think and act in a loop until your goal is done[/#888888]")
        chat_log.write("[#888888]──────────────────────────────────────[/#888888]")
        terminal_log.write("[bold #00ff41]terminal ready[/bold #00ff41]")
        terminal_log.write("[#888888]──────────────────────────────────────[/#888888]")

    def run_agent_loop(self, goal, chat_log, terminal_log, status, thinking_label):
        self.agent_running = True
        steps_done = []
        last_output = ""
        last_error = ""
        max_steps = 6
        step_count = 0

        self.call_from_thread(chat_log.write, f"\n[bold white]you:[/bold white] {goal}")
        self.call_from_thread(status.update, "agent thinking...")

        while step_count < max_steps:
            step_count += 1

            decision = agent_think(goal, steps_done, last_output, last_error, self.history)

            thinking = decision.get("thinking", "")
            next_command = decision.get("next_command", "").strip()
            goal_complete = decision.get("goal_complete", False)
            message = decision.get("message", "")

            self.call_from_thread(thinking_label.update, f"► {thinking}")

            if message:
                self.call_from_thread(chat_log.write, f"[bold #00bfff]AI:[/bold #00bfff] {message}")

            if goal_complete or not next_command:
                self.call_from_thread(chat_log.write, "[bold #00ff41]done! what's next?[/bold #00ff41]")
                self.call_from_thread(status.update, "ready")
                self.call_from_thread(thinking_label.update, "")
                break

            if is_dangerous(next_command):
                self.call_from_thread(chat_log.write, f"[bold red]blocked: {next_command}[/bold red]")
                self.call_from_thread(terminal_log.write, f"[bold red]BLOCKED: {next_command}[/bold red]")
                break

            if is_interactive(next_command):
                self.call_from_thread(chat_log.write, f"[yellow]opening {next_command} in new window[/yellow]")
                subprocess.Popen(f"xterm -e {next_command}", shell=True)
                break

            self.call_from_thread(terminal_log.write, f"\n[bold #ffff00]$ {next_command}[/bold #ffff00]")
            self.call_from_thread(status.update, f"step {step_count}...")

            try:
                stdout, stderr = run_command(next_command)
            except subprocess.TimeoutExpired:
                self.call_from_thread(terminal_log.write, "[bold red]timed out[/bold red]")
                last_error = "command timed out"
                last_output = ""
                steps_done.append(f"{next_command} → TIMEOUT")
                continue

            last_output = stdout
            last_error = stderr if "warning" not in stderr.lower() else ""

            if stdout:
                self.call_from_thread(terminal_log.write, f"[#00ff41]{stdout.strip()}[/#00ff41]")
            if stderr and "warning" not in stderr.lower():
                self.call_from_thread(terminal_log.write, f"[bold red]{stderr.strip()}[/bold red]")

            steps_done.append(f"{next_command} → {'OK: ' + stdout[:100] if not last_error else 'ERROR: ' + last_error[:100]}")

        if step_count >= max_steps:
            self.call_from_thread(chat_log.write, "[yellow]hit step limit, stopping[/yellow]")
            self.call_from_thread(status.update, "stopped")

        self.history.append({"role": "user", "content": goal})
        self.history.append({"role": "assistant", "content": f"completed: {goal} in {step_count} steps"})
        save_memory(self.history)
        self.agent_running = False

    async def on_input_submitted(self, event: Input.Submitted):
        chat_log = self.query_one("#chat_log", RichLog)
        terminal_log = self.query_one("#terminal_log", RichLog)
        status = self.query_one("#status", Static)
        thinking_label = self.query_one("#thinking", Static)

        if event.input.id == "chat_input":
            user_goal = event.value.strip()
            if not user_goal:
                return
            event.input.clear()

            if self.agent_running:
                chat_log.write("[yellow]still working on previous goal, please wait[/yellow]")
                return

            thread = threading.Thread(
                target=self.run_agent_loop,
                args=(user_goal, chat_log, terminal_log, status, thinking_label),
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
