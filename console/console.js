const $ = (id) => document.getElementById(id);
const post = (path) =>
  fetch(path, { method: "POST", headers: { "X-FileDrop-Console": "1" } }).then((r) => r.json());

function render(s) {
  $("state").textContent = s.state;
  $("url").textContent = s.url ? `Users connect at ${s.url}` : "";
  $("error").textContent = s.error || "";
  $("toggle").textContent = s.state === "running" ? "Stop web server" : "Start web server";
  $("toggle").disabled = s.state === "starting" || s.state === "stopping";
}

function refresh() {
  fetch("/api/server").then((r) => r.json()).then(render).catch(() => {
    $("state").textContent = "FileDrop is not running";
    $("toggle").disabled = true;
  });
}

$("toggle").addEventListener("click", () => {
  $("toggle").disabled = true;
  const running = $("state").textContent === "running";
  post(running ? "/api/server/stop" : "/api/server/start").then(render);
});

$("quit").addEventListener("click", () => {
  if (confirm("Quit FileDrop? The web server will stop for everyone.")) {
    post("/api/quit").then(() => { $("state").textContent = "FileDrop has quit"; });
  }
});

refresh();
setInterval(refresh, 3000);
