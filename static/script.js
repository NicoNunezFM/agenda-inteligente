const chatArea = document.getElementById("chatArea");
const mensajeInput = document.getElementById("mensajeInput");

if (chatArea) {
    chatArea.scrollTop = chatArea.scrollHeight;
}

if (mensajeInput) {
    mensajeInput.addEventListener("keydown", function(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            this.form.submit();
        }
    });
}