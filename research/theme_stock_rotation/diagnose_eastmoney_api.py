from __future__ import annotations

import argparse
import re
import socket
import time
from dataclasses import dataclass

import akshare as ak
import requests


DEFAULT_HOSTS = [
    "push2.eastmoney.com",
    "79.push2.eastmoney.com",
    "48.push2.eastmoney.com",
    "29.push2.eastmoney.com",
]
REQUEST_INTERVAL_SECONDS = 1.2
_LAST_REQUEST_AT = 0.0


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="诊断东方财富/AkShare 题材接口连通性。")
    parser.add_argument("--theme-name", default="国家大基金持股", help="要测试的题材名称。")
    parser.add_argument("--theme-code", default="", help="已知东方财富板块代码，如 BKxxxx。")
    parser.add_argument("--hosts", default=",".join(DEFAULT_HOSTS), help="逗号分隔的东方财富 host。")
    parser.add_argument("--timeout", type=float, default=15.0, help="单次请求超时时间，单位秒。")
    parser.add_argument("--max-pages", type=int, default=50, help="题材列表最多扫描页数，每页 100 条。")
    parser.add_argument("--request-interval", type=float, default=1.2, help="诊断请求之间的最小间隔秒数。")
    parser.add_argument("--skip-akshare", action="store_true", help="跳过 AkShare 包装接口测试。")
    return parser.parse_args()


def eastmoney_params(
    fs: str,
    fields: str,
    page_size: int,
    page_number: int = 1,
) -> dict[str, str]:
    return {
        "pn": str(page_number),
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": fs,
        "fields": fields,
        "_": str(int(time.time() * 1000)),
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
        }
    )
    return session


def paced_session_get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    global _LAST_REQUEST_AT

    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < REQUEST_INTERVAL_SECONDS:
        time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
    try:
        return session.get(url, **kwargs)
    finally:
        _LAST_REQUEST_AT = time.monotonic()


def rows_from_payload(payload: dict) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    rows = data.get("diff", [])
    if isinstance(rows, dict):
        return list(rows.values())
    if isinstance(rows, list):
        return rows
    return []


def total_from_payload(payload: dict) -> int:
    data = payload.get("data")
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("total") or 0)
    except (TypeError, ValueError):
        return 0


def valid_theme_code(theme_code: str) -> bool:
    return bool(re.fullmatch(r"BK\d+", theme_code.strip().upper()))


def check_dns(hosts: list[str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for host in hosts:
        try:
            addresses = socket.gethostbyname_ex(host)[2]
            results.append(CheckResult(f"DNS {host}", True, ", ".join(addresses[:5])))
        except Exception as exc:
            results.append(CheckResult(f"DNS {host}", False, f"{type(exc).__name__}: {exc}"))
    return results


def check_concept_list(
    session: requests.Session,
    hosts: list[str],
    theme_name: str,
    timeout: float,
    max_pages: int,
) -> tuple[list[CheckResult], str]:
    results: list[CheckResult] = []
    found_code = ""
    for host in hosts:
        url = f"https://{host}/api/qt/clist/get"
        try:
            total_rows = 0
            total = 0
            first_names: list[str] = []
            for page_number in range(1, max_pages + 1):
                params = eastmoney_params(
                    fs="m:90 t:3 f:!50",
                    fields="f12,f14",
                    page_size=100,
                    page_number=page_number,
                )
                response = paced_session_get(session, url, params=params, timeout=timeout)
                response.raise_for_status()
                payload = response.json()
                rows = rows_from_payload(payload)
                if page_number == 1:
                    first_names = [str(row.get("f14", "")) for row in rows[:5]]
                if not rows:
                    break
                total_rows += len(rows)
                total = total or total_from_payload(payload)
                matched = [
                    str(row.get("f12", "")).strip().upper()
                    for row in rows
                    if str(row.get("f14", "")).strip() == theme_name
                ]
                if matched:
                    found_code = matched[0]
                    results.append(
                        CheckResult(
                            f"东方财富题材列表 {host}",
                            True,
                            f"扫描 {page_number} 页/{total_rows} 条，命中 {theme_name}={found_code}",
                        )
                    )
                    break
                if total and total_rows >= total:
                    break
            else:
                page_number = max_pages

            if found_code:
                return results, found_code
            names = ", ".join(first_names)
            total_text = f"，total={total}" if total else ""
            results.append(
                CheckResult(
                    f"东方财富题材列表 {host}",
                    True,
                    f"扫描 {page_number} 页/{total_rows} 条{total_text}，未命中；第一页前几项：{names}",
                )
            )
        except Exception as exc:
            results.append(
                CheckResult(f"东方财富题材列表 {host}", False, f"{type(exc).__name__}: {exc}")
            )
    return results, found_code


def check_constituents_by_code(
    session: requests.Session,
    hosts: list[str],
    theme_code: str,
    timeout: float,
) -> list[CheckResult]:
    if not theme_code:
        return [CheckResult("东方财富按板块代码拉成分股", False, "未提供或未解析出 BKxxxx。")]
    if not valid_theme_code(theme_code):
        return [
            CheckResult(
                "东方财富按板块代码拉成分股",
                False,
                f"{theme_code} 不是有效板块代码；请使用类似 BK1234 的真实代码，BKxxxx 只是占位符。",
            )
        ]

    results: list[CheckResult] = []
    params = eastmoney_params(
        fs=f"b:{theme_code.upper()} f:!50",
        fields="f12,f14,f2,f3",
        page_size=20,
    )
    for host in hosts:
        url = f"https://{host}/api/qt/clist/get"
        try:
            response = paced_session_get(session, url, params=params, timeout=timeout)
            response.raise_for_status()
            rows = rows_from_payload(response.json())
            preview = ", ".join(
                f"{row.get('f12', '')}{row.get('f14', '')}" for row in rows[:5]
            )
            results.append(
                CheckResult(
                    f"东方财富成分股 {host}",
                    bool(rows),
                    f"返回 {len(rows)} 条；样例：{preview}",
                )
            )
        except Exception as exc:
            results.append(CheckResult(f"东方财富成分股 {host}", False, f"{type(exc).__name__}: {exc}"))
    return results


def check_akshare(theme_name: str) -> CheckResult:
    try:
        df = ak.stock_board_concept_cons_em(symbol=theme_name)
        columns = ", ".join(map(str, df.columns[:8]))
        return CheckResult("AkShare stock_board_concept_cons_em", not df.empty, f"返回 {len(df)} 行；列：{columns}")
    except Exception as exc:
        return CheckResult("AkShare stock_board_concept_cons_em", False, f"{type(exc).__name__}: {exc}")


def print_results(results: list[CheckResult]) -> None:
    for result in results:
        status = "通过" if result.ok else "失败"
        print(f"[{status}] {result.name}: {result.message}")


def main() -> None:
    global REQUEST_INTERVAL_SECONDS

    args = parse_args()
    REQUEST_INTERVAL_SECONDS = max(0.0, args.request_interval)
    hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
    session = make_session()

    print("EDP 东方财富/AkShare 题材接口诊断")
    print(f"theme_name={args.theme_name}")
    print(f"theme_code={args.theme_code or '(未提供)'}")
    print(f"timeout={args.timeout}s")
    print(f"max_pages={args.max_pages}")
    print(f"request_interval={args.request_interval}s")
    print()

    all_results: list[CheckResult] = []
    dns_results = check_dns(hosts)
    print_results(dns_results)
    all_results.extend(dns_results)
    print()

    concept_results, found_code = check_concept_list(
        session,
        hosts,
        args.theme_name,
        args.timeout,
        args.max_pages,
    )
    print_results(concept_results)
    all_results.extend(concept_results)
    print()

    theme_code = args.theme_code.strip().upper() or found_code
    constituent_results = check_constituents_by_code(session, hosts, theme_code, args.timeout)
    print_results(constituent_results)
    all_results.extend(constituent_results)
    print()

    if not args.skip_akshare:
        akshare_result = check_akshare(args.theme_name)
        print_results([akshare_result])
        all_results.append(akshare_result)
        print()

    any_remote_ok = any(
        result.ok
        for result in all_results
        if result.name.startswith("东方财富") or result.name.startswith("AkShare")
    )
    if any_remote_ok:
        print("结论：至少有一个远程行情接口可用。若正式脚本仍失败，优先检查题材名/BK代码或 AkShare 包装层。")
        raise SystemExit(0)

    print("结论：远程行情接口全部失败。若 DNS 通过但请求失败，多半是网络权限、代理、防火墙或东方财富远端断连。")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
