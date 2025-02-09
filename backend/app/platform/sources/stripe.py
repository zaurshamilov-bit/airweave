"""Stripe source implementation.

We retrieve data from the Stripe API for the following core resources:
- Balance
- Balance Transactions
- Charges
- Customers
- Events
- Invoices
- Payment Intents
- Payment Methods
- Payouts
- Refunds
- Subscriptions

Then, we yield them as chunks using the respective chunk schemas defined in chunks/stripe.py.
"""

from typing import AsyncGenerator

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk
from app.platform.chunks.stripe import (
    StripeBalanceChunk,
    StripeBalanceTransactionChunk,
    StripeChargeChunk,
    StripeCustomerChunk,
    StripeEventChunk,
    StripeInvoiceChunk,
    StripePaymentIntentChunk,
    StripePaymentMethodChunk,
    StripePayoutChunk,
    StripeRefundChunk,
    StripeSubscriptionChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Stripe", "stripe", AuthType.config_class, "StripeAuthConfig")
class StripeSource(BaseSource):
    """Stripe source implementation.

    This connector retrieves data from various Stripe objects, yielding them as chunks
    through their respective schemas. The following resource endpoints are used:

      - /v1/balance
      - /v1/balance_transactions
      - /v1/charges
      - /v1/customers
      - /v1/events
      - /v1/invoices
      - /v1/payment_intents
      - /v1/payment_methods
      - /v1/payouts
      - /v1/refunds
      - /v1/subscriptions

    Each resource endpoint may use Stripe’s pagination (has_more + starting_after) to
    retrieve all objects. Fields are mapped to the chunk schemas defined in chunks/stripe.py.
    """

    @classmethod
    async def create(cls, access_token: str) -> "StripeSource":
        """Create a new Stripe source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> dict:
        """Make an authenticated GET request to the Stripe API.

        The `url` should be a fully qualified endpoint (e.g., 'https://api.stripe.com/v1/customers').
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _generate_balance_chunk(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve the current account balance (single object) from.

        GET https://api.stripe.com/v1/balance
        Yields exactly one StripeBalanceChunk if successful.
        """
        url = "https://api.stripe.com/v1/balance"
        data = await self._get_with_auth(client, url)
        yield StripeBalanceChunk(
            source_name="stripe",
            entity_id="balance",  # Arbitrary ID since there's only one balance resource
            available=data.get("available", []),
            pending=data.get("pending", []),
            instant_available=data.get("instant_available"),
            connect_reserved=data.get("connect_reserved"),
            livemode=data.get("livemode", False),
        )

    async def _generate_balance_transaction_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve balance transactions in a paginated loop from.

        GET https://api.stripe.com/v1/balance_transactions
        Yields StripeBalanceTransactionChunk objects.
        """
        base_url = "https://api.stripe.com/v1/balance_transactions?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for txn in data.get("data", []):
                yield StripeBalanceTransactionChunk(
                    source_name="stripe",
                    entity_id=txn["id"],
                    amount=txn.get("amount"),
                    currency=txn.get("currency"),
                    created_at=txn.get("created"),
                    description=txn.get("description"),
                    fee=txn.get("fee"),
                    fee_details=txn.get("fee_details", []),
                    net=txn.get("net"),
                    reporting_category=txn.get("reporting_category"),
                    source=txn.get("source"),
                    status=txn.get("status"),
                    type=txn.get("type"),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_charge_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of charges.

          GET https://api.stripe.com/v1/charges
        Paginated, yields StripeChargeChunk objects.
        """
        base_url = "https://api.stripe.com/v1/charges?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for charge in data.get("data", []):
                yield StripeChargeChunk(
                    source_name="stripe",
                    entity_id=charge["id"],
                    amount=charge.get("amount"),
                    currency=charge.get("currency"),
                    captured=charge.get("captured", False),
                    paid=charge.get("paid", False),
                    refunded=charge.get("refunded", False),
                    created_at=charge.get("created"),
                    description=charge.get("description"),
                    receipt_url=charge.get("receipt_url"),
                    customer_id=charge.get("customer"),
                    invoice_id=charge.get("invoice"),
                    metadata=charge.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_customer_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of customers.

        GET https://api.stripe.com/v1/customers
        Paginated, yields StripeCustomerChunk objects.
        """
        base_url = "https://api.stripe.com/v1/customers?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for cust in data.get("data", []):
                yield StripeCustomerChunk(
                    source_name="stripe",
                    entity_id=cust["id"],
                    email=cust.get("email"),
                    phone=cust.get("phone"),
                    name=cust.get("name"),
                    description=cust.get("description"),
                    created_at=cust.get("created"),
                    currency=cust.get("currency"),
                    default_source=cust.get("default_source"),
                    delinquent=cust.get("delinquent", False),
                    invoice_prefix=cust.get("invoice_prefix"),
                    metadata=cust.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_event_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of events.

        GET https://api.stripe.com/v1/events
        Paginated, yields StripeEventChunk objects.
        """
        base_url = "https://api.stripe.com/v1/events?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for evt in data.get("data", []):
                yield StripeEventChunk(
                    source_name="stripe",
                    entity_id=evt["id"],
                    event_type=evt.get("type"),
                    api_version=evt.get("api_version"),
                    created_at=evt.get("created"),
                    data=evt.get("data", {}),
                    livemode=evt.get("livemode", False),
                    pending_webhooks=evt.get("pending_webhooks"),
                    request=evt.get("request"),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_invoice_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of invoices.

        GET https://api.stripe.com/v1/invoices
        Paginated, yields StripeInvoiceChunk objects.
        """
        base_url = "https://api.stripe.com/v1/invoices?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for inv in data.get("data", []):
                yield StripeInvoiceChunk(
                    source_name="stripe",
                    entity_id=inv["id"],
                    customer_id=inv.get("customer"),
                    number=inv.get("number"),
                    status=inv.get("status"),
                    amount_due=inv.get("amount_due"),
                    amount_paid=inv.get("amount_paid"),
                    amount_remaining=inv.get("amount_remaining"),
                    created_at=inv.get("created"),
                    due_date=inv.get("due_date"),
                    paid=inv.get("paid", False),
                    currency=inv.get("currency"),
                    metadata=inv.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_intent_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of payment intents.

        GET https://api.stripe.com/v1/payment_intents
        Paginated, yields StripePaymentIntentChunk objects.
        """
        base_url = "https://api.stripe.com/v1/payment_intents?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for pi in data.get("data", []):
                yield StripePaymentIntentChunk(
                    source_name="stripe",
                    entity_id=pi["id"],
                    amount=pi.get("amount"),
                    currency=pi.get("currency"),
                    status=pi.get("status"),
                    description=pi.get("description"),
                    created_at=pi.get("created"),
                    customer_id=pi.get("customer"),
                    metadata=pi.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_method_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of payment methods for the account or for a specific customer.

        The typical GET is: https://api.stripe.com/v1/payment_methods?customer=<id>&type=<type>
        For demonstration, we'll assume you pass a type of 'card' for all of them.
        Paginated, yields StripePaymentMethodChunk objects.
        """
        # Adjust as needed to retrieve the correct PaymentMethods.
        base_url = "https://api.stripe.com/v1/payment_methods?limit=100&type=card"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for pm in data.get("data", []):
                yield StripePaymentMethodChunk(
                    source_name="stripe",
                    entity_id=pm["id"],
                    type=pm.get("type"),
                    billing_details=pm.get("billing_details", {}),
                    customer_id=pm.get("customer"),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payout_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of payouts.

        GET https://api.stripe.com/v1/payouts
        Paginated, yields StripePayoutChunk objects.
        """
        base_url = "https://api.stripe.com/v1/payouts?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for payout in data.get("data", []):
                yield StripePayoutChunk(
                    source_name="stripe",
                    entity_id=payout["id"],
                    amount=payout.get("amount"),
                    currency=payout.get("currency"),
                    arrival_date=payout.get("arrival_date"),
                    created_at=payout.get("created"),
                    description=payout.get("description"),
                    destination=payout.get("destination"),
                    method=payout.get("method"),
                    status=payout.get("status"),
                    statement_descriptor=payout.get("statement_descriptor"),
                    metadata=payout.get("metadata", {}),
                )
            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_refund_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of refunds.

        GET https://api.stripe.com/v1/refunds
        Paginated, yields StripeRefundChunk objects.
        """
        base_url = "https://api.stripe.com/v1/refunds?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for refund in data.get("data", []):
                yield StripeRefundChunk(
                    source_name="stripe",
                    entity_id=refund["id"],
                    amount=refund.get("amount"),
                    currency=refund.get("currency"),
                    created_at=refund.get("created"),
                    status=refund.get("status"),
                    reason=refund.get("reason"),
                    receipt_number=refund.get("receipt_number"),
                    charge_id=refund.get("charge"),
                    payment_intent_id=refund.get("payment_intent"),
                    metadata=refund.get("metadata", {}),
                )
            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_subscription_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Retrieve a list of subscriptions.

        GET https://api.stripe.com/v1/subscriptions
        Paginated, yields StripeSubscriptionChunk objects.
        """
        base_url = "https://api.stripe.com/v1/subscriptions?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for sub in data.get("data", []):
                yield StripeSubscriptionChunk(
                    source_name="stripe",
                    entity_id=sub["id"],
                    customer_id=sub.get("customer"),
                    status=sub.get("status"),
                    current_period_start=sub.get("current_period_start"),
                    current_period_end=sub.get("current_period_end"),
                    cancel_at_period_end=sub.get("cancel_at_period_end", False),
                    canceled_at=sub.get("canceled_at"),
                    created_at=sub.get("created"),
                    metadata=sub.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:  # noqa: C901
        """Generate all Stripe chunks.

        - Balance
        - Balance Transactions
        - Charges
        - Customers
        - Events
        - Invoices
        - Payment Intents
        - Payment Methods
        - Payouts
        - Refunds
        - Subscriptions
        """
        async with httpx.AsyncClient() as client:
            # 1) Single Balance resource
            async for balance_chunk in self._generate_balance_chunk(client):
                yield balance_chunk

            # 2) Balance Transactions
            async for txn_chunk in self._generate_balance_transaction_chunks(client):
                yield txn_chunk

            # 3) Charges
            async for charge_chunk in self._generate_charge_chunks(client):
                yield charge_chunk

            # 4) Customers
            async for customer_chunk in self._generate_customer_chunks(client):
                yield customer_chunk

            # 5) Events
            async for event_chunk in self._generate_event_chunks(client):
                yield event_chunk

            # 6) Invoices
            async for invoice_chunk in self._generate_invoice_chunks(client):
                yield invoice_chunk

            # 7) Payment Intents
            async for pi_chunk in self._generate_payment_intent_chunks(client):
                yield pi_chunk

            # 8) Payment Methods
            async for pm_chunk in self._generate_payment_method_chunks(client):
                yield pm_chunk

            # 9) Payouts
            async for payout_chunk in self._generate_payout_chunks(client):
                yield payout_chunk

            # 10) Refunds
            async for refund_chunk in self._generate_refund_chunks(client):
                yield refund_chunk

            # 11) Subscriptions
            async for sub_chunk in self._generate_subscription_chunks(client):
                yield sub_chunk
