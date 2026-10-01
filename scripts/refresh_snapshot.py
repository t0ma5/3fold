#!/usr/bin/env python3
"""Refresh numeric fields in site/snapshot.json. Editorial names and notes stay."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import requests
from substrateinterface import SubstrateInterface

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "site" / "snapshot.json"
INDEX_PATH = ROOT / "site" / "index.html"

ISSUER = "GBOVQKJYHXRR3DX6NOX2RRYFRCUMSADGDESTDNBDS6CDVLGVESRTAC47"
VAULT_TF = "GBNOTAYUMXVO5QDYWYO2SOCOYIJ3XFIP65GKOQN7H65ZZSO6BK4SLWSC"
VAULT_BSC = "GBFFWXWBZDILJJAMSINHPJEUJKB3H4UYXRWNB4COYQAF7UUQSWSBUXW5"
VAULT_ETH = "GARQ6KUXUCKDPIGI7NPITDN55J23SVR5RJ5RFOOU3ZPLMRJYOQRNMOIJ"
BSC_TOKEN = "0x8f0FB159380176D324542b3a7933F0C2Fd0c2bbf"
BSC_RPC = "https://bsc-dataseed.binance.org"
TFCHAIN_URL = "wss://tfchain.grid.tf"
STROOP = Decimal(10_000_000)
UA = {"User-Agent": "tft-ledger-overview/1.0"}


def money(stroops: int) -> Decimal:
    return (Decimal(stroops) * Decimal("0.10") / STROOP).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def fmt_tft(stroops: int) -> str:
    negative = stroops < 0
    amount = (Decimal(abs(stroops)) / STROOP).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    text = f"{amount:,.2f}"
    return f"-{text}" if negative else text


def fmt_usd(stroops: int) -> str:
    negative = stroops < 0
    text = f"{money(abs(stroops)):,.2f}"
    return f"-{text}" if negative else text


def fmt_pct(part: int, whole: int) -> str:
    if whole == 0:
        return "0.00%"
    share = (Decimal(part) / Decimal(whole) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{share}%"


def tft_to_stroops(text: str) -> int:
    return int(
        (Decimal(text) * STROOP).to_integral_value(rounding=ROUND_HALF_UP)
    )


def get_json(url: str) -> dict:
    response = requests.get(url, headers=UA, timeout=60)
    response.raise_for_status()
    return response.json()


def horizon_tft(account: str) -> int:
    payload = get_json(f"https://horizon.stellar.org/accounts/{account}")
    for balance in payload["balances"]:
        if (
            balance.get("asset_code") == "TFT"
            and balance.get("asset_issuer") == ISSUER
        ):
            return tft_to_stroops(balance["balance"])
    raise SystemExit(f"No TFT balance on {account}")


def stellar_supply_and_holders() -> tuple[int, list[tuple[str, int]]]:
    asset = get_json(
        "https://api.stellar.expert/explorer/public/asset/"
        f"TFT-{ISSUER}"
    )
    supply = int(asset["supply"])
    holders = get_json(
        "https://api.stellar.expert/explorer/public/asset/"
        f"TFT-{ISSUER}/holders?order=desc&limit=10"
    )
    rows = []
    for record in holders["_embedded"]["records"]:
        account = record.get("account") or record["address"]
        rows.append((account, int(record["balance"])))
    if len(rows) != 10:
        raise SystemExit(f"Expected 10 Stellar holders, got {len(rows)}")
    return supply, rows


def bsc_call(data: str) -> int:
    response = requests.post(
        BSC_RPC,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": BSC_TOKEN, "data": data}, "latest"],
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise SystemExit(f"BSC eth_call failed: {payload['error']}")
    return int(payload["result"], 16)


def bsc_balances(addresses: list[str]) -> tuple[int, list[tuple[str, int]]]:
    total = bsc_call("0x18160ddd")
    rows = []
    for address in addresses:
        padded = address.lower().removeprefix("0x").zfill(64)
        balance = bsc_call("0x70a08231" + padded)
        if balance > 0:
            rows.append((address, balance))
    rows.sort(key=lambda item: item[1], reverse=True)
    return total, rows


def tfchain_issuance_and_top() -> tuple[int, int, int, list[tuple[str, int]]]:
    substrate = SubstrateInterface(url=TFCHAIN_URL)
    substrate.init_runtime()
    issuance = int(substrate.query("Balances", "TotalIssuance").value)
    block = int(substrate.get_block_number(substrate.get_chain_head()))
    ranked: list[tuple[int, str]] = []
    summed = 0
    accounts = 0
    for key, value in substrate.query_map("System", "Account", page_size=1000):
        accounts += 1
        data = value.value["data"]
        balance = int(data["free"]) + int(data["reserved"])
        summed += balance
        if balance > 0:
            ranked.append((balance, key.value))
    if summed != issuance:
        raise SystemExit(
            f"TFChain account sum {summed} != TotalIssuance {issuance}"
        )
    ranked.sort(reverse=True)
    top = [(account, balance) for balance, account in ranked[:10]]
    if len(top) < 10:
        raise SystemExit(f"Expected 10 TFChain holders, got {len(top)}")
    return issuance, block, accounts, top


def replace_once(text: str, pattern: str, repl: str, label: str) -> str:
    updated, count = re.subn(pattern, repl, text, count=1)
    if count != 1:
        raise SystemExit(f"Could not refresh {label}")
    return updated


def keep_row(old_rows: list[dict], account: str) -> dict:
    for row in old_rows:
        if str(row.get("account", "")).lower() == account.lower():
            return row
    return {}


def holder_rows(
    old_rows: list[dict],
    fresh: list[tuple[str, int]],
    total: int,
) -> list[dict]:
    rows = []
    for rank, (account, stroops) in enumerate(fresh, start=1):
        old = keep_row(old_rows, account)
        rows.append(
            {
                "rank": rank,
                "account": account,
                "tft": fmt_tft(stroops),
                "share": fmt_pct(stroops, total),
                "name": old.get("name", "No public match"),
                "note": old.get("note", "No saved name for this account."),
            }
        )
    return rows


def supply_row(rows: list[dict], place: str) -> dict:
    for row in rows:
        if row.get("place") == place:
            return row
    raise SystemExit(f"Missing supply row: {place}")


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if snapshot.get("issuer") != ISSUER:
        raise SystemExit("Snapshot issuer does not match the TFT issuer")

    now = datetime.now(timezone.utc)
    label = f"{now.day} {now.strftime('%b')} {now.year}"
    supply, stellar_holders = stellar_supply_and_holders()
    vault_tf = horizon_tft(VAULT_TF)
    vault_bsc = horizon_tft(VAULT_BSC)
    vault_eth = horizon_tft(VAULT_ETH)
    outside = supply - vault_tf - vault_bsc - vault_eth
    if outside < 0:
        raise SystemExit("Vault balances exceed issuer supply")

    print("Reading TFChain accounts…", flush=True)
    issuance, block, accounts, tf_top = tfchain_issuance_and_top()
    extra = vault_tf - issuance
    bsc_addresses = [row["account"] for row in snapshot["bsc"]["rows"]]
    bsc_total, bsc_rows = bsc_balances(bsc_addresses)

    stellar_top = sum(stroops for _, stroops in stellar_holders)
    tf_top_sum = sum(stroops for _, stroops in tf_top)
    block_text = f"{block:,}"

    snapshot["snapshotLabel"] = label
    snapshot["snapshotDetail"] = (
        f"{now.day} {now.strftime('%B')} {now.year}, {now.strftime('%H:%M')} UTC. "
        "Stellar holders from stellar.expert. Vault balances from Horizon. "
        f"TFChain System.Account at block {block_text}. "
        "BSC balances from the BEP-20 contract."
    )
    snapshot["pauseNote"] = (
        "Weekly refresh runs on GitHub Actions, Mondays at 06:00 UTC."
    )

    places = {
        "Stellar wallets outside the 3 known vaults": outside,
        "TFChain holders": issuance,
        "Extra still frozen in that vault": extra,
        "BSC vault": vault_bsc,
        "Ethereum vault": vault_eth,
    }
    rounded_usd = Decimal("0.00")
    for place, stroops in places.items():
        row = supply_row(snapshot["supply"]["rows"], place)
        row["tft"] = fmt_tft(stroops)
        row["usd"] = fmt_usd(stroops)
        rounded_usd += money(stroops)
        if place == "Ethereum vault":
            raw = f"{(Decimal(vault_eth) / STROOP):f}"
            row["detail"] = replace_once(
                row["detail"],
                r"Horizon TFT balance [0-9.]+",
                f"Horizon TFT balance {raw}",
                "Ethereum vault detail",
            )

    exact = money(supply)
    snapshot["supply"]["total"] = {
        "tft": fmt_tft(supply),
        "sporeIfSwapped": f"{(Decimal(supply) / STROOP * Decimal(10)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):,}",
        "usdLabeled": f"{exact:,.2f}",
        "rowCentsUsd": f"{rounded_usd.quantize(Decimal('0.01')):,.2f}",
        "exactProductUsd": f"{exact:,.2f}",
    }

    snapshot["stellar"]["lede"] = replace_once(
        snapshot["stellar"]["lede"],
        r"Top 10 are [\d.]+%",
        f"Top 10 are {fmt_pct(stellar_top, supply)}",
        "Stellar top-10 share",
    )
    snapshot["stellar"]["rows"] = holder_rows(
        snapshot["stellar"]["rows"], stellar_holders, supply
    )

    tf_lede = snapshot["tfchain"]["lede"]
    tf_lede = replace_once(
        tf_lede, r"at block [\d,]+", f"at block {block_text}", "TFChain block"
    )
    tf_lede = replace_once(
        tf_lede,
        r"TFChain issuance, [\d,]+\.\d+ TFT",
        f"TFChain issuance, {fmt_tft(issuance)} TFT",
        "TFChain issuance",
    )
    tf_lede = replace_once(
        tf_lede,
        r"Ranks 1[–-]10 hold [\d.]+%",
        f"Ranks 1–10 hold {fmt_pct(tf_top_sum, issuance)}",
        "TFChain top-10 share",
    )
    snapshot["tfchain"]["lede"] = tf_lede
    snapshot["tfchain"]["rows"] = holder_rows(
        snapshot["tfchain"]["rows"], tf_top, issuance
    )

    bsc_lede = snapshot["bsc"]["lede"]
    bsc_lede = replace_once(
        bsc_lede,
        r"Contract total supply [\d,]+\.\d+ TFT",
        f"Contract total supply {fmt_tft(bsc_total)} TFT",
        "BSC total supply",
    )
    bsc_lede = replace_once(
        bsc_lede,
        r"read \d{1,2} \w+ \d{4}",
        f"read {label}",
        "BSC read date",
    )
    snapshot["bsc"]["lede"] = bsc_lede
    snapshot["bsc"]["rows"] = holder_rows(
        snapshot["bsc"]["rows"], bsc_rows, bsc_total
    )

    rank2 = next(
        (stroops for account, stroops in stellar_holders if account == "GC4HM4YR653H5F7R3S2AS6E2VIRLIQTOJ7UQCDUVJD65Z2M42UFHFWSA"),
        None,
    )
    if rank2 is None:
        rank2 = horizon_tft(
            "GC4HM4YR653H5F7R3S2AS6E2VIRLIQTOJ7UQCDUVJD65Z2M42UFHFWSA"
        )
    wallet = snapshot["topStellarWallet"]
    wallet["close"] = replace_once(
        wallet["close"],
        r"live [\d,]+\.\d+ TFT",
        f"live {fmt_tft(rank2)} TFT",
        "GC4HM4 live balance",
    )

    aside = snapshot["portal"]["aside"]
    snapshot["portal"]["aside"] = replace_once(
        aside,
        r"would require \$[\d,]+\.\d{2}",
        f"would require ${exact:,.2f}",
        "SPORE dollar figure",
    )

    for row in snapshot["method"]["rows"]:
        body = row["body"]
        if "At block " in body:
            body = replace_once(
                body,
                r"At block [\d,]+, [\d,]+ accounts summed to [\d,]+\.\d+ TFT",
                (
                    f"At block {block_text}, {accounts:,} accounts summed to "
                    f"{fmt_tft(issuance)} TFT"
                ),
                "method TFChain sum",
            )
        if "indexed supply was" in body:
            body = replace_once(
                body,
                r"indexed supply was \d+ stroops, printed as [\d,]+\.\d+ TFT",
                (
                    f"indexed supply was {supply} stroops, printed as "
                    f"{fmt_tft(supply)} TFT"
                ),
                "method Stellar supply",
            )
        row["body"] = body

    write_json(SNAPSHOT_PATH, snapshot)

    index = INDEX_PATH.read_text(encoding="utf-8")
    index = replace_once(
        index,
        r"<title>TFT snapshot · [^<]+</title>",
        f"<title>TFT snapshot · {label}</title>",
        "page title",
    )
    index = replace_once(
        index,
        r"each TFT counted once, [^.<]+\.",
        f"each TFT counted once, {label}.",
        "page description",
    )
    index = replace_once(
        index,
        r'<p id="pause">[^<]*</p>',
        f'<p id="pause">{snapshot["pauseNote"]}</p>',
        "pause note",
    )
    INDEX_PATH.write_text(index, encoding="utf-8")
    print(
        f"Snapshot {label}: supply {fmt_tft(supply)} TFT, "
        f"label ${exact:,.2f}, TFChain block {block_text}"
    )


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        sys.exit(f"Network read failed: {exc}")
