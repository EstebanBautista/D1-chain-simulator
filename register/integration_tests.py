#!/usr/bin/env python3
"""End-to-end integration tests, run from inside a cash register.

Run it from a register container, where it sees exactly what a register sees:

    make shell CONTAINER=store-1-register-1
    python integration_tests.py

Exits zero when every check passes, non-zero as soon as one fails.
"""

import os
import socket
import sys
from decimal import Decimal

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://store-1-backend:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://store-1-frontend:80")

# Named so the isolation checks can assert these are UNREACHABLE from here.
PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "http://payment-gateway:5000")
CENTRAL_API_URL = os.getenv("CENTRAL_API_URL", "http://central-api:8000")
OTHER_STORE_BACKEND_URL = os.getenv(
    "OTHER_STORE_BACKEND_URL", "http://store-2-backend:8000"
)

# This register serves the site on port 80 of its own container.
REGISTER_SITE_URL = "http://localhost:80"
REGISTER_ID = os.getenv("REGISTER_ID", "store-1-register-1")
STORE_ID = os.getenv("STORE_ID", "store-1")
DECLINE_THRESHOLD = Decimal(os.getenv("DECLINE_THRESHOLD", "1000000"))

# Present in the seed catalog. Cheap enough that a large quantity still lands
# below the decline threshold.
KNOWN_EAN = "7702001010301"
UNKNOWN_EAN = "0000000000000"

REQUEST_TIMEOUT_SECONDS = 10

# Shorter for the checks that are SUPPOSED to fail. On an internal network the
# name usually fails to resolve immediately, but a route that simply goes
# nowhere would otherwise hang for the full timeout, four times over.
UNREACHABLE_TIMEOUT_SECONDS = 4

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

failures: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> bool:
    """Report one check and remember it if it failed."""
    if condition:
        print(f"  {GREEN}PASS{RESET}  {description}")
    else:
        print(f"  {RED}FAIL{RESET}  {description}")
        if detail:
            print(f"        {detail}")
        failures.append(description)
    return condition


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


# --- 1. Network isolation and connectivity --------------------------------------------


def resolves(hostname: str) -> bool:
    """Whether Docker's DNS gives this register an address for a name.

    On a separate network the name does not resolve at all, which is a cleaner
    signal than a connection timing out.
    """
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


def expect_unreachable(description: str, url: str) -> None:
    """Assert that this destination CANNOT be reached from the register.

    A failure here is a PASS. That inversion is the whole point of this phase:
    a register on a real store's LAN has no route to the payment processor, to
    head office or to another branch, and the exercise is only honest if the
    tests confirm it rather than assuming it.

    Note the registers DO keep internet access. Sealing their network with
    `internal: true` would have removed it, but Docker then refuses to publish
    a host port for the container, and a register nobody can open in a browser
    is not a register. See the README.
    """
    try:
        response = httpx.get(url, timeout=UNREACHABLE_TIMEOUT_SECONDS)
    except (httpx.HTTPError, OSError):
        check(f"{description} is NOT reachable from the register", True)
        return

    check(
        f"{description} is NOT reachable from the register",
        False,
        f"Reached it and got HTTP {response.status_code} - the network is not isolated",
    )


def test_network_connectivity() -> None:
    section("1. Network isolation and connectivity")

    # --- What MUST work: this store's own services ----------------------

    try:
        response = httpx.get(f"{BACKEND_URL}/health", timeout=REQUEST_TIMEOUT_SECONDS)
        ok = check(
            "The register reaches its own store's backend",
            response.status_code == 200,
            f"Got HTTP {response.status_code}",
        )
        if ok:
            check(
                "The backend reports the store this register belongs to",
                response.json().get("store_id") == STORE_ID,
                f"Expected {STORE_ID}, got {response.json().get('store_id')}",
            )
    except httpx.HTTPError as error:
        check("The register reaches its own store's backend", False, str(error))

    hostname = BACKEND_URL.split("//")[-1].split(":")[0]
    try:
        resolved = socket.gethostbyname(hostname)
        check(f"The backend service name '{hostname}' resolves", True, f"-> {resolved}")
    except socket.gaierror as error:
        check(f"The backend service name '{hostname}' resolves", False, str(error))

    try:
        response = httpx.get(FRONTEND_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        check(
            "The register reaches its own store's web server",
            response.status_code == 200,
            f"Got HTTP {response.status_code}",
        )
    except httpx.HTTPError as error:
        check("The register reaches its own store's web server", False, str(error))

    # --- What MUST NOT work: everything outside this store --------------

    # Charging a card is the backend's job. A register that could reach the
    # payment processor directly would be a register that could charge one.
    expect_unreachable("The payment gateway", f"{PAYMENT_GATEWAY_URL}/health")

    # Head office is reached by the forwarder, never by a register.
    expect_unreachable("The central site", f"{CENTRAL_API_URL}/health")

    # The two stores are separate sites and share no network.
    expect_unreachable("The other store's backend", f"{OTHER_STORE_BACKEND_URL}/health")

    # Head office's database is behind its API, on head office's own network.
    check(
        "The central database name does not even resolve from the register",
        not resolves("central-mysql"),
        "It resolved, so the register shares a network with head office",
    )


# --- 2. The register serves the web site --------------------------------


def test_register_serves_the_site() -> None:
    section("2. The register is the way into the web site")

    try:
        response = httpx.get(REGISTER_SITE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        check(
            "The register serves the store web site",
            response.status_code == 200 and "<html" in response.text.lower(),
            f"Got HTTP {response.status_code}",
        )
    except httpx.HTTPError as error:
        check("The register serves the store web site", False, str(error))

    try:
        response = httpx.get(
            f"{REGISTER_SITE_URL}/register-config.js", timeout=REQUEST_TIMEOUT_SECONDS
        )
        check(
            "The register publishes its own store and register identity",
            response.status_code == 200
            and REGISTER_ID in response.text
            and STORE_ID in response.text,
            f"HTTP {response.status_code}: {response.text.strip()}",
        )
    except httpx.HTTPError as error:
        check(
            "The register publishes its own store and register identity",
            False,
            str(error),
        )

    try:
        response = httpx.get(
            f"{REGISTER_SITE_URL}/api/products/{KNOWN_EAN}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        check(
            "API calls reach the backend through the register",
            response.status_code == 200,
            f"Got HTTP {response.status_code}",
        )
    except httpx.HTTPError as error:
        check("API calls reach the backend through the register", False, str(error))

    # The site container publishes no host port, so a browser cannot reach it
    # without going through a register. From inside the network it is of course
    # reachable, and it must NOT hand out a register identity of its own.
    try:
        response = httpx.get(
            f"{FRONTEND_URL}/register-config.js", timeout=REQUEST_TIMEOUT_SECONDS
        )
        check(
            "The web site itself claims no register identity",
            response.status_code == 404,
            f"Got HTTP {response.status_code}",
        )
    except httpx.HTTPError as error:
        check("The web site itself claims no register identity", False, str(error))


# --- 3. API and database integration ------------------------------------


def test_api_database_integration() -> None:
    section("3. API and database integration")

    try:
        response = httpx.get(
            f"{BACKEND_URL}/products/{KNOWN_EAN}", timeout=REQUEST_TIMEOUT_SECONDS
        )
        ok = check(
            "Looking up a seeded product returns HTTP 200",
            response.status_code == 200,
            f"Got HTTP {response.status_code}",
        )

        if ok:
            product = response.json()
            check(
                "The product carries a name from the database",
                bool(product.get("name")),
                f"Payload: {product}",
            )
            check(
                "The product carries a positive unit price",
                Decimal(str(product.get("price", "0"))) > 0,
                f"Payload: {product}",
            )
    except httpx.HTTPError as error:
        check("Looking up a seeded product returns HTTP 200", False, str(error))

    try:
        response = httpx.get(
            f"{BACKEND_URL}/products/{UNKNOWN_EAN}", timeout=REQUEST_TIMEOUT_SECONDS
        )
        check(
            "Looking up an unknown EAN returns HTTP 404",
            response.status_code == 404,
            f"Got HTTP {response.status_code}",
        )
    except httpx.HTTPError as error:
        check("Looking up an unknown EAN returns HTTP 404", False, str(error))


# --- 4. Payment flow and persistence ------------------------------------


def test_approved_purchase() -> None:
    section("4. Approved purchase and persistence")

    payload = {
        "register_id": REGISTER_ID,
        "items": [{"ean": KNOWN_EAN, "quantity": 2}],
    }

    try:
        response = httpx.post(
            f"{BACKEND_URL}/payments", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
        ok = check(
            "A purchase within the threshold is accepted",
            response.status_code == 200,
            f"Got HTTP {response.status_code}: {response.text}",
        )
        if not ok:
            return

        result = response.json()
        check(
            "The payment is approved",
            result.get("status") == "APPROVED",
            f"Payload: {result}",
        )
        check(
            "The response carries a sale identifier",
            result.get("sale_id") is not None,
            f"Payload: {result}",
        )

        sale_id = result.get("sale_id")
        if sale_id is None:
            return

        sale_response = httpx.get(
            f"{BACKEND_URL}/sales/{sale_id}", timeout=REQUEST_TIMEOUT_SECONDS
        )
        ok = check(
            "The sale can be read back from the database",
            sale_response.status_code == 200,
            f"Got HTTP {sale_response.status_code}",
        )
        if not ok:
            return

        sale = sale_response.json()
        check("The stored sale carries a timestamp", bool(sale.get("sale_date")))
        check(
            "The stored total matches the charged total",
            Decimal(str(sale.get("total"))) == Decimal(str(result.get("total"))),
            f"Stored {sale.get('total')} vs charged {result.get('total')}",
        )
        check(
            "The stored sale is attributed to this register",
            sale.get("register_id") == REGISTER_ID,
            f"Got {sale.get('register_id')}",
        )
        check(
            "The stored sale carries its item detail",
            len(sale.get("items", [])) == 1
            and sale["items"][0]["ean"] == KNOWN_EAN
            and sale["items"][0]["quantity"] == 2,
            f"Items: {sale.get('items')}",
        )
    except httpx.HTTPError as error:
        check("A purchase within the threshold is accepted", False, str(error))


def test_declined_purchase() -> None:
    section("5. Declined purchase leaves nothing behind")

    # Buy enough units to cross the gateway's decline threshold. The rule is
    # deterministic, so this is a reliable way to force a decline.
    try:
        product = httpx.get(
            f"{BACKEND_URL}/products/{KNOWN_EAN}", timeout=REQUEST_TIMEOUT_SECONDS
        ).json()
        unit_price = Decimal(str(product["price"]))
        quantity = int(DECLINE_THRESHOLD / unit_price) + 10
    except (httpx.HTTPError, KeyError, ValueError) as error:
        check("Could prepare an over-threshold purchase", False, str(error))
        return

    payload = {
        "register_id": REGISTER_ID,
        "items": [{"ean": KNOWN_EAN, "quantity": quantity}],
    }

    try:
        response = httpx.post(
            f"{BACKEND_URL}/payments", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
        ok = check(
            "An over-threshold purchase is processed",
            response.status_code == 200,
            f"Got HTTP {response.status_code}: {response.text}",
        )
        if not ok:
            return

        result = response.json()
        check(
            "The payment is declined",
            result.get("status") == "DECLINED",
            f"Payload: {result}",
        )
        check(
            "The decline carries a reason",
            bool(result.get("decline_reason")),
            f"Payload: {result}",
        )
        check(
            "No sale identifier is issued for a declined payment",
            result.get("sale_id") is None,
            f"Payload: {result}",
        )
    except httpx.HTTPError as error:
        check("An over-threshold purchase is processed", False, str(error))


def main() -> int:
    print(f"{BOLD}Integration tests from {REGISTER_ID} ({STORE_ID}){RESET}")
    print(f"Backend: {BACKEND_URL}")
    print("Checks marked NOT reachable are meant to fail; a PASS there means")
    print("the network isolation is holding.")

    test_network_connectivity()
    test_register_serves_the_site()
    test_api_database_integration()
    test_approved_purchase()
    test_declined_purchase()

    print()
    if failures:
        print(f"{RED}{BOLD}{len(failures)} check(s) failed:{RESET}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"{GREEN}{BOLD}All checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
