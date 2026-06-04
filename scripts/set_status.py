from __future__ import annotations

import sys

from traffic_light_common import STATUS_LABELS, VALID_STATUSES, write_status


def main() -> int:
    status = (sys.argv[1] if len(sys.argv) > 1 else "green").lower().strip()
    if status not in VALID_STATUSES:
        print("Usage: python set_status.py red|yellow|green")
        return 2
    data = write_status(status, STATUS_LABELS[status], heartbeat=True)
    print(f"status={data['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
