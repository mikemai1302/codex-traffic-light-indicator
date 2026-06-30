from __future__ import annotations

import sys

from traffic_light_common import VALID_STATUSES, read_status, status_label, write_status


def main() -> int:
    # 这个脚本用于手动测试灯色，例如：
    # python set_status.py red / yellow / green
    status = (sys.argv[1] if len(sys.argv) > 1 else "green").lower().strip()
    if status not in VALID_STATUSES:
        print("Usage: python set_status.py red|yellow|green")
        return 2
    language = read_status().get("language")
    # 写入状态时沿用当前语言，这样右键切到英文后测试脚本也显示英文。
    data = write_status(status, status_label(status, language), heartbeat=True)
    print(f"status={data['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
