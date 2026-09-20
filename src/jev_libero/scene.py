"""Collision geometry bindings; no task policy or waypoint generation."""

from itertools import product

import mujoco
import numpy as np


class CollisionScene:
    def __init__(self, env, object_name, joint_suffix):
        self.env = env
        self.m = env.sim.model._model
        self.d = env.sim.data._data
        obj = env.env.get_object(object_name)
        self.geoms = [env.sim.model.geom_name2id(name) for name in obj.contact_geoms]
        self.padgroups = {
            key: [
                env.sim.model.geom_name2id(name)
                for name in env.robots[0].gripper.important_geoms[key]
            ]
            for key in ("left_fingerpad", "right_fingerpad")
        }
        self.vertices = {g: self.local_vertices(g) for ids in self.padgroups.values() for g in ids}
        self.jid = None
        self.moving = self.geoms
        if joint_suffix:
            matches = [
                j
                for j in range(self.m.njnt)
                if (env.sim.model.joint_id2name(j) or "").startswith(object_name)
                and (env.sim.model.joint_id2name(j) or "").endswith(joint_suffix)
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one joint for {object_name}/{joint_suffix}, found {matches}"
                )
            self.jid = matches[0]
            body = int(self.m.jnt_bodyid[self.jid])

            def descends(child):
                while child:
                    if child == body:
                        return True
                    child = int(self.m.body_parentid[child])
                return False

            self.moving = [g for g in self.geoms if descends(int(self.m.geom_bodyid[g]))]

    def local_vertices(self, g):
        """Mesh vertices or primitive bounding-box corners (for finger gap)."""
        kind = int(self.m.geom_type[g])
        size = self.m.geom_size[g]
        types = mujoco.mjtGeom
        if kind == types.mjGEOM_MESH:
            mesh = int(self.m.geom_dataid[g])
            start = int(self.m.mesh_vertadr[mesh])
            return self.m.mesh_vert[start : start + int(self.m.mesh_vertnum[mesh])].copy()
        if kind in (types.mjGEOM_BOX, types.mjGEOM_ELLIPSOID):
            extent = size
        elif kind == types.mjGEOM_CAPSULE:
            extent = np.array([size[0], size[0], size[0] + size[1]])
        elif kind == types.mjGEOM_CYLINDER:
            extent = np.array([size[0], size[0], size[1]])
        elif kind == types.mjGEOM_SPHERE:
            extent = np.repeat(size[0], 3)
        else:
            raise ValueError(f"Unsupported finger-gap geometry type: {kind}")
        return np.array(list(product([-1, 1], repeat=3))) * extent

    def points(self, ids):
        return np.concatenate(
            [
                self.vertices[g] @ self.d.geom_xmat[g].reshape(3, 3).T + self.d.geom_xpos[g]
                for g in ids
            ]
        )
