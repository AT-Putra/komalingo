"""Reading an HTTP body without letting the read become the failure.

Extracted from check_package after check_api was found to have the identical
defect independently: catch HTTPError, call e.read() inside the except clause,
and a child that has stopped writing turns a plain 500 into a TimeoutError
raised from inside exception handling. That escapes the helper, escapes run(),
and replaces every remaining assert in the file with a stack trace naming
urllib instead of the bug.

Two checks hit this the same way, so it lives here rather than in either.
"""

import threading

DEFAULT_BUDGET = 15.0


def read_bounded(fp, budget: float = DEFAULT_BUDGET) -> bytes:
    """Read a response body within `budget` WALL-CLOCK seconds, never raising.

    urlopen's timeout is per-recv, not a budget for the whole body: a peer that
    stops writing part-way through can hold the read for another full timeout
    before it fails. The pull therefore happens on a thread, so the budget is
    real time rather than time-between-packets, and every outcome comes back as
    bytes that describe themselves instead of as an exception.
    """
    box: dict = {}

    def pull():
        try:
            box["data"] = fp.read()
        except Exception as exc:  # noqa: BLE001 -- every failure becomes a reason
            box["error"] = exc

    puller = threading.Thread(target=pull, daemon=True)
    puller.start()
    puller.join(budget)

    if "data" in box:
        return box["data"]
    if "error" in box:
        exc = box["error"]
        return f"<body unreadable: {type(exc).__name__}: {exc}>".encode()
    return f"<body did not arrive within {budget:.0f}s; the peer stopped writing>".encode()
