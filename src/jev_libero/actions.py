"""The shared 27-input vocabulary. No task-specific skills or action sequences."""

ACTIONS = {}
for axis, name in enumerate(("x", "y", "z")):
    for mm in (-40, -10, -3, 3, 10, 40):
        ACTIONS[f"{name}{mm:+d}mm"] = {
            "axis": axis,
            "mm": mm,
            "description": f"Move gripper {mm:+d} millimeters along WORLD {name}; hold orientation and finger command.",
        }
for axis, name in enumerate(("x", "y", "z")):
    for deg in (-10, 10):
        ACTIONS[f"rotate_{name}{deg:+d}deg"] = {
            "rot_axis": axis,
            "deg": deg,
            "description": f"Rotate gripper {deg:+d} degrees about WORLD {name}; hold position and finger command.",
        }
for name, description in (
    ("open", "Open gripper fingers; hold position and orientation."),
    ("close", "Close gripper fingers; hold position and orientation."),
    ("hold", "Hold pose and current finger command."),
):
    ACTIONS[name] = {"description": description}
