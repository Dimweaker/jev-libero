"""Independent analytic geometry checks; optional robot dependencies, no API."""

import numpy as np
import pytest

pytestmark = pytest.mark.simulation


@pytest.mark.parametrize(
    "kind,size",
    [
        ("box", ".1 .1 .1"),
        ("sphere", ".1"),
        ("capsule", ".1 .2"),
        ("cylinder", ".1 .2"),
        ("ellipsoid", ".1 .2 .3"),
    ],
)
def test_separation_intersection_and_contact_boundary(kind, size):
    import mujoco

    from jev_libero.geometry import GeometryGap

    model = mujoco.MjModel.from_xml_string(
        f'<mujoco><worldbody><geom type="{kind}" size="{size}"/>'
        f'<geom type="{kind}" size="{size}" pos="1 0 0"/></worldbody></mujoco>'
    )
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    query = GeometryGap(model, [0], [1])
    assert query.minimum_mm(data) == pytest.approx(800.0, abs=0.01)
    for offset in (-0.15, -1e-5, 0.0, 1e-5):
        model.geom_pos[1, 0] = 0.2 + offset
        mujoco.mj_forward(model, data)
        assert query.minimum_mm(data) == pytest.approx(max(0.0, offset) * 1000, abs=0.002)


def test_distance_does_not_modify_live_solver():
    import mujoco

    from jev_libero.geometry import GeometryGap

    model = mujoco.MjModel.from_xml_string(
        '<mujoco><worldbody><geom type="box" size=".1 .1 .1"/><geom type="box" size=".1 .1 .1" pos="1 0 0"/></worldbody></mujoco>'
    )
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    settings = (int(model.opt.disableflags), int(model.opt.ccd_iterations))
    pose = data.geom_xpos.copy()
    GeometryGap(model, [0], [1]).minimum_mm(data)
    np.testing.assert_array_equal(data.geom_xpos, pose)
    assert settings == (int(model.opt.disableflags), int(model.opt.ccd_iterations))
