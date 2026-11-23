"""
看板数据服务
口径：
- 在途 = acdate IS NULL
- 待提柜 = stcsdate IS NULL AND acdate 非空
- 本周/本月预计到港按 eta
- 超期未到 = eta < 今天 AND acdate IS NULL
"""
from datetime import date, timedelta
from typing import Dict, Any, List

from app.core.database import fetch_all, fetch_one
from app.services.container_service import _row_to_dict, STATUS_SQL, DELAY_SQL


def _week_range(today: date) -> tuple:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def get_dashboard() -> Dict[str, Any]:
    today = date.today()
    ws, we = _week_range(today)
    month_start = today.replace(day=1)

    # 总在途箱量
    total_in_transit = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers WHERE acdate IS NULL"
    )["c"]
    yesterday_in_transit = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers "
        "WHERE acdate IS NULL AND DATE(createtime)<=%s",
        (str(today - timedelta(days=1)),),
    )["c"]

    # 本周预计到港
    week_total = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers WHERE eta BETWEEN %s AND %s",
        (str(ws), str(we) + " 23:59:59"),
    )["c"]
    week_arrived = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers "
        "WHERE eta BETWEEN %s AND %s AND acdate IS NOT NULL",
        (str(ws), str(we) + " 23:59:59"),
    )["c"]

    # 本月预计到港
    month_total = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers WHERE eta>=%s",
        (str(month_start),),
    )["c"]
    month_arrived = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers "
        "WHERE eta>=%s AND acdate IS NOT NULL",
        (str(month_start),),
    )["c"]

    # 超期未到预警 + 平均延误
    overdue = fetch_one("""
        SELECT COUNT(*) AS c,
               AVG(DATEDIFF(CURDATE(), eta)) AS avg_delay
        FROM transit_containers
        WHERE acdate IS NULL AND eta < CURDATE()
    """)
    overdue_count = overdue["c"]
    avg_delay = round(float(overdue["avg_delay"]), 1) if overdue["avg_delay"] else 0

    # 待提柜
    pending_pickup = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers "
        "WHERE acdate IS NOT NULL AND stcsdate IS NULL"
    )["c"]
    picked_up = fetch_one(
        "SELECT COUNT(*) AS c FROM transit_containers "
        "WHERE acdate IS NOT NULL AND stcsdate IS NOT NULL"
    )["c"]

    cards = {
        "total_in_transit": {
            "value": total_in_transit,
            "change": total_in_transit - yesterday_in_transit,
        },
        "week_eta": {
            "value": week_total,
            "arrived": week_arrived,
            "remaining": week_total - week_arrived,
        },
        "month_eta": {
            "value": month_total,
            "arrived": month_arrived,
            "rate": round(month_arrived / month_total * 100) if month_total else 0,
        },
        "overdue": {"value": overdue_count, "avg_delay": avg_delay},
        "pending_pickup": {"value": pending_pickup, "picked": picked_up},
    }

    # 本周每天到货分布
    week_dist = fetch_all("""
        SELECT DAYNAME(eta) AS d, COUNT(*) AS c
        FROM transit_containers
        WHERE eta BETWEEN %s AND %s
        GROUP BY DAYNAME(eta)
    """, (str(ws), str(we) + " 23:59:59"))
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    dist_map = {r["d"]: r["c"] for r in week_dist}
    week_distribution = [
        {"day": label, "count": dist_map.get(name, 0)}
        for name, label in zip(day_names, day_labels)
    ]

    # 在途明细（前若干条）
    cols = (
        "*, (SELECT brandname FROM mdmbasedb.brand b WHERE b.brandid="
        "transit_containers.brand AND b.dbsplitcode=1 LIMIT 1) AS brand_name, "
        f"{STATUS_SQL}, {DELAY_SQL} "
    )
    detail_rows = fetch_all(
        f"SELECT {cols} FROM transit_containers "
        "WHERE acdate IS NULL ORDER BY eta ASC LIMIT 20"
    )
    detail = [_row_to_dict(r) for r in detail_rows]

    # 近30天到货趋势（预计 vs 实际）
    trend = fetch_all("""
        SELECT d, SUM(plan) AS plan, SUM(actual) AS actual FROM (
            SELECT DATE(eta) AS d, COUNT(*) AS plan, 0 AS actual
            FROM transit_containers WHERE eta>=DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(eta)
            UNION ALL
            SELECT DATE(acdate) AS d, 0 AS plan, COUNT(*) AS actual
            FROM transit_containers WHERE acdate>=DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(acdate)
        ) t GROUP BY d ORDER BY d
    """)
    trend_data = [
        {
            "date": str(r["d"]),
            "plan": int(r["plan"] or 0),
            "actual": int(r["actual"] or 0),
        }
        for r in trend
    ]

    # 近7日在途箱量变化（按 createtime 累计未关单）
    seven_days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        c = fetch_one(
            "SELECT COUNT(*) AS c FROM transit_containers "
            "WHERE acdate IS NULL AND DATE(createtime)<=%s",
            (str(d),),
        )["c"]
        seven_days.append({"date": str(d), "count": c})

    return {
        "cards": cards,
        "week_distribution": week_distribution,
        "detail": detail,
        "trend": trend_data,
        "in_transit_7days": seven_days,
        "alerts": [r for r in detail if r.get("status") in ("延误", "待提柜")][:6],
    }
