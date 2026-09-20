"""Task-independent Jev hierarchy over declarative physical effect contracts."""

from collections import defaultdict

from .actions import ACTIONS
from .config import expression, load_task, project


class NoFeasibleAction(RuntimeError):
    """No candidate satisfies the configured local effect contracts."""


def contact_pairs(features):
    return {(c["hand"], c["other"]) for c in features["contacts"]}


def blocked_pairs(features):
    return {
        (c["hand"], c["other"])
        for c in features["contacts"]
        if c.get("obstacle", not c["moving_target"])
    }


def contracts(before, predictions, collision_aware=False, task_config=None):
    cfg = load_task(task_config)
    rules = cfg["contact"]
    blocked = blocked_pairs(before)
    pair_groups = {"blocked": blocked, "all": contact_pairs(before)}
    release_pairs = next(
        (pair_groups[k] for k in rules["release_priority"] if pair_groups[k]), set()
    )
    pools = {k: {} for k in cfg["contracts"]}
    rejected = {}
    thresholds = cfg["thresholds"]["collision_aware" if collision_aware else "ordinary"]
    for name, p in predictions.items():
        after = p["after"]
        if collision_aware:
            if (
                rules["reject_new_obstacles"]
                and set(map(tuple, p["obstacle_pairs_seen"])) - blocked
            ):
                rejected[name] = "Forecast introduces non-target contact at sampled control steps."
                continue
            if rules["require_obstacle_free_endpoint"] and after["obstacle_contact"]:
                rejected[name] = "Forecast does not resolve existing non-target contact."
                continue
        context = {
            "before": before,
            "after": after,
            "p": p,
            "thresholds": thresholds,
            "released_required_contacts": bool(release_pairs)
            and not bool(release_pairs & contact_pairs(after)),
            "has_reposition_witness": bool(p.get("reposition_witness")),
        }
        eligible = [key for key, rule in cfg["contracts"].items() if expression(rule, context)]
        for key in eligible:
            pools[key][name] = p
        if not eligible:
            rejected[name] = (
                "No witnessed goal effect in this horizon; not an executable local goal for this decision."
            )
    return {k: v for k, v in pools.items() if v}, rejected


def family(name, p):
    contact = "+".join(p["after"]["contact_modes"]) or "no_target_contact"
    kind = (
        "rotation"
        if name.startswith("rotate_")
        else "finger"
        if name in ("open", "close")
        else "hold"
        if name == "hold"
        else "translation"
    )
    return contact + "__" + kind


def summary(pool, task_config=None):
    cfg = load_task(task_config)
    result = {"primitive_count": len(pool)}
    for key, spec in cfg["policy"]["summary"].items():
        values = [expression({"ref": "p." + spec["field"]}, {"p": p}) for p in pool.values()]
        if spec["reduce"] == "any":
            result[key] = any(values)
        elif spec["reduce"] == "range":
            result[key] = [round(min(values), spec["digits"]), round(max(values), spec["digits"])]
        else:
            raise ValueError(f"Unknown summary reducer: {spec}")
    witnesses = [p["reposition_witness"] for p in pool.values() if p.get("reposition_witness")]
    if witnesses:
        result["two_step_witness_progress"] = [round(w["net_progress"], 3) for w in witnesses]
        result["two_step_witness_can_finish"] = any(w["terminal_success"] for w in witnesses)
    return result


class ValidatedPolicy:
    def __init__(self, collision_aware=False, task_config=None):
        self.config = load_task(task_config)
        self.collision_aware = collision_aware
        self.intent = None
        self.strategy = None
        self.last_review = -100
        self.history = []
        self.intent_calls = 0
        self.strategy_calls = 0

    def choose(self, api, step, before, predictions):
        cfg = self.config
        policy = cfg["policy"]
        pools, rejected = contracts(before, predictions, self.collision_aware, cfg)
        if not pools:
            raise NoFeasibleAction(
                "No primitive satisfies configured effect and feasibility contracts; stopping without a fallback action"
            )
        review = self.intent not in pools or step - self.last_review >= policy["review_interval"]
        if any(self.intent != key and key in pools for key in policy["review_when_available"]):
            review = True
        if any(key in pools for key in policy["review_transitions"].get(self.intent, [])):
            review = True
        if review:
            state = {
                "task": policy["task_text"],
                **project(policy["intent_state"], {"before": before}),
                "contact": "moving target and obstacle"
                if before["moving_contact"] and before["obstacle_contact"]
                else "moving target"
                if before["moving_contact"]
                else "obstacle"
                if before["obstacle_contact"]
                else "none",
                "current_intent": self.intent,
                "recent_real_outcomes": self.history[-3:],
                "prediction_scope": policy["prediction_scope"],
            }
            options = {
                k: {"meaning": policy["intent_descriptions"][k], **summary(v, cfg)}
                for k, v in pools.items()
            }
            self.intent = api.choose(step, "intent", state, policy["intent_instructions"], options)
            self.intent_calls += 1
            self.strategy = None
            self.last_review = step
        grouped = defaultdict(dict)
        for name, p in pools[self.intent].items():
            grouped[family(name, p)][name] = p
        finish_elsewhere = (
            self.collision_aware
            and policy["review_if_finish_elsewhere"]
            and self.strategy in grouped
            and not any(p["after"]["success"] for p in grouped[self.strategy].values())
            and any(p["after"]["success"] for pool in grouped.values() for p in pool.values())
        )
        if self.strategy not in grouped or finish_elsewhere:
            self.strategy = api.choose(
                step,
                "strategy",
                {"intent": self.intent, **project(policy["strategy_state"], {"before": before})},
                policy["strategy_instructions"],
                {k: summary(v, cfg) for k, v in grouped.items()},
            )
            self.strategy_calls += 1
        candidates = grouped[self.strategy]
        options = {}
        for name, p in candidates.items():
            options[name] = {
                "input": ACTIONS[name]["description"],
                **project(policy["motor_options"], {"before": before, "after": p["after"], "p": p}),
            }
            if p.get("reposition_witness"):
                options[name]["verified_two_step_witness"] = p["reposition_witness"]
        choice = api.choose(
            step,
            "motor",
            {
                "intent": self.intent,
                "strategy": self.strategy,
                "recent_real_outcomes": self.history[-2:],
            },
            policy["motor_instructions"],
            options,
        )
        return choice, {
            "intent": self.intent,
            "strategy": self.strategy,
            "reviewed_intent": review,
            "eligible_by_intent": {k: list(v) for k, v in pools.items()},
            "eligible_motor": list(candidates),
            "rejected": rejected,
        }

    def feedback(self, choice, before, after):
        self.history.append(
            {
                "input": choice,
                **project(self.config["policy"]["feedback"], {"before": before, "after": after}),
            }
        )
