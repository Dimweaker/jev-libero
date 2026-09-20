"""Configured LIBERO forward model with reversible full controller snapshots.
No task policy or model calls. Branches execute the same 27 atomic inputs as live.
"""

import copy
import math
import random

import numpy as np

from .actions import ACTIONS
from .config import expression, load_task, project
from .environment import load_libero


class Snapshot:
    def __init__(self, world):
        self.world = world
        e = world.env.env
        r = e.robots[0]
        self.data = world.mujoco.MjData(world.model)
        world.mujoco.mj_copyData(self.data, world.model, world.data)
        self.controller = copy.deepcopy(
            {k: v for k, v in r.controller.__dict__.items() if k != "sim"}
        )
        self.robot = copy.deepcopy(
            {k: v for k, v in r.__dict__.items() if k.startswith("recent_") or k == "torques"}
        )
        self.gripper = copy.deepcopy(r.gripper.current_action)
        self.clock = {
            k: copy.deepcopy(getattr(e, k)) for k in ("cur_time", "timestep", "done", "_obs_cache")
        }
        self.observables = {k: copy.deepcopy(v.__dict__) for k, v in e._observables.items()}
        self.obs = copy.deepcopy(world.obs)
        self.rng = np.random.get_state()
        self.py_rng = random.getstate()

    def restore(self):
        w = self.world
        e = w.env.env
        r = e.robots[0]
        w.mujoco.mj_copyData(w.data, w.model, self.data)
        sim = r.controller.sim
        r.controller.__dict__.clear()
        r.controller.__dict__.update(copy.deepcopy(self.controller))
        r.controller.sim = sim
        for k, v in self.robot.items():
            setattr(r, k, copy.deepcopy(v))
        r.gripper.current_action = copy.deepcopy(self.gripper)
        for k, v in self.clock.items():
            setattr(e, k, copy.deepcopy(v))
        for k, v in self.observables.items():
            e._observables[k].__dict__.clear()
            e._observables[k].__dict__.update(copy.deepcopy(v))
        w.obs = copy.deepcopy(self.obs)
        np.random.set_state(self.rng)
        random.setstate(self.py_rng)


class World:
    def __init__(
        self,
        init_index=0,
        render=False,
        seed=0,
        task_config=None,
        libero_root=None,
        config_dir=None,
    ):
        benchmark, ControlEnv, assets, self.config_dir = load_libero(libero_root, config_dir)
        import mujoco

        from .geometry import GeometryGap
        from .scene import CollisionScene

        self.mujoco = mujoco
        self.render_enabled = render
        self.config = load_task(task_config)
        binding = self.config["binding"]
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        suite_name, task_name, obj, joint = (
            binding[k] for k in ("suite", "task", "object", "joint_suffix")
        )
        suite = benchmark.get_benchmark_dict()[suite_name]()
        idx = next(i for i in range(suite.n_tasks) if suite.get_task(i).name == task_name)
        task = suite.get_task(idx)
        self.task = task.language
        self.env = ControlEnv(
            bddl_file_name=str(assets / "bddl_files" / task.problem_folder / task.bddl_file),
            use_camera_obs=False,
            has_renderer=False,
            has_offscreen_renderer=render,
            camera_heights=384,
            camera_widths=384,
        )
        self.env.seed(seed)
        self.env.reset()
        self.obs = self.env.set_init_state(suite.get_task_init_states(idx)[init_index])
        for _ in range(10):
            self.obs, _, _, _ = self.env.step([0, 0, 0, 0, 0, 0, -1])
        self.scene = CollisionScene(self.env, obj, joint)
        self.model = self.env.sim.model._model
        self.data = self.env.sim.data._data
        if self.env.env.tracking_object_states_change:
            raise RuntimeError(
                "Snapshot contract currently excludes tasks with model-mutating switch/light state"
            )
        self.jid = self.scene.jid
        if self.jid is None:
            self.scene.moving = self.scene.geoms
        if binding["success"] != "libero":
            raise ValueError("Only the original LIBERO success predicate is supported")
        self.gripper_geoms = [
            i
            for i in range(self.model.ngeom)
            if "gripper" in (self.env.sim.model.geom_id2name(i) or "")
            and (self.model.geom_contype[i] or self.model.geom_conaffinity[i])
        ]
        self.qindex = int(self.model.jnt_qposadr[self.jid]) if self.jid is not None else None
        self.geometry_gap = GeometryGap(self.model, self.gripper_geoms, self.scene.moving)
        from .measurements import Measurements

        self.measurements = Measurements(self)

    def features(self):
        contacts = []
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            a, b = int(c.geom1), int(c.geom2)
            hand = a if a in self.gripper_geoms else b if b in self.gripper_geoms else None
            if hand is None:
                continue
            other = b if hand == a else a
            if other in self.gripper_geoms:
                continue
            f = np.zeros(6)
            self.mujoco.mj_contactForce(self.model, self.data, i, f)
            rules = self.config["contact"]
            if f[0] <= rules["min_normal_force_N"]:
                continue
            hand_name = self.env.sim.model.geom_id2name(hand)
            other_name = self.env.sim.model.geom_id2name(other)
            part = next(
                (rule["name"] for rule in rules["parts"] if rule["contains"] in hand_name),
                rules["default_part"],
            )
            contacts.append(
                {
                    "hand": hand_name,
                    "part": part,
                    "other": other_name,
                    "moving_target": other in self.scene.moving,
                    "obstacle": other not in self.scene.moving
                    and other_name not in rules["allowed_other_geoms"],
                    "normal_force_N": float(f[0]),
                    "position_mm": (np.array(c.pos) * 1000).tolist(),
                }
            )
        distance = self.geometry_gap.minimum_mm(self.data)
        left = self.scene.points(self.scene.padgroups["left_fingerpad"])
        right = self.scene.points(self.scene.padgroups["right_fingerpad"])
        axis = right.mean(axis=0) - left.mean(axis=0)
        axis /= np.linalg.norm(axis)
        gap = max(0.0, float((right @ axis).min() - (left @ axis).max())) * 1000
        target = [c for c in contacts if c["moving_target"]]
        obstacles = [c for c in contacts if c["obstacle"]]
        raw = self.measurements.read()
        return {
            **project(self.config["features"], {"raw": raw}),
            "eef_mm": (self.obs["robot0_eef_pos"] * 1000).tolist(),
            "eef_rotation_matrix": self.data.site_xmat[self.env.robots[0].eef_site_id]
            .reshape(3, 3)
            .tolist(),
            "finger_gap_mm": gap,
            "moving_contact": bool(target),
            "obstacle_contact": bool(obstacles),
            "contact_modes": sorted(set(c["part"] for c in target)),
            "target_force_N": sum(c["normal_force_N"] for c in target),
            "obstacle_force_N": sum(c["normal_force_N"] for c in obstacles),
            "distance_to_moving_geometry_mm": distance,
            "contacts": contacts,
            "success": bool(self.env.check_success()),
        }

    def execute(self, name, grip=-1.0, record=False):
        spec = ACTIONS[name]
        target = self.obs["robot0_eef_pos"].copy()
        rotation = np.zeros(3)
        if "axis" in spec:
            target[spec["axis"]] += spec["mm"] / 1000
        if "rot_axis" in spec:
            rotation[spec["rot_axis"]] = math.radians(spec["deg"])
        if name in ("open", "close"):
            grip = -1.0 if name == "open" else 1.0
        commands = []
        states = []
        frames = []
        feature_trace = []
        peak_obstacle = 0.0
        obstacle_pairs = set()
        for k in range(8):
            a = np.r_[
                np.clip((target - self.obs["robot0_eef_pos"]) / 0.05, -1, 1),
                rotation / 0.5 if k == 0 else np.zeros(3),
                grip,
            ]
            if record:
                states.append(self.env.sim.get_state().flatten().copy())
            commands.append(a.copy())
            self.obs, _, _, _ = self.env.step(a)
            features = self.features()
            if record and self.config.get("record_features"):
                feature_trace.append(
                    {
                        "sim_time_s": float(self.data.time),
                        **{key: features[key] for key in self.config["record_features"]},
                    }
                )
            peak_obstacle = max(peak_obstacle, features["obstacle_force_N"])
            obstacle_pairs.update(
                (c["hand"], c["other"]) for c in features["contacts"] if c["obstacle"]
            )
            if record and self.render_enabled:
                frames.append(
                    self.env.sim.render(width=384, height=384, camera_name="agentview")[::-1].copy()
                )
            if features["success"]:
                break
        return {
            "features": features,
            "grip": grip,
            "steps": len(commands),
            "commands": commands,
            "states": states,
            "frames": frames,
            "feature_trace": feature_trace,
            "peak_obstacle_force_N": peak_obstacle,
            "obstacle_pairs_seen": sorted(obstacle_pairs),
        }

    def predict_all(self, grip=-1.0):
        snapshot = Snapshot(self)
        before = self.features()
        predictions = {}
        try:
            for name in ACTIONS:
                snapshot.restore()
                result = self.execute(name, grip)
                f = result["features"]
                predictions[name] = {
                    "after": f,
                    **project(self.config["predictions"], {"before": before, "after": f}),
                    "geometry_approach_mm": before["distance_to_moving_geometry_mm"]
                    - f["distance_to_moving_geometry_mm"],
                    "eef_displacement_mm": float(
                        np.linalg.norm(np.array(f["eef_mm"]) - before["eef_mm"])
                    ),
                    "gap_change_mm": f["finger_gap_mm"] - before["finger_gap_mm"],
                    "peak_obstacle_force_N": result["peak_obstacle_force_N"],
                    "obstacle_pairs_seen": result["obstacle_pairs_seen"],
                    "steps": result["steps"],
                    "sim_state_after": self.env.sim.get_state().flatten().tolist(),
                }
        finally:
            snapshot.restore()
        return before, predictions

    def two_step_witnesses(self, grip=-1.0):
        """Evaluate safe two-primitive branches; return witnesses, never execute a plan."""
        from .policy import blocked_pairs, contracts

        root = Snapshot(self)
        before = self.features()
        witnesses = {}
        evaluations = 0
        initial_obstacles = blocked_pairs(before)
        rules = self.config["contact"]
        try:
            for first in ACTIONS:
                root.restore()
                one = self.execute(first, grip)
                if (
                    rules["reject_new_obstacles"]
                    and set(one["obstacle_pairs_seen"]) - initial_obstacles
                ):
                    continue
                if rules["require_obstacle_free_endpoint"] and one["features"]["obstacle_contact"]:
                    continue
                _, seconds = self.predict_all(one["grip"])
                best = None
                best_score = None
                for second, p in seconds.items():
                    evaluations += 1
                    end = p["after"]
                    combined = {
                        **p,
                        **project(self.config["predictions"], {"before": before, "after": end}),
                        "geometry_approach_mm": before["distance_to_moving_geometry_mm"]
                        - end["distance_to_moving_geometry_mm"],
                        "obstacle_pairs_seen": sorted(
                            set(one["obstacle_pairs_seen"])
                            | set(map(tuple, p["obstacle_pairs_seen"]))
                        ),
                        "peak_obstacle_force_N": max(
                            one["peak_obstacle_force_N"], p["peak_obstacle_force_N"]
                        ),
                    }
                    goals, _ = contracts(
                        before, {first: combined}, collision_aware=True, task_config=self.config
                    )
                    if not goals:
                        continue
                    # Choose a witness for each first input, NOT the executed
                    # first input. Jev later chooses among those first inputs.
                    context = {
                        "after": end,
                        "before": before,
                        "p": combined,
                        "effects": {k: k in goals for k in self.config["contracts"]},
                    }
                    score = tuple(
                        expression(rule, context) for rule in self.config["search"]["score"]
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                        best = {
                            "second_input": second,
                            "net_progress": combined[self.config["search"]["progress_field"]],
                            "net_gap_reduction_mm": combined["geometry_approach_mm"],
                            "terminal_contact": end["moving_contact"],
                            "terminal_success": end["success"],
                            "peak_obstacle_force_N": combined["peak_obstacle_force_N"],
                            "witnessed_effects": list(goals),
                        }
                if best is not None:
                    witnesses[first] = best
        finally:
            root.restore()
        return witnesses, evaluations

    def close(self):
        self.env.close()
