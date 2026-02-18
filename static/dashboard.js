let REFRESH_INTERVAL = 5000; // will be overridden by /api/status
let lastResetTime = Date.now(); // Time when progress bar was last reset
let isInitialLoad = true;

async function confirmQuit() {
  if (
    confirm("Stop the ADSBAlert app? You can restart it from the command line.")
  ) {
    try {
      await fetch("/api/quit", { method: "POST" });
      alert("App shutting down...");
    } catch (e) {
      console.error("Failed to quit:", e);
    }
  }
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const s = await res.json();
    REFRESH_INTERVAL = s.check_interval * 1000;

    // Use server's last fetch timestamp (ms) so progress persists across page reloads
    if (
      typeof s.last_fetch_time === "number" &&
      !Number.isNaN(s.last_fetch_time)
    ) {
      // guard against small clock skew (don't accept a future timestamp)
      lastResetTime = Math.min(s.last_fetch_time, Date.now());
    }

    const info = document.getElementById("refresh-info");
    if (info) {
      info.textContent = `Refresh: ${s.check_interval}s · Est req/day: ${s.estimated_requests_per_day} · Allowed/day: ${s.allowed_requests_per_day} · Remaining credits: ${s.remaining_credits}`;
    }
  } catch (e) {
    console.warn("Failed to fetch status", e);
  }
}

async function loadData() {
  const res = await fetch("/api/aircraft");
  const data = await res.json();

  const table = document.getElementById("aircraft-table");
  table.innerHTML = "";

  data.forEach((ac) => {
    const row = document.createElement("tr");
    if (ac.interesting) row.classList.add("interesting");

    row.innerHTML = `
            <td>${ac.icao24}</td>
            <td> <a href="https://flightradar24.com/${ac.registration}/" target="_blank" rel="noopener noreferrer"/>${ac.callsign || ac.registration}</td>
            <td>${ac.registration}</td>
            <td>${ac.typecode}</td>
            <td>${ac.operator}</td>
            <td>${ac.lat ?? ""}</td>
            <td>${ac.lon ?? ""}</td>
            <td>${ac.altitude ?? ""}</td>
            <td>${ac.velocity ?? ""}</td>
        `;
    table.appendChild(row);
  });

  // Only reset the progress timer on scheduled (client-driven) refreshes.
  // For the initial page load we keep the server-provided timestamp so the bar
  // continues where the backend left off.
  if (!isInitialLoad) {
    lastResetTime = Date.now();
  }
  isInitialLoad = false;
}

function updateProgressBar() {
  const elapsed = Date.now() - lastResetTime;
  const progress = Math.min((elapsed / REFRESH_INTERVAL) * 100, 100);
  document.getElementById("refresh-bar").style.width = progress + "%";

  // When progress hits 100%, reset and fetch new data
  if (progress >= 100) {
    lastResetTime = Date.now();
    loadData();
  }
}

setInterval(updateProgressBar, 50);
// initial status fetch to set interval and display quotas
fetchStatus().then(() => {
  setInterval(loadData, REFRESH_INTERVAL);
  loadData();
  // refresh status periodically in case env or config changes
  setInterval(fetchStatus, 60000);
});
