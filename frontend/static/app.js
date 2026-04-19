const mapEl = document.getElementById("map");
const statsEl = document.getElementById("stats");
const statusEl = document.getElementById("status");
const datasetForm = document.getElementById("dataset-form");
const imageForm = document.getElementById("image-form");
const sourceFilterEl = document.getElementById("source-filter");
const tagFilterEl = document.getElementById("tag-filter");
const simulateFeedBtn = document.getElementById("simulate-feed-btn");
const toggleRefreshBtn = document.getElementById("toggle-refresh-btn");
const typeFilterEls = {
  OSINT: document.getElementById("filter-osint"),
  HUMINT: document.getElementById("filter-humint"),
  IMINT: document.getElementById("filter-imint"),
};

let allRecords = [];
let currentSources = null;
let intelMap = null;
let markerLayer = null;
let autoRefreshId = null;
let lastRefreshAt = null;

function ensureMap() {
  if (intelMap) {
    return;
  }

  intelMap = L.map(mapEl, {
    crs: L.CRS.Simple,
    minZoom: -2,
    maxZoom: 2,
    zoomControl: true,
  });

  const bounds = [[0, 0], [100, 100]];
  L.imageOverlay("/terrain-map.svg", bounds).addTo(intelMap);
  markerLayer = L.layerGroup().addTo(intelMap);
  intelMap.fitBounds(bounds);
}

function renderStats(records) {
  const counts = records.reduce(
    (acc, record) => {
      acc.total += 1;
      const key = record.intelType.toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    { total: 0, osint: 0, humint: 0, imint: 0 }
  );

  statsEl.innerHTML = `
    <div class="stats-grid">
      <div class="stat"><span>Total Nodes</span><strong>${counts.total}</strong></div>
      <div class="stat"><span>OSINT</span><strong>${counts.osint}</strong></div>
      <div class="stat"><span>HUMINT</span><strong>${counts.humint}</strong></div>
      <div class="stat"><span>IMINT</span><strong>${counts.imint}</strong></div>
    </div>
  `;
}

function renderSourceModes(sources) {
  if (!sources) {
    return "";
  }
  const mongoMode = sources.mongo?.mode || "sample";
  const s3Mode = sources.s3?.mode || "sample";
  return `MongoDB: ${mongoMode.toUpperCase()} | S3: ${s3Mode.toUpperCase()}`;
}

function popupMarkup(record) {
  const imageMarkup = record.imagePath
    ? `<img src="${record.imagePath}" alt="${record.title}" />`
    : "";
  const tagMarkup = (record.tags || [])
    .map((tag) => `<span class="tag-pill">${tag}</span>`)
    .join("");

  return `
    <div class="intel-popup">
      <p class="eyebrow">${record.intelType} | ${record.sourceName}</p>
      <h3>${record.title}</h3>
      <p>${record.description || "No description provided."}</p>
      <p>Lat: ${record.lat} | Lon: ${record.lon}</p>
      <p>Confidence: ${record.confidence}%</p>
      <p>Priority: ${record.priority || "MEDIUM"} | Shape: ${record.markerShape || "circle"}</p>
      ${imageMarkup}
      <div class="tag-row">${tagMarkup}</div>
    </div>
  `;
}

function getActiveRecords() {
  const selectedTypes = Object.entries(typeFilterEls)
    .filter(([, element]) => element.checked)
    .map(([key]) => key);
  const sourceValue = sourceFilterEl.value;
  const tagValue = tagFilterEl.value;

  return allRecords.filter((record) => {
    const typeMatch = selectedTypes.includes(record.intelType);
    const sourceMatch = sourceValue === "ALL" || record.sourceName === sourceValue;
    const tagMatch = tagValue === "ALL" || (record.tags || []).includes(tagValue);
    return typeMatch && sourceMatch && tagMatch;
  });
}

function renderMarkers(records) {
  ensureMap();
  markerLayer.clearLayers();

  records.forEach((record) => {
    const lat = Math.max(0, Math.min(100, Number(record.lat)));
    const lon = Math.max(0, Math.min(100, Number(record.lon)));
    const marker = L.marker([100 - lat, lon], {
      title: record.title,
      icon: L.divIcon({
        className: "",
        html: `<div class="intel-marker ${record.intelType.toLowerCase()} ${(record.markerShape || "circle").toLowerCase()}"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      }),
    }).bindPopup(popupMarkup(record), {
      closeButton: false,
      offset: [0, -10],
    });

    marker.on("mouseover", () => marker.openPopup());
    marker.on("mouseout", () => marker.closePopup());
    marker.addTo(markerLayer);
  });
}

function populateSourceFilter(records) {
  const currentValue = sourceFilterEl.value;
  const sources = [...new Set(records.map((record) => record.sourceName))].sort();
  sourceFilterEl.innerHTML = `<option value="ALL">All Sources</option>${sources
    .map((source) => `<option value="${source}">${source}</option>`)
    .join("")}`;
  if (sources.includes(currentValue)) {
    sourceFilterEl.value = currentValue;
  }
}

function populateTagFilter(records) {
  const currentValue = tagFilterEl.value;
  const tags = [...new Set(records.flatMap((record) => record.tags || []))].sort();
  tagFilterEl.innerHTML = `<option value="ALL">All Tags</option>${tags
    .map((tag) => `<option value="${tag}">${tag}</option>`)
    .join("")}`;
  if (tags.includes(currentValue)) {
    tagFilterEl.value = currentValue;
  }
}

function refreshDashboardView() {
  const visibleRecords = getActiveRecords();
  renderStats(visibleRecords);
  renderMarkers(visibleRecords);
  const sourceModes = renderSourceModes(currentSources);
  const refreshed = lastRefreshAt ? ` Last refresh: ${lastRefreshAt}.` : "";
  statusEl.textContent = `Loaded ${visibleRecords.length} visible intelligence nodes. ${sourceModes}. Hover any marker to inspect image or metadata.${refreshed}`;
}

async function loadDashboard() {
  statusEl.textContent = "Loading intelligence picture...";
  const response = await fetch("/api/intelligence");
  const payload = await response.json();
  allRecords = payload.records || [];
  currentSources = payload.sources;
  populateSourceFilter(allRecords);
  populateTagFilter(allRecords);
  lastRefreshAt = new Date().toLocaleTimeString();
  refreshDashboardView();
}

async function submitForm(form, url) {
  statusEl.textContent = "Uploading and ingesting data...";
  const formData = new FormData(form);
  const response = await fetch(url, { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Upload failed.");
  }
  form.reset();
  form.querySelectorAll("[data-drop-label]").forEach((element) => {
    element.textContent = "No file selected";
  });
  statusEl.textContent = payload.message;
  await loadDashboard();
}

async function simulateFeed() {
  statusEl.textContent = "Simulating live feed...";
  const response = await fetch("/api/simulate-feed");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Simulation failed.");
  }
  statusEl.textContent = payload.message;
  await loadDashboard();
}

function toggleAutoRefresh() {
  if (autoRefreshId) {
    clearInterval(autoRefreshId);
    autoRefreshId = null;
    toggleRefreshBtn.textContent = "Start Auto Refresh";
    statusEl.textContent = "Auto refresh stopped.";
    return;
  }
  autoRefreshId = window.setInterval(() => {
    loadDashboard().catch((error) => {
      statusEl.textContent = error.message;
    });
  }, 5000);
  toggleRefreshBtn.textContent = "Stop Auto Refresh";
  statusEl.textContent = "Auto refresh started. Dashboard will refresh every 5 seconds.";
}

function attachDropzones() {
  document.querySelectorAll(".dropzone").forEach((zone) => {
    const input = document.getElementById(zone.dataset.targetInput);
    const label = zone.querySelector("[data-drop-label]");

    function updateLabel() {
      label.textContent = input.files?.[0]?.name || "No file selected";
    }

    zone.addEventListener("click", () => input.click());
    input.addEventListener("change", updateLabel);

    ["dragenter", "dragover"].forEach((eventName) => {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.remove("dragover");
      });
    });

    zone.addEventListener("drop", (event) => {
      const files = event.dataTransfer?.files;
      if (!files?.length) {
        return;
      }
      input.files = files;
      updateLabel();
    });
  });
}

datasetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await submitForm(datasetForm, "/api/upload/dataset");
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

imageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await submitForm(imageForm, "/api/upload/image");
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

Object.values(typeFilterEls).forEach((element) => {
  element.addEventListener("change", refreshDashboardView);
});

sourceFilterEl.addEventListener("change", refreshDashboardView);
tagFilterEl.addEventListener("change", refreshDashboardView);

simulateFeedBtn.addEventListener("click", async () => {
  try {
    await simulateFeed();
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

toggleRefreshBtn.addEventListener("click", toggleAutoRefresh);

attachDropzones();
loadDashboard().catch((error) => {
  statusEl.textContent = error.message;
});
