const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const chatBox = document.getElementById("chatBox");
const resetButton = document.getElementById("resetChat");
const sessionId = `chat-${Date.now()}`;

function getTimeStamp() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function addMessage(content, role = "bot") {
  const message = document.createElement("div");
  message.className = `message ${role}`;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "bot" ? "AI" : "You";

  const text = document.createElement("span");
  text.textContent = content;

  const time = document.createElement("div");
  time.className = "meta";
  time.textContent = getTimeStamp();

  message.appendChild(meta);
  message.appendChild(text);
  message.appendChild(time);

  chatBox.appendChild(message);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function resetConversation() {
  chatBox.innerHTML = `
    <div class="message bot">
      <div class="meta">AI</div>
      <span>Conversation reset. Ask me anything.</span>
      <div class="meta">${getTimeStamp()}</div>
    </div>
  `;
  userInput.focus();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = userInput.value.trim();
  if (!message) return;

  addMessage(message, "user");
  userInput.value = "";

  const thinking = document.createElement("div");
  thinking.className = "message bot";
  thinking.innerHTML =
    "<div class='meta'>AI</div><span>Thinking...</span><div class='meta'>just now</div>";
  chatBox.appendChild(thinking);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    const data = await response.json();
    chatBox.removeChild(thinking);
    addMessage(data.reply || "Sorry, I could not respond.", "bot");
  } catch (error) {
    chatBox.removeChild(thinking);
    addMessage("Something went wrong. Please try again.", "bot");
  }
});

resetButton.addEventListener("click", resetConversation);
