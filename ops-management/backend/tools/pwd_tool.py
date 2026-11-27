"""
账户密码维护脚本（与 ERP 一致的 SHA-256 双层链路）

用法（在 backend 目录下执行）：

    # 查看账户当前状态（只显示哈希前缀，不打印密码）
    python tools/pwd_tool.py show yjr

    # 修改密码（保留原 salt）
    python tools/pwd_tool.py set yjr 新密码

    # 修改密码并重新生成 salt
    python tools/pwd_tool.py set yjr 新密码 --new-salt

    # 校验某个密码是否能登录（不写库，用于验证）
    python tools/pwd_tool.py check yjr abcd123456

    # 批量校验明细：列出所有 status=1 且 salt 缺失的账户（无法登录的账户）
    python tools/pwd_tool.py audit

注意：
- 只处理 dbsplitcode='1' 的主库账户；
- 同 usercode 存在多条时，默认作用于 id 最小的那条，可用 --id 精确指定。
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import fetch_all, execute  # noqa: E402
from app.core.auth import hash_password, stage1_hash, verify_password  # noqa: E402


def _find(usercode: str, account_id: int | None = None):
    where = "usercode=%s AND dbsplitcode='1'"
    params = [usercode]
    if account_id is not None:
        where += " AND id=%s"
        params.append(account_id)
    return fetch_all(
        f"SELECT id, usercode, accountname, pwd, salt, status FROM ucsdb.account "
        f"WHERE {where} ORDER BY id",
        tuple(params),
    )


def _pick(rows, account_id):
    if not rows:
        print(f"未找到账户: {account_id or ''}")
        return None
    if account_id is None and len(rows) > 1:
        print(f"注意: usercode 存在 {len(rows)} 条记录，将作用于 id 最小的一条")
    return rows[0]


def cmd_show(args):
    rows = _find(args.usercode)
    if not rows:
        print("未找到账户")
        return 1
    print(f"{'id':22s} {'status':6s} {'salt':8s} {'pwd(前16位)':18s} name")
    for r in rows:
        pwd = (r.get("pwd") or "")
        print(f"{r['id']:<22} {r['status']:<6} {str(r.get('salt') or '-'):<8} "
              f"{pwd[:16] + '…' if pwd else '(空)':<18} {r.get('accountname') or ''}")
    return 0


def cmd_set(args):
    row = _pick(_find(args.usercode, args.id), args.id)
    if not row:
        return 1
    old_pwd = (row.get("pwd") or "")[:16]
    salt = str(random.randint(0, 999999)).zfill(6) if args.new_salt else str(row.get("salt") or "").strip()
    if not salt:
        salt = str(random.randint(0, 999999)).zfill(6)
        print("原记录 salt 为空，已生成新 salt")
    new_pwd = hash_password(row["usercode"], args.password, salt)
    n = execute(
        "UPDATE ucsdb.account SET pwd=%s, salt=%s WHERE id=%s AND dbsplitcode='1'",
        (new_pwd.upper(), salt, row["id"]),
    )
    print(f"已更新 id={row['id']} usercode={row['usercode']}")
    print(f"  salt: {salt}")
    print(f"  pwd : {old_pwd}… -> {new_pwd[:16].upper()}…")
    print(f"  影响行数: {n}")
    print(f"  校验: {'通过' if verify_password(stage1_hash(row['usercode'], args.password), new_pwd, row['usercode'], salt) else '失败'}")
    return 0


def cmd_check(args):
    rows = _find(args.usercode, args.id)
    if not rows:
        print("未找到账户")
        return 1
    s1 = stage1_hash(args.usercode, args.password)
    print(f"第一层哈希: {s1}")
    ok_any = False
    for r in rows:
        s2_ok = verify_password(s1, r.get("pwd") or "", r["usercode"], r.get("salt") or "")
        print(f"  id={r['id']:<22} status={r['status']} salt={r.get('salt')} -> {'MATCH' if s2_ok else 'no'}")
        ok_any = ok_any or s2_ok
    if args.verbose:
        print(f"\n能登录: {ok_any}")
    return 0 if ok_any else 2


def cmd_audit(args):
    rows = fetch_all(
        "SELECT id, usercode, accountname, salt, status, LENGTH(pwd) plen "
        "FROM ucsdb.account WHERE dbsplitcode='1' ORDER BY usercode, id"
    )
    bad_salt = [r for r in rows if not (r.get("salt") or "").strip()]
    bad_pwd = [r for r in rows if r.get("plen") != 64]
    disabled = [r for r in rows if r.get("status") != 1]
    print(f"账户总数(split=1):        {len(rows)}")
    print(f"  status=1 可用:          {len(rows) - len(disabled)}")
    print(f"  status!=1 停用:         {len(disabled)}")
    print(f"  salt 缺失(无法登录):    {len(bad_salt)}")
    for r in bad_salt[:20]:
        print(f"      {r['usercode']:<20} id={r['id']}")
    print(f"  pwd 非64位哈希:         {len(bad_pwd)}")
    for r in bad_pwd[:20]:
        print(f"      {r['usercode']:<20} id={r['id']} len={r['plen']}")
    # 重复账户
    from collections import Counter
    c = Counter(r["usercode"] for r in rows)
    dups = {k: v for k, v in c.items() if v > 1}
    print(f"  重复 usercode:          {len(dups)} 组")
    for k, v in list(dups.items())[:20]:
        ids = [str(r["id"]) for r in rows if r["usercode"] == k]
        print(f"      {k:<20} {v} 条 -> {', '.join(ids)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="账户密码维护（SHA-256 双层链路）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="查看账户状态")
    p.add_argument("usercode")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("set", help="设置密码")
    p.add_argument("usercode")
    p.add_argument("password")
    p.add_argument("--id", type=int, default=None, help="指定账户 id（重复 usercode 时）")
    p.add_argument("--new-salt", action="store_true", help="同时重新生成 salt")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("check", help="校验密码是否可登录（不写库）")
    p.add_argument("usercode")
    p.add_argument("password")
    p.add_argument("--id", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("audit", help="账户健康度审计")
    p.set_defaults(func=cmd_audit)

    args = ap.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
