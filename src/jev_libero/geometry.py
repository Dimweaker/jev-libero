"""Unsigned distance between MuJoCo collision shapes, using independent FCL.

MuJoCo 3.5.0 native CCD can report zero for separated convex pairs. Do not
use that query or replace suspicious zeros with guessed distances. Construct
the same primitive / mesh convex hull shapes and query them without changing
the live simulator's model or collision solver. Penetration has gap zero;
actual force-bearing contact remains measured by MuJoCo separately.
"""

import fcl
import mujoco
import numpy as np
from scipy.spatial import ConvexHull


def collision_shape(model, g):
    kind = int(model.geom_type[g])
    size = model.geom_size[g]
    types = mujoco.mjtGeom
    if kind == types.mjGEOM_BOX:
        return fcl.Box(*(2 * size))
    if kind == types.mjGEOM_SPHERE:
        return fcl.Sphere(size[0])
    if kind == types.mjGEOM_CAPSULE:
        return fcl.Capsule(size[0], 2 * size[1])
    if kind == types.mjGEOM_CYLINDER:
        return fcl.Cylinder(size[0], 2 * size[1])
    if kind == types.mjGEOM_ELLIPSOID:
        return fcl.Ellipsoid(*size)
    if kind == types.mjGEOM_MESH:
        mesh = int(model.geom_dataid[g])
        start = int(model.mesh_vertadr[mesh])
        count = int(model.mesh_vertnum[mesh])
        vertices = np.array(model.mesh_vert[start : start + count], dtype=np.float64)
        hull = ConvexHull(vertices)
        faces = []
        for triangle, equation in zip(hull.simplices, hull.equations):
            a, b, c = map(int, triangle)
            if (
                np.dot(np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a]), equation[:3])
                < 0
            ):
                b, c = c, b
            faces.extend((3, a, b, c))
        return fcl.Convex(vertices, len(hull.simplices), np.asarray(faces, dtype=np.int32))
    raise ValueError(f"Unsupported collision distance geometry type {kind}, geom {g}")


class GeometryGap:
    def __init__(self, model, left, right):
        self.pairs = [
            (g, o)
            for g in left
            for o in right
            if (model.geom_contype[g] & model.geom_conaffinity[o])
            or (model.geom_contype[o] & model.geom_conaffinity[g])
        ]
        if not self.pairs:
            raise ValueError("No collision-enabled geometry pairs for target approach")
        self.objects = {
            g: fcl.CollisionObject(collision_shape(model, g))
            for g in set(sum(([g, o] for g, o in self.pairs), []))
        }
        self.request = fcl.DistanceRequest(enable_nearest_points=True, enable_signed_distance=True)

    def distances(self, data):
        # Refresh from actual MuJoCo poses every call, including after snapshot
        # restore; FCL transforms are derived caches, never independent state.
        for g, obj in self.objects.items():
            obj.setTransform(
                fcl.Transform(
                    np.array(data.geom_xmat[g]).reshape(3, 3), np.array(data.geom_xpos[g])
                )
            )
        values = {}
        for g, o in self.pairs:
            result = fcl.DistanceResult()
            distance = float(fcl.distance(self.objects[g], self.objects[o], self.request, result))
            if not np.isfinite(distance):
                raise RuntimeError(f"Nonfinite geometry distance: {(g, o)}")
            # Signed distance uses one interface for separation and penetration.
            # Combining unsigned -1 with a separate collision predicate is
            # inconsistent at numerical contact boundaries in FCL.
            witness = float(
                np.linalg.norm(np.asarray(result.nearest_points[1]) - result.nearest_points[0])
            )
            if abs(witness - abs(distance)) > 1e-6:
                raise RuntimeError(
                    f"Inconsistent distance and witnesses: {(g, o)}, {distance}, {witness}"
                )
            values[g, o] = max(0.0, distance)
        return values

    def minimum_mm(self, data):
        return min(self.distances(data).values()) * 1000
