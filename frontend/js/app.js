const state = {
  mode: "map",
  persons: [],
  personId: null,
  pair: { a: null, b: null },
  currentEpisode: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    /* respuesta sin JSON */
  }
  if (!res.ok) {
    throw new Error((data && data.error) || "Error " + res.status);
  }
  return data;
}

function escapeHtml(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function scoreColor(score) {
  const hue = Math.round(((score - 1) / 9) * 120); // 1 -> rojo, 10 -> verde
  return `hsl(${hue}, 70%, 50%)`;
}

function formatValue(value) {
  if (value === null || value === undefined) return "";
  const num = Number(value);
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

function personById(id) {
  return state.persons.find((p) => p.id === id) || null;
}

/* ---------- Personas ---------- */

async function loadPersons() {
  state.persons = await api("/api/persons");

  ["person-select", "person-a", "person-b"].forEach((id) => {
    const sel = $(id);
    sel.innerHTML = "";
    state.persons.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = String(p.id);
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
  });

  const first = state.persons.length > 0 ? state.persons[0].id : null;
  const second = state.persons.length > 1 ? state.persons[1].id : first;

  if (first != null && (!state.personId || !personById(state.personId))) {
    state.personId = first;
  }
  if (first == null) state.personId = null;

  if (first != null) {
    const a = personById(state.pair.a) ? state.pair.a : first;
    const b = personById(state.pair.b) ? state.pair.b : second;
    state.pair = { a, b };
  } else {
    state.pair = { a: null, b: null };
  }

  if ($("person-select").options.length) $("person-select").value = String(state.personId);
  if ($("person-a").options.length) $("person-a").value = String(state.pair.a);
  if ($("person-b").options.length) $("person-b").value = String(state.pair.b);

  const chips = $("person-chips");
  chips.innerHTML = "";
  state.persons.forEach((p) => {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = p.name;
    chips.appendChild(chip);
  });
}

/* ---------- Heatmap ---------- */

function renderMessage(text) {
  const table = $("heatmap");
  table.innerHTML = "";
  const tbody = document.createElement("tbody");
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.className = "empty";
  td.colSpan = 13;
  td.textContent = text;
  tr.appendChild(td);
  tbody.appendChild(tr);
  table.appendChild(tbody);
}

/**
 * Dibuja la tabla heatmap compartida por Mapa y Promedio.
 * seasons: [{ number, episodes: [{ season, number, title, scores, average }] }]
 * getCell(ep) -> { value: number|null, display: string }
 * tooltipFor(ep, value) -> string
 * mode: "map" | "average" (modo con el que se abre el modal)
 */
function renderHeatmap(seasons, getCell, tooltipFor, mode) {
  const table = $("heatmap");
  table.innerHTML = "";

  const sorted = (seasons || []).slice().sort((a, b) => a.number - b.number);
  if (!sorted.length) {
    renderMessage("Todavía no hay episodios.");
    return;
  }

  const bySeason = new Map();
  let maxEp = 0;
  sorted.forEach((season) => {
    const map = new Map();
    (season.episodes || []).forEach((ep) => {
      map.set(ep.number, ep);
      if (ep.number > maxEp) maxEp = ep.number;
    });
    bySeason.set(season.number, map);
  });

  // Cabecera: esquina + una columna por temporada
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.className = "heatmap-corner";
  corner.textContent = "E \\ T";
  headRow.appendChild(corner);
  sorted.forEach((season) => {
    const th = document.createElement("th");
    th.textContent = "T" + season.number;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  // Filas: una por número de episodio
  const tbody = document.createElement("tbody");
  for (let n = 1; n <= maxEp; n++) {
    const tr = document.createElement("tr");
    const rowHead = document.createElement("th");
    rowHead.textContent = "E" + n;
    tr.appendChild(rowHead);

    sorted.forEach((season) => {
      const td = document.createElement("td");
      const ep = bySeason.get(season.number).get(n);
      if (!ep) {
        td.className = "heatmap-empty";
      } else {
        const cell = getCell(ep);
        const value = cell ? cell.value : null;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "heatmap-cell" + (value != null ? " has-score" : "");
        btn.title = tooltipFor(ep, value);
        btn.textContent = value != null ? cell.display : "";
        if (value != null) btn.style.background = scoreColor(value);
        btn.addEventListener("click", () => openModal(ep, mode));
        td.appendChild(btn);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

function mapCell(ep) {
  const value = state.personId != null && ep.scores ? ep.scores[state.personId] : null;
  const v = value === null || value === undefined ? null : Number(value);
  return { value: v, display: formatValue(v) };
}

function averageCell(ep) {
  const value = ep.average === null || ep.average === undefined ? null : Number(ep.average);
  return { value, display: formatValue(value) };
}

function mapTooltip(ep, value) {
  return `T${ep.season}E${ep.number} · ${ep.title}` + (value != null ? ` · ${formatValue(value)}/10` : " · sin nota");
}

function averageTooltip(ep, value) {
  const a = ep.scores ? ep.scores[state.pair.a] : null;
  const b = ep.scores ? ep.scores[state.pair.b] : null;
  const nameA = personById(state.pair.a)?.name || "A";
  const nameB = personById(state.pair.b)?.name || "B";
  let tip = `T${ep.season}E${ep.number} · ${ep.title}`;
  if (value != null) tip += ` · promedio ${formatValue(value)}`;
  tip += ` · ${nameA}: ${a != null ? a : "–"} · ${nameB}: ${b != null ? b : "–"}`;
  return tip;
}

/* ---------- Vistas ---------- */

async function renderCurrentView() {
  if (state.mode === "map") {
    if (state.personId == null) {
      renderMessage("Añadí una persona para empezar a puntuar.");
      return;
    }
    const data = await api(`/api/episodes/all?person=${state.personId}`);
    renderHeatmap(data.seasons, mapCell, mapTooltip, "map");
    return;
  }

  if (state.pair.a == null || state.pair.b == null) {
    renderMessage("Elegí dos personas para ver el promedio.");
    return;
  }
  const data = await api(`/api/averages?person_a=${state.pair.a}&person_b=${state.pair.b}`);
  renderHeatmap(data.seasons, averageCell, averageTooltip, "average");
}

async function switchMode(mode) {
  state.mode = mode;
  $("view-map").classList.toggle("hidden", mode !== "map");
  $("view-average").classList.toggle("hidden", mode !== "average");
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
  await renderCurrentView();
}

/* ---------- Modal ---------- */

function openModal(ep, mode) {
  state.currentEpisode = ep;
  $("modal-title").textContent = `Temporada ${ep.season} · Episodio ${ep.number}: ${ep.title}`;
  const content = $("modal-content");
  content.innerHTML = `
    <p><strong>${escapeHtml(ep.title)}</strong></p>
    ${
      ep.references
        ? `<div class="modal-synopsis">
             <span class="modal-synopsis-label">Sinopsis</span>
             <p>${escapeHtml(ep.references)}</p>
           </div>`
        : ""
    }
    <div id="refs-wrap"></div>
    <div id="score-wrap"></div>
    <div class="modal-actions">
      <button id="save-refs-btn">💾 Guardar referencias</button>
      <button id="close-modal-btn">Cerrar</button>
    </div>
  `;

  // Personas que se puntúan y anotan en este modal (sin duplicados si A = B)
  const people = [];
  const seen = new Set();
  const addPerson = (pid) => {
    const person = personById(pid);
    if (person && !seen.has(person.id)) {
      seen.add(person.id);
      people.push(person);
    }
  };
  if (mode === "map") addPerson(state.personId);
  else [state.pair.a, state.pair.b].forEach(addPerson);

  const refsWrap = $("refs-wrap");
  people.forEach((person) => {
    const block = document.createElement("div");
    block.className = "ref-block";
    const label = document.createElement("label");
    label.htmlFor = "ref-" + person.id;
    label.textContent = "Referencias de " + person.name;
    const textarea = document.createElement("textarea");
    textarea.id = "ref-" + person.id;
    textarea.rows = 3;
    textarea.placeholder = "Mejor momento, frases, chistes…";
    textarea.value = (ep.refs && ep.refs[person.id]) || "";
    block.appendChild(label);
    block.appendChild(textarea);
    refsWrap.appendChild(block);
  });

  const scoreWrap = $("score-wrap");
  people.forEach((person) => {
    const row = document.createElement("div");
    row.className = "score-row";
    const label = document.createElement("label");
    label.htmlFor = "score-" + person.id;
    label.textContent = person.name;
    const input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = "10";
    input.step = "0.1";
    input.inputMode = "decimal";
    input.placeholder = "1–10";
    input.id = "score-" + person.id;
    input.value = ep.scores && ep.scores[person.id] != null ? ep.scores[person.id] : "";
    row.appendChild(label);
    row.appendChild(input);
    scoreWrap.appendChild(row);
  });

  if (people.length) {
    const hint = document.createElement("p");
    hint.className = "score-hint";
    hint.textContent = "Escala 1–10 · admite decimales (ej. 9.5) · dejar vacío borra la nota";
    scoreWrap.appendChild(hint);
  }

  scoreWrap.querySelectorAll("input[type=number]").forEach((input) => {
    input.addEventListener("change", async () => {
      const personId = parseInt(input.id.replace("score-", ""), 10);
      const ep = state.currentEpisode;
      if (!ep) return;
      try {
        if (input.value === "") {
          await api(
            `/api/scores?person_id=${personId}&season=${ep.season}&episode_number=${ep.number}`,
            { method: "DELETE" }
          );
        } else {
          const value = parseFloat(input.value);
          if (!Number.isFinite(value) || value < 1 || value > 10) {
            alert("La puntuación tiene que ser un número entre 1 y 10 (admite decimales, ej. 9.5).");
            input.value = ep.scores && ep.scores[personId] != null ? ep.scores[personId] : "";
            return;
          }
          await api("/api/scores", {
            method: "POST",
            body: JSON.stringify({
              person_id: personId,
              season: ep.season,
              episode_number: ep.number,
              value: Math.round(value * 10) / 10,
            }),
          });
        }
        closeModal();
        await renderCurrentView();
      } catch (e) {
        alert("Error: " + e.message);
      }
    });
  });

  $("save-refs-btn").addEventListener("click", async () => {
    const ep = state.currentEpisode;
    if (!ep) return;
    try {
      await Promise.all(
        people.map((person) => {
          const textarea = $("ref-" + person.id);
          return api("/api/references", {
            method: "POST",
            body: JSON.stringify({
              person_id: person.id,
              season: ep.season,
              number: ep.number,
              references: textarea ? textarea.value : "",
            }),
          });
        })
      );
      closeModal();
      await renderCurrentView();
    } catch (e) {
      alert("Error: " + e.message);
    }
  });

  $("close-modal-btn").addEventListener("click", closeModal);
  $("modal").classList.remove("hidden");
}

function closeModal() {
  $("modal").classList.add("hidden");
  state.currentEpisode = null;
}

/* ---------- Eventos ---------- */

async function addPerson() {
  const name = $("new-person-name").value.trim();
  if (!name) return;
  try {
    const person = await api("/api/persons", { method: "POST", body: JSON.stringify({ name }) });
    $("new-person-name").value = "";
    if (state.personId == null) state.personId = person.id;
    if (state.pair.a == null) state.pair.a = person.id;
    if (state.pair.b == null) state.pair.b = person.id;
    await loadPersons();
    await renderCurrentView();
  } catch (e) {
    alert("Error: " + e.message);
  }
}

async function init() {
  await loadPersons();

  $("person-select").addEventListener("change", async (e) => {
    state.personId = parseInt(e.target.value, 10);
    await renderCurrentView();
  });
  $("person-a").addEventListener("change", async (e) => {
    state.pair = { a: parseInt(e.target.value, 10), b: state.pair.b };
    await renderCurrentView();
  });
  $("person-b").addEventListener("change", async (e) => {
    state.pair = { a: state.pair.a, b: parseInt(e.target.value, 10) };
    await renderCurrentView();
  });

  $("tab-map").addEventListener("click", () => switchMode("map"));
  $("tab-average").addEventListener("click", () => switchMode("average"));

  $("add-person-btn").addEventListener("click", addPerson);
  $("new-person-name").addEventListener("keydown", (e) => {
    if (e.key === "Enter") addPerson();
  });
  $("modal-close").addEventListener("click", closeModal);

  await renderCurrentView();
}

init();
