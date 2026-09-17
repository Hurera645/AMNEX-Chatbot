import json
import mimetypes
import os
from collections import defaultdict, deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
SESSION_MEMORY = defaultdict(deque)
MAX_HISTORY = 8


def load_env_file():
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


def get_active_provider():
    provider = (os.getenv("AI_PROVIDER") or "openai").strip().lower()
    if provider in {"chatgpt", "openai"}:
        return "openai"
    if provider in {"gemini", "google"}:
        return "gemini"
    if provider == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        return "openai"
    return "openai"


def has_real_ai_key():
    provider = get_active_provider()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    return bool(os.getenv("OPENAI_API_KEY"))


def fallback_response(message: str) -> str:
    text = message.lower()

    if any(word in text for word in ["hello", "hi", "hey", "good morning", "good evening"]):
        return "Hello! I’m good and ready to chat with you."
    if "how are you" in text:
        return "I’m doing great, thank you! How can I help you today?"
    if "what is your name" in text or "your name" in text or "who are you" in text:
        return "I am AMNEX AI Chatbot, your friendly assistant."
    if "what time" in text or "time" in text:
        return f"The current time is {datetime.now().strftime('%H:%M:%S')}."
    if "bye" in text or "goodbye" in text or "see you" in text:
        return "Goodbye! Have a great day and talk to me anytime."
    if "i am good" in text or "im good" in text or "fine" in text:
        return "That’s nice to hear! What would you like to do today?"
    if "i am not good" in text or "sad" in text or "tired" in text:
        return "I’m sorry to hear that. Take a break and I’ll be here to help you feel better."
    if "code" in text or "program" in text:
        return "I can help with coding, debugging, project ideas, and learning programming concepts."
    if "who" in text and "you" in text:
        return "I’m a helpful AI assistant designed to chat, answer questions, and help with ideas."
    if "thank you" in text or "thanks" in text:
        return "You’re welcome! I’m happy to help."
    if "what can you do" in text or "help me" in text:
        return "I can chat, answer questions, help with coding, explain ideas, and assist with daily tasks."

    return "I’m here to help. You can ask me about coding, ideas, planning, or general questions."


def get_conversation_history(session_id: str):
    history = SESSION_MEMORY.get(session_id, deque(maxlen=MAX_HISTORY))
    return list(history)


def add_to_history(session_id: str, role: str, text: str):
    SESSION_MEMORY[session_id].append({"role": role, "content": text})


def call_openai_chat(message: str, history: list) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    messages = [
        {"role": "system", "content": "You are a helpful and friendly AI assistant. Keep the conversation natural and remember recent context."}
    ]
    for item in history:
        messages.append(item)
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 300,
    }

    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


def call_gemini_chat(message: str, history: list) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    parts = []
    for item in history:
        parts.append({"text": f"{item['role']}: {item['content']}"})
    parts.append({"text": f"user: {message}"})

    payload = {
        "contents": [{"parts": [{"text": "\n".join(part["text"] for part in parts)}]}],
        "systemInstruction": {
            "parts": [{"text": "You are a helpful and friendly AI assistant. Keep the conversation natural and remember recent context."}]
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_ai_reply(message: str, session_id: str = "default") -> str:
    history = get_conversation_history(session_id)
    provider = get_active_provider()

    if provider == "gemini" and os.getenv("GEMINI_API_KEY"):
        add_to_history(session_id, "user", message)
        try:
            reply = call_gemini_chat(message, history)
            add_to_history(session_id, "assistant", reply)
            return reply
        except (error.HTTPError, error.URLError, KeyError, ValueError, TimeoutError) as exc:
            reply = f"Gemini API error: {exc}. Using local fallback instead.\n{fallback_response(message)}"
            add_to_history(session_id, "assistant", reply)
            return reply

    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        add_to_history(session_id, "user", message)
        try:
            reply = call_openai_chat(message, history)
            add_to_history(session_id, "assistant", reply)
            return reply
        except (error.HTTPError, error.URLError, KeyError, ValueError, TimeoutError) as exc:
            reply = f"OpenAI API error: {exc}. Using local fallback instead.\n{fallback_response(message)}"
            add_to_history(session_id, "assistant", reply)
            return reply

    add_to_history(session_id, "user", message)
    reply = fallback_response(message)
    add_to_history(session_id, "assistant", reply)
    return reply


class ChatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            file_path = BASE_DIR / "templates" / "index.html"
            content_type = "text/html; charset=utf-8"
        elif path.startswith("/static/"):
            file_path = BASE_DIR / path.lstrip("/")
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        else:
            self.send_error(404, "Not Found")
            return

        try:
            data = file_path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "File Not Found")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404, "Not Found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
        except Exception:
            payload = {}

        message = str(payload.get("message", "")).strip()
        session_id = str(payload.get("session_id", "default"))
        if not message:
            reply = {"reply": "Please type a message first."}
            status = 400
        else:
            reply = {"reply": get_ai_reply(message, session_id)}
            status = 200

        response = json.dumps(reply).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer((host, port), ChatHandler)
    provider = get_active_provider()
    print(f"Chatbot running at http://localhost:{port}")
    print(f"Active AI provider: {provider}.")
    print("Set OPENAI_API_KEY or GEMINI_API_KEY in .env for real model responses.")
    server.serve_forever()
