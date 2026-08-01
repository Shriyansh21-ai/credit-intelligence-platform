"""Payment-gateway abstraction.

The billing engine never talks to Stripe/Razorpay directly — it depends on the
:class:`PaymentGateway` interface. The built-in :class:`InternalGateway` records
"charges" locally (invoices are marked paid immediately) so the platform is
fully functional without an external provider. Wiring a real gateway is a matter
of implementing this interface and registering it via :func:`set_gateway`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class ChargeResult:
    success: bool
    provider: str
    provider_ref: str
    message: str = ""


class PaymentGateway(Protocol):
    name: str

    def create_customer(self, organization_id: int, email: Optional[str]) -> str: ...

    def charge_invoice(self, invoice_number: str, amount: float, currency: str) -> ChargeResult: ...


class InternalGateway:
    """No-op local gateway — always succeeds, generates local refs."""

    name = "internal"

    def create_customer(self, organization_id: int, email: Optional[str]) -> str:
        return f"cus_internal_{organization_id}"

    def charge_invoice(self, invoice_number: str, amount: float, currency: str) -> ChargeResult:
        return ChargeResult(
            success=True, provider=self.name,
            provider_ref=f"pay_{uuid.uuid4().hex[:16]}",
            message="internal charge recorded",
        )


class StripeGateway:
    """Placeholder for the real Stripe integration (raises until configured)."""

    name = "stripe"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def create_customer(self, organization_id: int, email: Optional[str]) -> str:  # pragma: no cover
        raise NotImplementedError("Stripe gateway not configured")

    def charge_invoice(self, invoice_number: str, amount: float, currency: str) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError("Stripe gateway not configured")


class RazorpayGateway:
    """Placeholder for the real Razorpay integration (raises until configured)."""

    name = "razorpay"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def create_customer(self, organization_id: int, email: Optional[str]) -> str:  # pragma: no cover
        raise NotImplementedError("Razorpay gateway not configured")

    def charge_invoice(self, invoice_number: str, amount: float, currency: str) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError("Razorpay gateway not configured")


_gateway: PaymentGateway = InternalGateway()


def set_gateway(gateway: PaymentGateway) -> None:
    global _gateway
    _gateway = gateway


def get_gateway() -> PaymentGateway:
    return _gateway
