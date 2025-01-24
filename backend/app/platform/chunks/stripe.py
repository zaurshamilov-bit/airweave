"""Stripe chunk schemas.

Based on the Stripe API reference (2024-12-18.acacia), we define chunk schemas for
commonly used Stripe Core Resources: Customers, Invoices, Charges, Subscriptions,
Payment Intents, Balance, Balance Transactions, Events, Payouts, Payment Methods,
and Refunds.

These schemas follow the same style as other connectors (e.g., Asana, HubSpot, Todoist),
where each chunk class inherits from our BaseChunk and adds relevant fields with
shared or per-resource metadata as needed.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class StripeBalanceChunk(BaseChunk):
    """Schema for Stripe Balance resource.

    https://stripe.com/docs/api/balance/balance_object
    """

    # Lists of objects describing funds in various currency amounts.
    # Each object typically contains {"amount": <int>, "currency": <str>, ...}
    available: List[Dict[str, Union[int, str]]] = Field(
        default_factory=list,
        description="Funds that are available to be paid out, broken down by currency",
    )
    pending: List[Dict[str, Union[int, str]]] = Field(
        default_factory=list,
        description="Funds not yet available, broken down by currency",
    )
    instant_available: Optional[List[Dict[str, Union[int, str]]]] = Field(
        None,
        description="Funds available for Instant Payouts (if enabled)",
    )
    connect_reserved: Optional[List[Dict[str, Union[int, str]]]] = Field(
        None,
        description="Funds reserved for connected accounts (if using Connect)",
    )
    livemode: bool = Field(False, description="Whether this balance is in live mode (vs test mode)")


class StripeBalanceTransactionChunk(BaseChunk):
    """Schema for Stripe Balance Transaction resource.

    https://stripe.com/docs/api/balance_transactions
    """

    amount: Optional[int] = Field(None, description="Gross amount of the transaction, in cents")
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code")
    created_at: Optional[datetime] = Field(
        None, description="Time at which the transaction was created"
    )
    description: Optional[str] = Field(None, description="Text description of the transaction")
    fee: Optional[int] = Field(None, description="Fees (in cents) taken from this transaction")
    fee_details: List[Dict[str, Union[str, int]]] = Field(
        default_factory=list,
        description="Detailed breakdown of fees (type, amount, application, etc.)",
    )
    net: Optional[int] = Field(None, description="Net amount of the transaction, in cents")
    reporting_category: Optional[str] = Field(
        None, description="Reporting category (e.g., 'charge', 'refund', etc.)"
    )
    source: Optional[str] = Field(
        None, description="ID of the charge or other object that caused this balance transaction"
    )
    status: Optional[str] = Field(
        None, description="Status of the balance transaction (e.g., 'available', 'pending')"
    )
    type: Optional[str] = Field(
        None, description="Transaction type (e.g., 'charge', 'refund', 'payout')"
    )


class StripeChargeChunk(BaseChunk):
    """Schema for Stripe Charge chunks.

    https://stripe.com/docs/api/charges
    """

    amount: Optional[int] = Field(None, description="Amount charged in cents")
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code")
    captured: bool = Field(False, description="Whether the charge was captured")
    paid: bool = Field(False, description="Whether the charge was paid")
    refunded: bool = Field(False, description="Whether the charge was refunded")
    created_at: Optional[datetime] = Field(None, description="When the charge was created")
    description: Optional[str] = Field(None, description="Arbitrary description of the charge")
    receipt_url: Optional[str] = Field(None, description="URL to view this charge's receipt")
    customer_id: Optional[str] = Field(
        None, description="ID of the Customer this charge belongs to"
    )
    invoice_id: Optional[str] = Field(
        None, description="ID of the Invoice this charge is linked to (if any)"
    )
    # Example: { "reason": "Purchase of widget" }
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Set of key-value pairs attached to the charge"
    )


class StripeCustomerChunk(BaseChunk):
    """Schema for Stripe Customer chunks.

    https://stripe.com/docs/api/customers
    """

    email: Optional[str] = Field(None, description="The customer's email address")
    phone: Optional[str] = Field(None, description="The customer's phone number")
    name: Optional[str] = Field(None, description="The customer's full name")
    description: Optional[str] = Field(None, description="Arbitrary description of the customer")
    created_at: Optional[datetime] = Field(None, description="When the customer was created")
    currency: Optional[str] = Field(
        None, description="Preferred currency for the customer's recurring payments"
    )
    default_source: Optional[str] = Field(
        None, description="ID of the default payment source (e.g. card) attached to this customer"
    )
    delinquent: bool = Field(
        False, description="Whether the customer has any unpaid/overdue invoices"
    )
    invoice_prefix: Optional[str] = Field(None, description="Prefix for the customer's invoices")
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Set of key-value pairs attached to the customer"
    )


class StripeEventChunk(BaseChunk):
    """Schema for Stripe Event resource.

    https://stripe.com/docs/api/events
    """

    event_type: Optional[str] = Field(
        None,
        description="The event's type (e.g., 'charge.succeeded', 'customer.created')",
    )
    api_version: Optional[str] = Field(None, description="API version used to render event data")
    created_at: Optional[datetime] = Field(
        None, description="When the notification was created (time of the event)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="The event payload. Typically includes 'object' and 'previous_attributes'.",
    )
    livemode: bool = Field(False, description="Whether the event was triggered in live mode")
    pending_webhooks: Optional[int] = Field(
        None, description="Number of webhooks yet to be delivered"
    )
    request: Optional[Dict[str, Any]] = Field(
        None, description="Information on the request that created or triggered the event"
    )


class StripeInvoiceChunk(BaseChunk):
    """Schema for Stripe Invoice chunks.

    https://stripe.com/docs/api/invoices
    """

    customer_id: Optional[str] = Field(
        None, description="The ID of the customer this invoice belongs to"
    )
    number: Optional[str] = Field(
        None, description="A unique, user-facing reference for this invoice"
    )
    status: Optional[str] = Field(
        None, description="Invoice status (e.g., 'draft', 'open', 'paid', 'void')"
    )
    amount_due: Optional[int] = Field(
        None, description="Final amount due in cents (before any payment or credit)"
    )
    amount_paid: Optional[int] = Field(None, description="Amount paid in cents")
    amount_remaining: Optional[int] = Field(
        None, description="Amount remaining to be paid in cents"
    )
    created_at: Optional[datetime] = Field(None, description="When the invoice was created")
    due_date: Optional[datetime] = Field(
        None, description="Date on which payment is due (if applicable)"
    )
    paid: bool = Field(False, description="Whether the invoice has been fully paid")
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code (e.g. 'usd')")
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the invoice",
    )


class StripePaymentIntentChunk(BaseChunk):
    """Schema for Stripe PaymentIntent chunks.

    https://stripe.com/docs/api/payment_intents
    """

    amount: Optional[int] = Field(
        None, description="Amount in cents intended to be collected by this PaymentIntent"
    )
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code")
    status: Optional[str] = Field(
        None,
        description="Status of the PaymentIntent (e.g. 'requires_payment_method', 'succeeded')",
    )
    description: Optional[str] = Field(
        None, description="Arbitrary description for the PaymentIntent"
    )
    created_at: Optional[datetime] = Field(None, description="When the PaymentIntent was created")
    customer_id: Optional[str] = Field(
        None, description="ID of the Customer this PaymentIntent is for (if any)"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Set of key-value pairs attached to the PaymentIntent"
    )


class StripePaymentMethodChunk(BaseChunk):
    """Schema for Stripe PaymentMethod resource.

    https://stripe.com/docs/api/payment_methods
    """

    type: Optional[str] = Field(None, description="Type of the PaymentMethod (card, ideal, etc.)")
    billing_details: Dict[str, Any] = Field(
        default_factory=dict, description="Billing information associated with the PaymentMethod"
    )
    customer_id: Optional[str] = Field(
        None, description="ID of the Customer to which this PaymentMethod is saved (if any)"
    )
    card: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "If the PaymentMethod type is 'card', details about the card " "(brand, last4, etc.)"
        ),
    )
    created_at: Optional[datetime] = Field(None, description="When the PaymentMethod was created")
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the PaymentMethod",
    )


class StripePayoutChunk(BaseChunk):
    """Schema for Stripe Payout resource.

    https://stripe.com/docs/api/payouts
    """

    amount: Optional[int] = Field(None, description="Amount in cents to be transferred")
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code")
    arrival_date: Optional[datetime] = Field(
        None, description="Date the payout is expected to arrive in the bank"
    )
    created_at: Optional[datetime] = Field(None, description="When this payout was created")
    description: Optional[str] = Field(
        None, description="An arbitrary string attached to the payout"
    )
    destination: Optional[str] = Field(
        None, description="ID of the bank account or card the payout was sent to"
    )
    method: Optional[str] = Field(
        None, description="The method used to send this payout (e.g., 'standard', 'instant')"
    )
    status: Optional[str] = Field(
        None, description="Status of the payout (e.g., 'paid', 'pending', 'in_transit')"
    )
    statement_descriptor: Optional[str] = Field(
        None, description="Extra information to be displayed on the user's bank statement"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the payout",
    )


class StripeRefundChunk(BaseChunk):
    """Schema for Stripe Refund resource.

    https://stripe.com/docs/api/refunds
    """

    amount: Optional[int] = Field(None, description="Amount in cents refunded")
    currency: Optional[str] = Field(None, description="Three-letter ISO currency code")
    created_at: Optional[datetime] = Field(None, description="When this refund was created")
    status: Optional[str] = Field(
        None, description="Status of the refund (e.g., 'pending', 'succeeded', 'failed')"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for the refund (duplicate, fraudulent, requested_by_customer, etc.)",
    )
    receipt_number: Optional[str] = Field(
        None, description="Transaction number that appears on email receipts issued for this refund"
    )
    charge_id: Optional[str] = Field(None, description="ID of the charge being refunded")
    payment_intent_id: Optional[str] = Field(
        None, description="ID of the PaymentIntent being refunded (if applicable)"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the refund",
    )


class StripeSubscriptionChunk(BaseChunk):
    """Schema for Stripe Subscription chunks.

    https://stripe.com/docs/api/subscriptions
    """

    customer_id: Optional[str] = Field(
        None, description="The ID of the customer who owns this subscription"
    )
    status: Optional[str] = Field(
        None, description="Status of the subscription (e.g., 'active', 'past_due', 'canceled')"
    )
    current_period_start: Optional[datetime] = Field(
        None, description="Start of the current billing period for this subscription"
    )
    current_period_end: Optional[datetime] = Field(
        None, description="End of the current billing period for this subscription"
    )
    cancel_at_period_end: bool = Field(
        False, description="Whether the subscription will cancel at the end of the current period"
    )
    canceled_at: Optional[datetime] = Field(
        None, description="When the subscription was canceled (if any)"
    )
    created_at: Optional[datetime] = Field(
        None, description="When the subscription was first created"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Set of key-value pairs attached to the subscription",
    )
