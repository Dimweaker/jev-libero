import {
  LAYERS,
  COLORS,
  LAYER_COLORS,
  label,
  compactAction,
  stepAt,
  frameAt,
  layerCall,
  distribution,
  actionState,
  project,
  polyline,
} from "./replay.js";

const $ = (id) => document.getElementById(id);
const video = $("video");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const state = {
  data: null,
  index: -1,
  layer: "motor",
  candidate: null,
  chart: [],
  path: [],
  load: 0,
  raf: 0,
};
const cache = new Map();
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const percent = (value) => `${Math.round(value * 100)}%`;
const pad = (value) => String(value).padStart(2, "0");
const icons = {
  intent: '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2"/>',
  strategy: '<path d="M3 2v8l3 3m7-11v8l-3 3M8 1v7"/>',
  motor: '<path d="M2 8h12M10 4l4 4-4 4M8 2v12"/>',
};
const titles = {
  intent: "Which objective?",
  strategy: "Which interaction?",
  motor: "Which input?",
};
const selectedStep = () => state.data.steps[state.index];

function showError(message) {
  $("load-status").hidden = false;
  $("load-status").classList.add("error");
  $("load-status").textContent = message;
}

async function loadEpisode(id) {
  const token = ++state.load;
  stopAnimation();
  video.pause();
  state.data = null;
  state.index = -1;
  state.layer = "motor";
  state.candidate = null;
  $("explorer").setAttribute("aria-busy", "true");
  $("load-status").classList.remove("error");
  $("load-status").hidden = false;
  $("load-status").textContent = "Loading the recorded episode…";
  document.querySelectorAll("[data-episode]").forEach((button) => {
    const selected = button.dataset.episode === id;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  $("episode-panel").setAttribute("aria-labelledby", `tab-${id}`);
  try {
    if (!cache.has(id)) {
      const response = await fetch(`./data/${id}.json`);
      if (!response.ok)
        throw new Error(
          `Episode data could not load (HTTP ${response.status}).`,
        );
      cache.set(id, await response.json());
    }
    if (token !== state.load) return;
    const data = cache.get(id);
    state.data = data;
    $("episode-title").textContent = data.title;
    $("duration").textContent = `${data.duration.toFixed(2)} s`;
    $("seek").max = data.duration;
    $("seek").value = 0;
    $("measure-title").textContent = data.measure.toUpperCase();
    $("unit").textContent = data.unit;
    $("chart-end").textContent = `${data.duration.toFixed(2)} s`;
    $("record-link").href =
      `https://github.com/Dimweaker/jev-libero/tree/main/examples/records/${data.record}`;
    $("timeline").innerHTML = data.steps
      .map(
        (step, index) =>
          `<button style="--duration:${step.end - step.start};--tint:${COLORS[step.intent]}" data-step="${index}" aria-label="Decision ${index + 1}: ${escape(label(step.intent))}, ${escape(label(step.choice))}" title="${pad(index + 1)} · ${escape(label(step.intent))} · ${escape(label(step.choice))}">${pad(index + 1)}</button>`,
      )
      .join("");
    $("action-grid").innerHTML = data.actions
      .map(
        (action) =>
          `<button class="action-cell" data-action="${escape(action)}">${escape(compactAction(action))}</button>`,
      )
      .join("");
    buildChart();
    buildPath();
    video.src = data.video;
    video.playbackRate = Number($("speed").value);
    video.load();
    tick();
  } catch (error) {
    if (token === state.load) showError(error.message);
  }
}

function buildChart() {
  const values = state.data.samples;
  const low = Math.min(0, ...values),
    high = Math.max(...values);
  state.chart = values.map((value, index) => [
    8 + (index / (values.length - 1)) * 464,
    102 - ((value - low) / Math.max(high - low, 1)) * 92,
  ]);
  $("chart-line").setAttribute("d", polyline(state.chart));
  $("chart-area").setAttribute(
    "d",
    `${polyline(state.chart)} L472,110 L8,110 Z`,
  );
}

function buildPath() {
  if (!state.data) return;
  state.pathKey = null;
  const points = [
    ...state.data.steps.map((step) => step.before.eef_mm),
    state.data.steps.at(-1).after.eef_mm,
  ];
  const forecasts = state.data.steps.flatMap((step) =>
    Object.values(step.effects).map((effect) => effect.eef),
  );
  const projected = project([...points, ...forecasts], $("projection").value);
  state.path = projected.slice(0, points.length);
  let offset = points.length;
  state.branches = state.data.steps.map((step) =>
    Object.fromEntries(
      Object.keys(step.effects).map((action) => [action, projected[offset++]]),
    ),
  );
  $("path-full").setAttribute("d", polyline(state.path));
  $("path-points").innerHTML = state.path
    .map(
      ([x, y], i) =>
        `<circle cx="${x}" cy="${y}" r="2.5" fill="#e3dedf" stroke="#b0a9b3" stroke-width=".7"><title>${i === state.data.steps.length ? "Final position" : `Decision ${i + 1}`} · ${points[i].map((v) => v.toFixed(1)).join(", ")} mm</title></circle>`,
    )
    .join("");
  updatePath();
}

function updatePath() {
  if (state.index < 0 || !state.path.length) return;
  const complete = video.currentTime >= state.data.duration - 0.001;
  const key = `${state.index}/${state.candidate}/${$("projection").value}/${complete}`;
  if (key === state.pathKey) return;
  state.pathKey = key;
  const index = complete ? state.path.length - 1 : state.index;
  const [x, y] = state.path[index];
  $("path-traveled").setAttribute(
    "d",
    polyline(state.path.slice(0, index + 1)),
  );
  $("path-dot").setAttribute("cx", x);
  $("path-dot").setAttribute("cy", y);
  const step = selectedStep();
  const selected = step.effects[state.candidate]
    ? state.candidate
    : step.choice;
  const actions = [...new Set([...step.eligible, selected])];
  $("path-branches").innerHTML = complete
    ? ""
    : actions
        .map((action) => {
          const end = state.branches[state.index][action];
          const highlighted = action === selected;
          const color = highlighted ? "#a04d88" : "#b6aec5";
          return `<g><path d="${polyline([[x, y], end])}" fill="none" stroke="${color}" stroke-width="${highlighted ? 1.8 : 0.8}" stroke-dasharray="3 3"/><circle cx="${end[0]}" cy="${end[1]}" r="${highlighted ? 3 : 1.7}" fill="${highlighted ? "#efb3dc" : "#f5f5ef"}" stroke="${color}" stroke-width="1"><title>${escape(label(action))} · preview endpoint</title></circle></g>`;
        })
        .join("");
  const point = complete
    ? selectedStep().after.eef_mm
    : selectedStep().before.eef_mm;
  const axes = $("projection").value;
  $("path-position").textContent =
    axes
      .split("")
      .map(
        (axis) =>
          `${axis.toUpperCase()} ${point["xyz".indexOf(axis)].toFixed(0)}`,
      )
      .join(" / ") + " mm";
}

function renderDecision(index) {
  state.index = index;
  state.candidate = null;
  const step = selectedStep();
  $("decision-counter").textContent =
    `${pad(index + 1)} / ${pad(state.data.steps.length)}`;
  $("action-overlay").textContent = label(step.choice);
  $("contact-overlay").textContent = step.before.moving_contact
    ? "TARGET CONTACT"
    : "FREE SPACE";
  $("contact-overlay").classList.toggle("touching", step.before.moving_contact);
  $("flow").innerHTML = LAYERS.map((layer, i) => {
    const call = layerCall(state.data, step, layer);
    const fresh = step.fresh.includes(layer);
    const choice = call.response.answers[layer].choice;
    return `<button class="flow-card ${fresh ? "fresh" : "held"}" data-layer="${layer}" style="--tint:${LAYER_COLORS[layer]}" aria-pressed="${state.layer === layer}" aria-label="Inspect ${layer}: ${escape(label(choice))}"><span class="flow-label">${pad(i + 1)} / ${layer.toUpperCase()}<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true">${icons[layer]}</svg></span><span class="flow-value">${escape(label(choice))}</span><span class="flow-state"><i></i>${fresh ? "NEW CHOICE" : `KEPT FROM #${pad(call.step + 1)}`}</span></button>`;
  }).join("");
  [...$("timeline").children].forEach((button, i) => {
    button.setAttribute("aria-current", String(i === index));
    button.classList.toggle("past", i < index);
  });
  [...$("action-grid").children].forEach((button) => {
    const action = button.dataset.action;
    const category = actionState(step, action);
    const status = {
      selected: "chosen by Jev",
      offered: "offered to Jev",
      feasible: "feasible in another goal or family",
      excluded: "not eligible",
    }[category];
    button.className = `action-cell ${category}`;
    button.title = `${label(action)} · ${status}`;
    button.setAttribute("aria-label", button.title);
  });
  $("candidate-count").textContent = `27 → ${step.eligible.length} OFFERED`;
  renderDistribution();
  updatePath();
}

function renderDistribution() {
  const step = selectedStep();
  const layer = state.layer;
  const call = layerCall(state.data, step, layer);
  const answer = call.response.answers[layer];
  const rows = distribution(state.data, step, layer);
  $("layer-number").textContent =
    `${pad(LAYERS.indexOf(layer) + 1)} / ${layer.toUpperCase()}`;
  $("distribution-title").textContent = titles[layer];
  $("confidence-value").textContent = percent(answer.confidence);
  $("option-count").textContent =
    `${rows.length} option${rows.length === 1 ? "" : "s"}`;
  $("call-status").textContent =
    call.step === step.index
      ? "Recorded Choice probabilities"
      : `Choice retained from decision ${pad(call.step + 1)}`;
  $("call-latency").textContent = `${Math.round(call.latency_s * 1000)} ms`;
  $("probabilities").innerHTML = rows
    .map(
      ({ name, probability, chosen }) =>
        `<button class="prob-row ${chosen ? "chosen" : ""}" data-candidate="${escape(name)}" title="${escape(label(name))}: ${percent(probability)}${chosen ? " · selected" : ""}" aria-label="${escape(label(name))}, probability ${percent(probability)}${chosen ? ", selected" : ""}"><span class="prob-name">${chosen ? '<span class="check">↗</span>' : ""}${escape(label(name))}</span><span class="prob-track"><span class="prob-fill entering" style="--p:${probability * 100}%;display:block"></span></span><span class="prob-value">${percent(probability)}</span></button>`,
    )
    .join("");
  document
    .querySelectorAll("[data-layer]")
    .forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.layer === layer),
      ),
    );
  renderCandidate(answer.choice);
}

function renderCandidate(name) {
  state.candidate = name;
  const step = selectedStep();
  [...$("probabilities").children].forEach((button) =>
    button.classList.toggle("inspecting", button.dataset.candidate === name),
  );
  if (state.layer === "motor" && step.effects[name]) {
    const effect = step.effects[name];
    const offered = step.eligible.includes(name);
    $("candidate-detail").innerHTML =
      `<strong>${escape(label(name))}</strong> · ${offered ? "preview" : "not offered"}<br>Progress <strong>${effect.progress >= 0 ? "+" : ""}${effect.progress.toFixed(2)}${state.data.unit}</strong> <span class="muted">/</span> surface gap <strong>${effect.gap.toFixed(1)} mm</strong> <span class="muted">/</span> ${effect.contact ? "target contact" : "free space"}`;
  } else {
    const criterion = layerCall(state.data, step, state.layer).request
      .questions[state.layer].criteria[name];
    let text = typeof criterion === "string" ? criterion : criterion?.meaning;
    if (!text)
      text =
        "This interaction groups inputs by their predicted contact and motion.";
    $("candidate-detail").textContent = text;
  }
  updatePath();
}

function tick() {
  if (!state.data) return;
  const time = Math.min(video.currentTime, state.data.duration);
  const index = stepAt(state.data, time);
  if (state.index !== index) renderDecision(index);
  const frame = frameAt(state.data, time);
  $("seek").value = time;
  $("seek").setAttribute(
    "aria-valuetext",
    `${time.toFixed(2)} seconds, decision ${index + 1}`,
  );
  $("clock").textContent = time.toFixed(2).padStart(5, "0");
  $("frame-counter").textContent =
    `${String(frame).padStart(3, "0")} / ${state.data.summary.sim_steps}`;
  $("measure").textContent = state.data.samples[frame].toFixed(1);
  const step = selectedStep();
  const observed =
    state.data.samples[step.startFrame] - state.data.samples[frame];
  const signed = (value) =>
    `${value >= 0 ? "+" : ""}${value.toFixed(2)}${state.data.unit}`;
  $("forecast-effect").textContent = signed(step.predictedProgress);
  $("observed-effect").textContent = signed(observed);
  const [x, y] = state.chart[frame];
  $("chart-cursor").setAttribute("x1", x);
  $("chart-cursor").setAttribute("x2", x);
  $("chart-dot").setAttribute("cx", x);
  $("chart-dot").setAttribute("cy", y);
  const complete = time >= state.data.duration - 0.001;
  $("outcome").textContent =
    complete && state.data.summary.success
      ? "✓ SUCCESS"
      : video.paused
        ? "PAUSED"
        : "PLAYING";
  $("outcome").classList.toggle(
    "success",
    complete && state.data.summary.success,
  );
  if (complete) {
    $("contact-overlay").textContent = selectedStep().after.moving_contact
      ? "TARGET CONTACT"
      : "FREE SPACE";
    $("contact-overlay").classList.toggle(
      "touching",
      selectedStep().after.moving_contact,
    );
  }
  updatePath();
}

function loop() {
  tick();
  state.raf = requestAnimationFrame(loop);
}
function stopAnimation() {
  cancelAnimationFrame(state.raf);
}
function playbackUI() {
  const playing = !video.paused;
  document.body.classList.toggle("playing", playing);
  const ended =
    video.ended ||
    (state.data && video.currentTime >= state.data.duration - 0.001);
  $("play").innerHTML = playing
    ? "Ⅱ <span>Pause</span>"
    : ended
      ? "↻ <span>Replay</span>"
      : "▶ <span>Play</span>";
  $("play").setAttribute(
    "aria-label",
    playing
      ? "Pause trajectory"
      : ended
        ? "Replay trajectory"
        : "Play trajectory",
  );
  $("video-toggle").innerHTML = playing
    ? '<span aria-hidden="true">Ⅱ</span>'
    : '<span aria-hidden="true">▶</span>';
  $("video-toggle").setAttribute(
    "aria-label",
    playing ? "Pause trajectory" : "Play trajectory",
  );
}
async function togglePlay() {
  if (!state.data || video.readyState < 1) return;
  if (!video.paused) {
    video.pause();
    return;
  }
  if (video.ended || video.currentTime >= state.data.duration - 0.001)
    video.currentTime = 0;
  try {
    await video.play();
  } catch {
    playbackUI();
  }
}
function seek(time) {
  if (!state.data || video.readyState < 1) return;
  video.pause();
  video.currentTime = Math.max(0, Math.min(state.data.duration, time));
  tick();
  playbackUI();
}
function jump(index) {
  if (!state.data) return;
  const step =
    state.data.steps[Math.max(0, Math.min(state.data.steps.length - 1, index))];
  seek(step.start);
}

video.addEventListener("loadedmetadata", async () => {
  if (!state.data) return;
  if (Math.abs(video.duration - state.data.duration) > 0.06) {
    showError("Video and trace durations differ. Please reload the page.");
    return;
  }
  video.playbackRate = Number($("speed").value);
  $("explorer").setAttribute("aria-busy", "false");
  $("load-status").hidden = true;
  tick();
  playbackUI();
  if (!reducedMotion.matches) {
    try {
      await video.play();
    } catch {
      playbackUI();
    }
  }
});
video.addEventListener("error", () =>
  showError(
    "The trajectory video could not load. Please reload, or open the MP4 from the GitHub README.",
  ),
);
video.addEventListener("play", () => {
  playbackUI();
  stopAnimation();
  loop();
});
video.addEventListener("pause", () => {
  stopAnimation();
  playbackUI();
  tick();
});
video.addEventListener("ended", () => {
  stopAnimation();
  playbackUI();
  tick();
});
video.addEventListener("seeked", tick);
video.addEventListener("timeupdate", () => {
  if (video.paused) tick();
});
$("play").addEventListener("click", togglePlay);
$("video-toggle").addEventListener("click", togglePlay);
$("previous").addEventListener("click", () => jump(state.index - 1));
$("next").addEventListener("click", () => jump(state.index + 1));
$("seek").addEventListener("input", (event) =>
  seek(Number(event.target.value)),
);
$("speed").addEventListener("change", (event) => {
  video.playbackRate = Number(event.target.value);
});
$("projection").addEventListener("change", buildPath);
$("timeline").addEventListener("click", (event) => {
  const button = event.target.closest("[data-step]");
  if (button) jump(Number(button.dataset.step));
});
$("flow").addEventListener("click", (event) => {
  const button = event.target.closest("[data-layer]");
  if (button) {
    video.pause();
    state.layer = button.dataset.layer;
    renderDistribution();
  }
});
$("probabilities").addEventListener("click", (event) => {
  const button = event.target.closest("[data-candidate]");
  if (button) {
    video.pause();
    renderCandidate(button.dataset.candidate);
  }
});
$("action-grid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (button && state.data) {
    video.pause();
    state.layer = "motor";
    renderDistribution();
    renderCandidate(button.dataset.action);
  }
});
const tabs = [...document.querySelectorAll("[data-episode]")];
tabs.forEach((button, index) => {
  button.addEventListener("click", () => loadEpisode(button.dataset.episode));
  button.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      const next = tabs[(index + 1) % tabs.length];
      next.focus();
      next.click();
    }
  });
});
$("inspect-request").addEventListener("click", () => {
  if (!state.data) return;
  video.pause();
  const call = layerCall(state.data, selectedStep(), state.layer);
  $("dialog-title").textContent =
    `${label(state.layer)} / decision ${pad(call.step + 1)}`;
  $("dialog-meta").textContent =
    `${call.response.model} · ${Math.round(call.latency_s * 1000)} ms · ${call.response.usage.input_tokens} input tokens`;
  $("request-json").textContent = JSON.stringify(call.request, null, 2);
  $("response-json").textContent = JSON.stringify(call.response, null, 2);
  $("request-dialog").showModal();
});
$("close-dialog").addEventListener("click", () => $("request-dialog").close());
$("request-dialog").addEventListener("click", (event) => {
  if (event.target === $("request-dialog")) {
    const box = $("request-dialog").getBoundingClientRect();
    if (
      event.clientX < box.left ||
      event.clientX > box.right ||
      event.clientY < box.top ||
      event.clientY > box.bottom
    )
      $("request-dialog").close();
  }
});
document.addEventListener("keydown", (event) => {
  if (
    $("request-dialog").open ||
    event.target.closest("button,a,input,select,textarea")
  )
    return;
  if (event.code === "Space") {
    event.preventDefault();
    togglePlay();
  }
  if (event.code === "ArrowLeft") {
    event.preventDefault();
    jump(state.index - 1);
  }
  if (event.code === "ArrowRight") {
    event.preventDefault();
    jump(state.index + 1);
  }
});
loadEpisode("microwave");
