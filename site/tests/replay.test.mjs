import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import {
  stepAt,
  frameAt,
  layerCall,
  distribution,
  actionState,
  project,
  label,
} from "../replay.js";

const root = new URL("../../", import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, root), "utf8"));
const lines = (path) =>
  gunzipSync(readFileSync(new URL(path, root)))
    .toString()
    .trim()
    .split("\n")
    .map(JSON.parse);

for (const id of ["microwave", "top-drawer"]) {
  const data = read(`_site/data/${id}.json`);
  test(`${id}: complete, contiguous simulation-time coverage`, () => {
    assert.equal(data.steps.length, data.summary.decisions);
    assert.equal(data.samples.length, data.summary.sim_steps + 1);
    assert.equal(data.duration, data.summary.sim_steps / 20);
    assert.equal(data.actions.length, 27);
    assert.equal(data.steps[0].start, 0);
    for (const [i, step] of data.steps.entries()) {
      assert.equal(stepAt(data, step.start), i);
      assert.equal(stepAt(data, step.end - 0.00001), i);
      if (i) assert.equal(step.start, data.steps[i - 1].end);
    }
    assert.equal(stepAt(data, data.duration), data.steps.length - 1);
    assert.equal(frameAt(data, 0), 1);
    assert.equal(frameAt(data, 0.05), 2);
    assert.equal(frameAt(data, data.duration), data.summary.sim_steps);
  });
  test(`${id}: actual API payloads and retained layers`, () => {
    const calls = lines(`examples/records/${data.record}/api.jsonl.gz`);
    assert.deepEqual(data.calls, calls);
    for (const step of data.steps) {
      for (const layer of ["intent", "strategy", "motor"]) {
        const call = layerCall(data, step, layer);
        assert.ok(call.step <= step.index);
        assert.equal(step.fresh.includes(layer), call.step === step.index);
        const rows = distribution(data, step, layer);
        assert.equal(rows.filter((row) => row.chosen).length, 1);
        assert.ok(
          rows.every((row) => row.probability >= 0 && row.probability <= 1),
        );
        assert.equal(
          rows.find((row) => row.chosen).name,
          step[layer === "motor" ? "choice" : layer],
        );
      }
    }
  });
  test(`${id}: measured boundaries and candidate membership`, () => {
    const traces = lines(`examples/records/${data.record}/trace.jsonl.gz`);
    for (const [index, step] of data.steps.entries()) {
      assert.ok(
        Math.abs(
          data.samples[step.startFrame] - traces[index].before_task_value,
        ) < 1e-8,
      );
      assert.ok(
        Math.abs(data.samples[step.endFrame] - traces[index].after_task_value) <
          1e-8,
      );
      assert.equal(actionState(step, step.choice), "selected");
      assert.ok(step.eligible.includes(step.choice));
      assert.deepEqual(
        [...step.eligible].sort(),
        Object.keys(
          layerCall(data, step, "motor").request.questions.motor.criteria,
        ).sort(),
      );
      assert.equal(Object.keys(step.effects).length, 27);
    }
  });
}
test("spatial projection preserves aspect and handles stationary points", () => {
  const p = project(
    [
      [0, 0, 0],
      [10, 0, 10],
    ],
    "xz",
  );
  assert.equal(p[1][0] - p[0][0], p[0][1] - p[1][1]);
  assert.deepEqual(project([[0, 0, 0]], "xz"), [[150, 80]]);
});
test("human-readable action and strategy labels", () => {
  assert.equal(
    label("no_target_contact__translation"),
    "Free space · Translate",
  );
  assert.equal(label("x-40mm"), "x−40 mm");
});
