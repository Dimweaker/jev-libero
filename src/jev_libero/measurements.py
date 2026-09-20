"""Declarative, read-only measurements shared by all manipulation tasks.

Only declared measurements are evaluated. Dependencies and geometry are cached
within a read; initial references are captured once, never advanced by previews.
"""

import json

import numpy as np

KINDS = {
    "joint_position",
    "positions",
    "bounds_mm",
    "center_mm",
    "pair_center_mm",
    "axis",
    "gap_mm",
    "span_mm",
    "contact_groups",
    "external_contacts",
    "external_contact_count",
    "expression",
    "initial",
}


def references(node):
    if isinstance(node, dict):
        if "ref" in node:
            yield node["ref"]
        else:
            for value in node.values():
                yield from references(value)
    elif isinstance(node, list):
        for value in node:
            yield from references(value)


def dependencies(spec):
    if spec["kind"] == "initial":
        return [spec["source"]]
    if spec["kind"] == "span_mm":
        return [spec["axis"]]
    if spec["kind"] == "expression":
        refs = list(references(spec["value"]))
        if any(not r.startswith("raw.") for r in refs):
            raise ValueError("Measurement expressions may only reference raw measurements")
        return [r.split(".")[1] for r in refs]
    return []


def validate_measurements(specs):
    from .config import validate_expression

    required = {
        "positions": {"entity", "names"},
        "bounds_mm": {"entity"},
        "center_mm": {"entity"},
        "pair_center_mm": {"left", "right"},
        "axis": {"left", "right"},
        "gap_mm": {"left", "right"},
        "span_mm": {"entity", "axis"},
        "contact_groups": {"entity", "groups"},
        "external_contacts": {"entity", "exclude"},
        "external_contact_count": {"entity", "exclude"},
        "expression": {"value"},
        "initial": {"source"},
        "joint_position": set(),
    }
    for name, spec in specs.items():
        kind = spec.get("kind")
        if not name or "." in name or kind not in KINDS:
            raise ValueError(f"Invalid measurement: {name}: {spec}")
        allowed = required[kind] | {"kind"}
        if kind in ("contact_groups", "external_contacts", "external_contact_count"):
            allowed.add("min_normal_force_N")
        if set(spec) - allowed or required[kind] - set(spec):
            raise ValueError(f"Invalid measurement arguments: {name}")
        if kind == "expression":
            validate_expression(spec["value"])
        selectors = []
        if kind in (
            "bounds_mm",
            "center_mm",
            "span_mm",
            "contact_groups",
            "external_contacts",
            "external_contact_count",
        ):
            selectors.append(spec["entity"])
        if kind in ("pair_center_mm", "axis", "gap_mm"):
            selectors.extend([spec["left"], spec["right"]])
        if kind == "contact_groups":
            selectors.extend(spec["groups"].values())
        if kind in ("external_contacts", "external_contact_count"):
            selectors.extend(spec["exclude"])
        for selector in selectors:
            if not isinstance(selector, dict) or set(selector) not in ({"object"}, {"group"}):
                raise ValueError(f"Invalid geometry selector: {selector}")
            if "group" in selector and selector["group"] not in (
                "target",
                "gripper",
                "left_fingerpad",
                "right_fingerpad",
            ):
                raise ValueError(f"Unknown geometry group: {selector['group']}")
        if kind == "positions" and spec["entity"] not in ("body", "site"):
            raise ValueError("Position entity must be body or site")
    visited, active = set(), set()

    def visit(name):
        if name not in specs:
            raise ValueError(f"Unknown measurement dependency: {name}")
        if name in active:
            raise ValueError(f"Measurement dependency cycle at {name}")
        if name in visited:
            return
        active.add(name)
        for dependency in dependencies(specs[name]):
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in specs:
        visit(name)


class Measurements:
    def __init__(self, world):
        self.world = world
        binding = world.config["binding"]
        # Compatibility adapter for published schema-1 records. New tasks declare
        # measurements explicitly, including an empty map when none are needed.
        self.specs = world.config.get(
            "measurements",
            {
                "joint_position": {"kind": "joint_position"},
                "body_positions": {
                    "kind": "positions",
                    "entity": "body",
                    "names": binding.get("bodies", {}),
                },
                "site_positions": {
                    "kind": "positions",
                    "entity": "site",
                    "names": binding.get("sites", {}),
                },
            },
        )
        validate_measurements(self.specs)
        self.vertices = {}
        self.entities = {}
        self.initial = {}
        self._reset()
        for name, spec in self.specs.items():
            if spec["kind"] == "initial":
                self.get(name)

    def _reset(self):
        self.cache = {}
        self.point_cache = {}
        self.contact_cache = None

    def ids(self, selector):
        key = json.dumps(selector, sort_keys=True)
        if key not in self.entities:
            if set(selector) == {"object"}:
                obj = self.world.env.env.get_object(selector["object"])
                ids = [self.world.env.sim.model.geom_name2id(n) for n in obj.contact_geoms]
            elif set(selector) == {"group"}:
                group = selector["group"]
                ids = {
                    "target": self.world.scene.moving,
                    "gripper": self.world.gripper_geoms,
                    **self.world.scene.padgroups,
                }[group]
            else:
                raise ValueError(f"Invalid geometry selector: {selector}")
            self.entities[key] = set(ids)
        return self.entities[key]

    def points(self, selector):
        key = json.dumps(selector, sort_keys=True)
        if key not in self.point_cache:
            d = self.world.data
            rows = []
            for g in sorted(self.ids(selector)):
                if g not in self.vertices:
                    self.vertices[g] = self.world.scene.local_vertices(g)
                rows.append(self.vertices[g] @ d.geom_xmat[g].reshape(3, 3).T + d.geom_xpos[g])
            self.point_cache[key] = np.concatenate(rows)
        return self.point_cache[key]

    def contacts(self):
        if self.contact_cache is None:
            w = self.world
            self.contact_cache = []
            for i in range(w.data.ncon):
                c = w.data.contact[i]
                force = np.zeros(6)
                w.mujoco.mj_contactForce(w.model, w.data, i, force)
                self.contact_cache.append((int(c.geom1), int(c.geom2), float(force[0])))
        return self.contact_cache

    def get(self, name):
        if name in self.cache:
            return self.cache[name]
        s = self.specs[name]
        kind = s["kind"]
        w = self.world
        if kind == "initial":
            if name not in self.initial:
                self.initial[name] = self.get(s["source"])
            value = self.initial[name]
        elif kind == "expression":
            from .config import expression

            class Values:
                def __getitem__(_, key):
                    return self.get(key)

            value = expression(s["value"], {"raw": Values()})
        elif kind == "joint_position":
            value = float(w.data.qpos[w.qindex]) if w.qindex is not None else None
        elif kind == "positions":
            if s["entity"] not in ("body", "site"):
                raise ValueError("Position entity must be body or site")
            lookup = getattr(w.env.sim.model, s["entity"] + "_name2id")
            positions = w.data.xpos if s["entity"] == "body" else w.data.site_xpos
            value = {k: positions[lookup(n)].tolist() for k, n in s["names"].items()}
        elif kind in ("bounds_mm", "center_mm", "span_mm"):
            points = self.points(s["entity"])
            if kind == "span_mm":
                value = float(np.ptp(points @ np.asarray(self.get(s["axis"]))) * 1000)
            else:
                low, high = points.min(axis=0), points.max(axis=0)
                value = (
                    (np.array([low, high]) * 1000).tolist()
                    if kind == "bounds_mm"
                    else ((low + high) * 500).tolist()
                )
        elif kind in ("pair_center_mm", "axis", "gap_mm"):
            left, right = self.points(s["left"]), self.points(s["right"])
            if kind == "pair_center_mm":
                value = ((left.mean(axis=0) + right.mean(axis=0)) * 500).tolist()
            else:
                axis = right.mean(axis=0) - left.mean(axis=0)
                axis /= np.linalg.norm(axis)
                value = (
                    axis.tolist()
                    if kind == "axis"
                    else float(((right @ axis).min() - (left @ axis).max()) * 1000)
                )
        else:
            target = self.ids(s["entity"])
            threshold = s.get("min_normal_force_N", w.config["contact"]["min_normal_force_N"])
            touching = [
                (b if a in target else a, f)
                for a, b, f in self.contacts()
                if (a in target) != (b in target) and f > threshold
            ]
            if kind == "contact_groups":
                others = {g for g, _ in touching}
                value = [
                    label for label, selector in s["groups"].items() if others & self.ids(selector)
                ]
            else:
                excluded = set().union(*(self.ids(x) for x in s["exclude"]))
                external = [(g, f) for g, f in touching if g not in excluded]
                value = (
                    len(external)
                    if kind == "external_contact_count"
                    else [
                        {"other": w.env.sim.model.geom_id2name(g), "normal_force_N": f}
                        for g, f in external
                    ]
                )
        self.cache[name] = value
        return value

    def read(self):
        self._reset()
        return {name: self.get(name) for name in self.specs}
