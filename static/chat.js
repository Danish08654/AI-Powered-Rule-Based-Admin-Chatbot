document.getElementById("msgForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("msg");
  const text = input.value.trim();
  if (!text) return;
  // show admin message immediately
  const messages = document.getElementById("messages");
  const adminDiv = document.createElement("div");
  adminDiv.className = "admin";
  adminDiv.innerText = text;
  messages.appendChild(adminDiv);
  messages.appendChild(document.createElement("br"));
  input.value = "";

  const res = await fetch("/api/message", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({message: text})
  });
  const data = await res.json();
  const botDiv = document.createElement("div");
  botDiv.className = "bot";
  botDiv.innerText = data.reply || "No response";
  messages.appendChild(botDiv);
  messages.appendChild(document.createElement("br"));
  window.scrollTo(0, document.body.scrollHeight);
});
