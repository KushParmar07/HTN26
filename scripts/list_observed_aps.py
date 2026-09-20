"""CLI tool to inspect observed Wi-Fi APs and configure legitimate phone hotspot BSSID."""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional
import httpx


def get_backend_data(base_url: str) -> Optional[Dict[str, Any]]:
    try:
        with httpx.Client(timeout=3.0) as client:
            resp_aps = client.get(f"{base_url}/api/aps")
            if resp_aps.status_code != 200:
                print(f"[!] Error: /api/aps returned status {resp_aps.status_code}")
                return None

            resp_threats = client.get(f"{base_url}/api/threats")
            threats_data = resp_threats.json() if resp_threats.status_code == 200 else {}

            resp_auth = client.get(f"{base_url}/api/authorize_bssid")
            auth_data = resp_auth.json() if resp_auth.status_code == 200 else {}

            return {
                "aps": resp_aps.json(),
                "threats": threats_data,
                "auth": auth_data,
            }
    except Exception as e:
        print(f"[!] Error connecting to backend at {base_url}: {e}")
        return None


def authorize_bssid_live(base_url: str, bssid: str, ssid: str = "AdrianPhone") -> bool:
    clean_bssid = bssid.strip().upper()
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(
                f"{base_url}/api/authorize_bssid",
                json={"bssid": clean_bssid, "ssid": ssid},
            )
            if resp.status_code == 200:
                print(f"[+] Successfully authorized {clean_bssid} (SSID: {ssid}) on backend!")
                # Also persist to .env
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                update_env_authorized_bssid(env_path, clean_bssid)
                return True
            else:
                print(f"[!] Failed to authorize: HTTP {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        print(f"[!] Network error authorizing BSSID: {e}")
        return False


def update_env_authorized_bssid(env_path: str, bssid: str) -> None:
    try:
        existing = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing[k.strip()] = v.strip()

        bssids = set(existing.get("AUTHORIZED_BSSIDS", "").split(","))
        bssids.discard("")
        bssids.add(bssid)
        existing["AUTHORIZED_BSSIDS"] = ",".join(sorted(bssids))
        existing["AUTHORIZED_SSID"] = "AdrianPhone"

        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")
        print(f"[+] Persisted authorized BSSID to {env_path}")
    except Exception as e:
        print(f"[!] Warning: could not write to .env: {e}")


def print_table(data: Dict[str, Any], target_ssid: str = "AdrianPhone", filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
    aps: List[Dict[str, Any]] = data.get("aps", [])
    threat_map = {}
    for t in data.get("threats", {}).get("threats", []):
        threat_map[t["bssid"].upper()] = t
    for m in data.get("threats", {}).get("monitored_aps", []):
        threat_map[m["bssid"].upper()] = m

    authorized_bssids = set(data.get("auth", {}).get("authorized_bssids", []))

    filtered_aps = []
    for ap in aps:
        ssid = ap.get("ssid") or "<Hidden>"
        bssid = ap.get("bssid", "").upper()
        if filter_query:
            q = filter_query.upper()
            if q not in ssid.upper() and q not in bssid:
                continue
        filtered_aps.append(ap)

    # Sort: target SSID first, then signal strength
    def sort_key(item):
        is_target = 0 if item.get("ssid", "").upper() == target_ssid.upper() else 1
        avg_rssi = -127.0
        rssi_dict = item.get("filtered_rssi", {})
        if rssi_dict:
            valid = [v for v in rssi_dict.values() if v is not None]
            if valid:
                avg_rssi = sum(valid) / len(valid)
        return (is_target, -avg_rssi)

    filtered_aps.sort(key=sort_key)

    header = (
        f"{'#':<3} | {'TARGET':<6} | {'SSID':<24} | {'BSSID':<18} | {'CH':<3} | {'AUTH':<10} | "
        f"{'PODS':<5} | {'AVG RSSI':<9} | {'STATUS':<24} | {'RISK':<5} | {'FLAGS'}"
    )
    separator = "-" * len(header)
    print("\n" + separator)
    print(f"OBSERVED ACCESS POINTS ({len(filtered_aps)} total) - Target SSID: '{target_ssid}'")
    print(separator)
    print(header)
    print(separator)

    for idx, ap in enumerate(filtered_aps, 1):
        ssid = ap.get("ssid") or "<Hidden>"
        bssid = ap.get("bssid", "").upper()
        ch = str(ap.get("current_channel") or "-")
        auth = ap.get("authmode") or "UNKNOWN"
        active_pods = ap.get("active_pods", [])
        pod_count = f"{len(active_pods)}/3"

        rssi_dict = ap.get("filtered_rssi", {})
        valid_rssi = [v for v in rssi_dict.values() if v is not None]
        avg_rssi = f"{sum(valid_rssi)/len(valid_rssi):.1f} dBm" if valid_rssi else "N/A"

        threat_info = threat_map.get(bssid)
        status = threat_info.get("status") if threat_info else ("AUTHORIZED" if bssid in authorized_bssids else "MONITORED")
        risk = f"{threat_info.get('risk_score', 0.0):.0f}" if threat_info else "0"
        flags = ", ".join(threat_info.get("evidence_flags", [])) if threat_info else ""

        is_target = ">>> YES" if ssid.upper() == target_ssid.upper() else ""
        if bssid in authorized_bssids:
            status_display = f"\033[92m{status} [LEGIT]\033[0m"
        elif status == "SUSPICIOUS_INFRASTRUCTURE":
            status_display = f"\033[91m{status} [ROGUE]\033[0m"
        else:
            status_display = status

        print(
            f"{idx:<3} | {is_target:<6} | {ssid[:24]:<24} | {bssid:<18} | {ch:<3} | {auth[:10]:<10} | "
            f"{pod_count:<5} | {avg_rssi:<9} | {status_display:<24} | {risk:<5} | {flags}"
        )

    print(separator + "\n")
    return filtered_aps


def main():
    parser = argparse.ArgumentParser(description="RF Threat Detection - Observed AP Inspector & Authorizer")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--target", default="AdrianPhone", help="Target demo SSID (default: AdrianPhone)")
    parser.add_argument("--filter", help="Optional substring filter for SSID or BSSID")
    parser.add_argument("--authorize", help="BSSID to mark as the authorized legitimate AP")
    parser.add_argument("--interactive", action="store_true", help="Interactively select which BSSID to authorize")
    parser.add_argument("--watch", action="store_true", help="Live refresh every 2 seconds")
    args = parser.parse_args()

    if args.authorize:
        success = authorize_bssid_live(args.url, args.authorize, args.target)
        sys.exit(0 if success else 1)

    while True:
        data = get_backend_data(args.url)
        if not data:
            print("[!] Could not fetch backend state. Is 'uvicorn backend.app.main:app' running?")
            if not args.watch:
                sys.exit(1)
            time.sleep(2)
            continue

        displayed = print_table(data, target_ssid=args.target, filter_query=args.filter)

        if args.interactive:
            target_aps = [ap for ap in displayed if ap.get("ssid", "").upper() == args.target.upper()]
            if not target_aps:
                print(f"[!] No APs matching target SSID '{args.target}' observed yet.")
            else:
                print(f"[*] Found {len(target_aps)} AP(s) matching '{args.target}':")
                for i, ap in enumerate(target_aps, 1):
                    bssid = ap.get("bssid", "").upper()
                    auth = ap.get("authmode") or "UNKNOWN"
                    print(f"  [{i}] BSSID: {bssid}  (Auth: {auth})")
                choice = input("\nEnter number of the LEGITIMATE phone hotspot to authorize (or 'q' to quit): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(target_aps):
                    selected = target_aps[int(choice) - 1]["bssid"]
                    authorize_bssid_live(args.url, selected, args.target)
                else:
                    print("Exiting without changes.")
            break

        if not args.watch:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
