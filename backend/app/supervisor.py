"""Local operational controls for the paper-trading service."""


def status(kill_switch_active: bool) -> dict:
    return {"status": "stopped" if kill_switch_active else "healthy", "kill_switch_active": kill_switch_active, "mode": "paper"}
