// Placeholder: confirms the LAN API is reachable.
fetch("/api/v1/health")
  .then((r) => r.json())
  .then((d) => { document.getElementById("health").textContent = `Server is up (v${d.version}).`; })
  .catch(() => { document.getElementById("health").textContent = "Server unreachable."; });
