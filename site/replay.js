// Pure replay helpers. The video clock is the single source of playback time.
export const LAYERS = ["intent", "strategy", "motor"];
export const COLORS = {
  approach_target: "#d4c7ed",
  establish_contact: "#efb3dc",
  advance_target: "#ddf597",
  release_contact: "#f4d4b0",
  reposition: "#f4d4b0",
};
export const LAYER_COLORS = {
  intent: "#ddf597",
  strategy: "#efb3dc",
  motor: "#d4c7ed",
};
const NAMES = {
  approach_target: "Approach target",
  establish_contact: "Establish contact",
  advance_target: "Advance target",
  release_contact: "Release contact",
  reposition: "Reposition",
  no_target_contact: "Free space",
  fingerpad: "Fingerpad",
  finger: "Finger",
  hand: "Hand",
  translation: "Translate",
  rotation: "Rotate",
  gripper: "Gripper",
};
export function label(value) {
  if (NAMES[value]) return NAMES[value];
  if (value.includes("__")) return value.split("__").map(label).join(" · ");
  if (value.includes("+") && !/^(?:rotate_)?[xyz][+-]/.test(value))
    return value.split("+").map(label).join(" + ");
  return value
    .replace(/^rotate_/, "↻ ")
    .replace(/deg$/, "°")
    .replace(/mm$/, " mm")
    .replace(/_/g, " ")
    .replace(/-/g, "−");
}
export function compactAction(value) {
  return value
    .replace("rotate_", "↻")
    .replace("deg", "°")
    .replace("mm", "")
    .replace("-", "−");
}
export function stepAt(data, time) {
  const index = data.steps.findIndex((step) => time < step.end);
  return index < 0 ? data.steps.length - 1 : index;
}
export function frameAt(data, time) {
  // Render frame zero was captured AFTER the first 20 Hz environment step.
  return Math.min(
    data.summary.sim_steps,
    Math.max(1, Math.floor(time * data.fps + 1e-7) + 1),
  );
}
export function layerCall(data, step, layer) {
  return data.calls[step.layers[layer]];
}
export function distribution(data, step, layer) {
  const call = layerCall(data, step, layer);
  const answer = call.response.answers[layer];
  return Object.entries(answer.probabilities)
    .map(([name, probability]) => ({
      name,
      probability,
      chosen: name === answer.choice,
    }))
    .sort((a, b) => b.probability - a.probability);
}
export function actionState(step, action) {
  if (action === step.choice) return "selected";
  if (step.eligible.includes(action)) return "offered";
  if (step.feasible.includes(action)) return "feasible";
  return "excluded";
}
export function project(points, axes, width = 300, height = 160, padding = 22) {
  const a = "xyz".indexOf(axes[0]),
    b = "xyz".indexOf(axes[1]);
  const xs = points.map((p) => p[a]),
    ys = points.map((p) => p[b]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const scale = Math.min(
    (width - 2 * padding) / Math.max(maxX - minX, 1),
    (height - 2 * padding) / Math.max(maxY - minY, 1),
  );
  return points.map((p) => [
    width / 2 + (p[a] - (minX + maxX) / 2) * scale,
    height / 2 - (p[b] - (minY + maxY) / 2) * scale,
  ]);
}
export function polyline(points) {
  return points
    .map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(2)},${p[1].toFixed(2)}`)
    .join(" ");
}
