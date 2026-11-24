"""Credential factory.

- Azure (Container Apps): DefaultAzureCredential -> user-assigned managed identity.
- Local dev: DefaultAzureCredential -> Azure CLI (`az login`).
- GitHub Actions: ClientAssertionCredential that requests a *fresh* GitHub OIDC token every time
  Entra needs one. GitHub ID tokens are short-lived, so a one-off `az login` breaks long jobs
  (e.g. the evaluation gate); this is Microsoft's recommended workload-identity pattern.
"""

import json
import os
import urllib.request
from functools import lru_cache
from typing import Any

from azure.identity import ClientAssertionCredential, DefaultAzureCredential
from azure.identity.aio import ClientAssertionCredential as AsyncClientAssertionCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

GITHUB_AUDIENCE = "api://AzureADTokenExchange"


def _in_github_oidc() -> bool:
    return bool(
        os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
        and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
        and os.environ.get("AZURE_CLIENT_ID")
        and os.environ.get("AZURE_TENANT_ID")
    )


def github_oidc_token() -> str:
    url = f"{os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']}&audience={GITHUB_AUDIENCE}"
    req = urllib.request.Request(  # noqa: S310 - URL comes from the GitHub runner
        url, headers={"Authorization": f"Bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        return str(json.load(resp)["value"])


@lru_cache
def credential() -> Any:
    if _in_github_oidc():
        return ClientAssertionCredential(
            os.environ["AZURE_TENANT_ID"], os.environ["AZURE_CLIENT_ID"], github_oidc_token
        )
    return DefaultAzureCredential()


def async_credential() -> Any:
    """New async credential (async credentials are bound to the event loop that uses them)."""
    if _in_github_oidc():
        return AsyncClientAssertionCredential(
            os.environ["AZURE_TENANT_ID"], os.environ["AZURE_CLIENT_ID"], github_oidc_token
        )
    return AsyncDefaultAzureCredential()
