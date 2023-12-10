import json
import logging
import os
import secrets
import string
import uuid
from typing import Optional

import stripe as stripe
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app import schemas, crud, models
from app.crud.entity import EntityNotFoundError
from app.dependencies import database
from app.schemas import StripeWebHookData

router = APIRouter()

logger = logging.getLogger("veverse")


# This is your Stripe CLI webhook secret for testing your endpoint locally.
# local_test_endpoint_secret = ''

# Stripe webhook
@router.post("/webhook")
async def stripe_webhook(request: Request,
                         request_data: StripeWebHookData,
                         stripe_signature: Optional[str] = Header(None),
                         db: Session = Depends(database.session)):
    webhook_secret = os.getenv('STRIPE_WEBHOOK_ENDPOINT_SECRET')

    request_body_raw = await request.body()

    params = {"type": request_data.type, "data": request_data.data, "signature": stripe_signature}
    action = schemas.ApiActionCreate(method="post", route="/stripe-webhook/{id}", params=params, result=None)
    crud.user.report_api_action_internal(db, action=action)

    logger.info('webhook type: <| ' + request_data.type + ' |>')

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload=request_body_raw, sig_header=stripe_signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            logger.warning('exception: ' + str(e))
            return e
        event_type = event['type']
    else:
        data = request_data.data
        event_type = request_data.type

    data_object = data['object']

    # Handle the event
    if event_type == 'account.updated':
        account = data_object
    elif event_type == 'account.application.authorized':
        application = data_object
    elif event_type == 'account.application.deauthorized':
        application = data_object
    elif event_type == 'account.external_account.created':
        external_account = data_object
    elif event_type == 'account.external_account.deleted':
        external_account = data_object
    elif event_type == 'account.external_account.updated':
        external_account = data_object
    elif event_type == 'application_fee.created':
        application_fee = data_object
    elif event_type == 'application_fee.refunded':
        application_fee = data_object
    elif event_type == 'application_fee.refund.updated':
        refund = data_object
    elif event_type == 'balance.available':
        balance = data_object
    elif event_type == 'billing_portal.configuration.created':
        configuration = data_object
    elif event_type == 'billing_portal.configuration.updated':
        configuration = data_object
    elif event_type == 'billing_portal.session.created':
        session = data_object
    elif event_type == 'capability.updated':
        capability = data_object
    elif event_type == 'cash_balance.funds_available':
        cash_balance = data_object
    elif event_type == 'charge.captured':
        charge = data_object
    elif event_type == 'charge.expired':
        charge = data_object
    elif event_type == 'charge.failed':
        charge = data_object
    elif event_type == 'charge.pending':
        charge = data_object
    elif event_type == 'charge.refunded':
        charge = data_object
    elif event_type == 'charge.succeeded':
        charge: stripe.Charge = data_object
        charge_id = charge["id"]
        transaction_id = charge["balance_transaction"]
        billing_details = charge["billing_details"]
        email = billing_details["email"]
        receipt_url = charge["receipt_url"]
        currency = charge["currency"]
        amount = charge["amount_captured"]
        status = charge["status"]
        payment_intent_id = charge["payment_intent"]
        payment_method_id = charge["payment_method"]

        try:
            user = crud.user._get_by_email_for_auth(db=db, email=email)
            user_id = user.id
            user_name = user.name
        except EntityNotFoundError:
            user_name = email.split('@')[0]
            password = ''.join((secrets.choice(string.ascii_letters + string.digits) for _ in range(8)))
            user_create_schema = schemas.UserCreate(email=email, password=password, name=user_name)
            user = crud.user.create(db=db, requester=None, entity=user_create_schema)
            crud.user.activate_by_email_internal(db=db, email=email)
            user_id = user.id

        event_name = f"{user_name} event"
        event_create_schema = schemas.EventCreate(name=event_name, title=event_name, summary='', description='', public=True, starts_at=None, ends_at=None, type=None)
        event = crud.event.create_for_requester(db=db, requester=user, source=event_create_schema)
        event_id = event.id

        payment = models.Payment(
            id=uuid.uuid4().hex,
            user_id=user_id,
            entity_id=event_id,
            charge_id=charge_id,
            balance_transaction_id=transaction_id,
            amount=amount,
            email=email,
            currency=currency,
            payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id,
            receipt_url=receipt_url,
            status=status,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        event.payment_id = payment.id
        db.add(event)
        db.commit()
    elif event_type == 'charge.updated':
        charge = data_object
    elif event_type == 'charge.dispute.closed':
        dispute = data_object
    elif event_type == 'charge.dispute.created':
        dispute = data_object
    elif event_type == 'charge.dispute.funds_reinstated':
        dispute = data_object
    elif event_type == 'charge.dispute.funds_withdrawn':
        dispute = data_object
    elif event_type == 'charge.dispute.updated':
        dispute = data_object
    elif event_type == 'charge.refund.updated':
        refund = data_object
    elif event_type == 'checkout.session.async_payment_failed':
        session = data_object
    elif event_type == 'checkout.session.async_payment_succeeded':
        session = data_object
    elif event_type == 'checkout.session.completed':
        session = data_object
    elif event_type == 'checkout.session.expired':
        session = data_object
    elif event_type == 'coupon.created':
        coupon = data_object
    elif event_type == 'coupon.deleted':
        coupon = data_object
    elif event_type == 'coupon.updated':
        coupon = data_object
    elif event_type == 'credit_note.created':
        credit_note = data_object
    elif event_type == 'credit_note.updated':
        credit_note = data_object
    elif event_type == 'credit_note.voided':
        credit_note = data_object
    elif event_type == 'customer.created':
        customer = data_object
    elif event_type == 'customer.deleted':
        customer = data_object
    elif event_type == 'customer.updated':
        customer = data_object
    elif event_type == 'customer.discount.created':
        discount = data_object
    elif event_type == 'customer.discount.deleted':
        discount = data_object
    elif event_type == 'customer.discount.updated':
        discount = data_object
    elif event_type == 'customer.source.created':
        source = data_object
    elif event_type == 'customer.source.deleted':
        source = data_object
    elif event_type == 'customer.source.expiring':
        source = data_object
    elif event_type == 'customer.source.updated':
        source = data_object
    elif event_type == 'customer.subscription.created':
        subscription = data_object
    elif event_type == 'customer.subscription.deleted':
        subscription = data_object
    elif event_type == 'customer.subscription.pending_update_applied':
        subscription = data_object
    elif event_type == 'customer.subscription.pending_update_expired':
        subscription = data_object
    elif event_type == 'customer.subscription.trial_will_end':
        subscription = data_object
    elif event_type == 'customer.subscription.updated':
        subscription = data_object
    elif event_type == 'customer.tax_id.created':
        tax_id = data_object
    elif event_type == 'customer.tax_id.deleted':
        tax_id = data_object
    elif event_type == 'customer.tax_id.updated':
        tax_id = data_object
    elif event_type == 'file.created':
        file = data_object
    elif event_type == 'financial_connections.account.created':
        account = data_object
    elif event_type == 'financial_connections.account.deactivated':
        account = data_object
    elif event_type == 'financial_connections.account.disconnected':
        account = data_object
    elif event_type == 'financial_connections.account.reactivated':
        account = data_object
    elif event_type == 'financial_connections.account.refreshed_balance':
        account = data_object
    elif event_type == 'identity.verification_session.canceled':
        verification_session = data_object
    elif event_type == 'identity.verification_session.created':
        verification_session = data_object
    elif event_type == 'identity.verification_session.processing':
        verification_session = data_object
    elif event_type == 'identity.verification_session.requires_input':
        verification_session = data_object
    elif event_type == 'identity.verification_session.verified':
        verification_session = data_object
    elif event_type == 'invoice.created':
        invoice = data_object
    elif event_type == 'invoice.deleted':
        invoice = data_object
    elif event_type == 'invoice.finalization_failed':
        invoice = data_object
    elif event_type == 'invoice.finalized':
        invoice = data_object
    elif event_type == 'invoice.marked_uncollectible':
        invoice = data_object
    elif event_type == 'invoice.paid':
        invoice = data_object
    elif event_type == 'invoice.payment_action_required':
        invoice = data_object
    elif event_type == 'invoice.payment_failed':
        invoice = data_object
    elif event_type == 'invoice.payment_succeeded':
        invoice = data_object
    elif event_type == 'invoice.sent':
        invoice = data_object
    elif event_type == 'invoice.upcoming':
        invoice = data_object
    elif event_type == 'invoice.updated':
        invoice = data_object
    elif event_type == 'invoice.voided':
        invoice = data_object
    elif event_type == 'invoiceitem.created':
        invoiceitem = data_object
    elif event_type == 'invoiceitem.deleted':
        invoiceitem = data_object
    elif event_type == 'invoiceitem.updated':
        invoiceitem = data_object
    elif event_type == 'issuing_authorization.created':
        issuing_authorization = data_object
    elif event_type == 'issuing_authorization.updated':
        issuing_authorization = data_object
    elif event_type == 'issuing_card.created':
        issuing_card = data_object
    elif event_type == 'issuing_card.updated':
        issuing_card = data_object
    elif event_type == 'issuing_cardholder.created':
        issuing_cardholder = data_object
    elif event_type == 'issuing_cardholder.updated':
        issuing_cardholder = data_object
    elif event_type == 'issuing_dispute.closed':
        issuing_dispute = data_object
    elif event_type == 'issuing_dispute.created':
        issuing_dispute = data_object
    elif event_type == 'issuing_dispute.funds_reinstated':
        issuing_dispute = data_object
    elif event_type == 'issuing_dispute.submitted':
        issuing_dispute = data_object
    elif event_type == 'issuing_dispute.updated':
        issuing_dispute = data_object
    elif event_type == 'issuing_transaction.created':
        issuing_transaction = data_object
    elif event_type == 'issuing_transaction.updated':
        issuing_transaction = data_object
    elif event_type == 'mandate.updated':
        mandate = data_object
    elif event_type == 'order.created':
        order = data_object
    elif event_type == 'order.payment_failed':
        order = data_object
    elif event_type == 'order.payment_succeeded':
        order = data_object
    elif event_type == 'order.updated':
        order = data_object
    elif event_type == 'order_return.created':
        order_return = data_object
    elif event_type == 'payment_intent.amount_capturable_updated':
        payment_intent = data_object
    elif event_type == 'payment_intent.canceled':
        payment_intent = data_object
    elif event_type == 'payment_intent.created':
        payment_intent = data_object
    elif event_type == 'payment_intent.partially_funded':
        payment_intent = data_object
    elif event_type == 'payment_intent.payment_failed':
        payment_intent = data_object
    elif event_type == 'payment_intent.processing':
        payment_intent = data_object
    elif event_type == 'payment_intent.requires_action':
        payment_intent = data_object
    elif event_type == 'payment_intent.succeeded':
        payment_intent = data_object
    elif event_type == 'payment_link.created':
        payment_link = data_object
    elif event_type == 'payment_link.updated':
        payment_link = data_object
    elif event_type == 'payment_method.attached':
        payment_method = data_object
    elif event_type == 'payment_method.automatically_updated':
        payment_method = data_object
    elif event_type == 'payment_method.detached':
        payment_method = data_object
    elif event_type == 'payment_method.updated':
        payment_method = data_object
    elif event_type == 'payout.canceled':
        payout = data_object
    elif event_type == 'payout.created':
        payout = data_object
    elif event_type == 'payout.failed':
        payout = data_object
    elif event_type == 'payout.paid':
        payout = data_object
    elif event_type == 'payout.updated':
        payout = data_object
    elif event_type == 'person.created':
        person = data_object
    elif event_type == 'person.deleted':
        person = data_object
    elif event_type == 'person.updated':
        person = data_object
    elif event_type == 'plan.created':
        plan = data_object
    elif event_type == 'plan.deleted':
        plan = data_object
    elif event_type == 'plan.updated':
        plan = data_object
    elif event_type == 'price.created':
        price = data_object
    elif event_type == 'price.deleted':
        price = data_object
    elif event_type == 'price.updated':
        price = data_object
    elif event_type == 'product.created':
        product = data_object
    elif event_type == 'product.deleted':
        product = data_object
    elif event_type == 'product.updated':
        product = data_object
    elif event_type == 'promotion_code.created':
        promotion_code = data_object
    elif event_type == 'promotion_code.updated':
        promotion_code = data_object
    elif event_type == 'quote.accepted':
        quote = data_object
    elif event_type == 'quote.canceled':
        quote = data_object
    elif event_type == 'quote.created':
        quote = data_object
    elif event_type == 'quote.finalized':
        quote = data_object
    elif event_type == 'radar.early_fraud_warning.created':
        early_fraud_warning = data_object
    elif event_type == 'radar.early_fraud_warning.updated':
        early_fraud_warning = data_object
    elif event_type == 'recipient.created':
        recipient = data_object
    elif event_type == 'recipient.deleted':
        recipient = data_object
    elif event_type == 'recipient.updated':
        recipient = data_object
    elif event_type == 'reporting.report_run.failed':
        report_run = data_object
    elif event_type == 'reporting.report_run.succeeded':
        report_run = data_object
    elif event_type == 'review.closed':
        review = data_object
    elif event_type == 'review.opened':
        review = data_object
    elif event_type == 'setup_intent.canceled':
        setup_intent = data_object
    elif event_type == 'setup_intent.created':
        setup_intent = data_object
    elif event_type == 'setup_intent.requires_action':
        setup_intent = data_object
    elif event_type == 'setup_intent.setup_failed':
        setup_intent = data_object
    elif event_type == 'setup_intent.succeeded':
        setup_intent = data_object
    elif event_type == 'sigma.scheduled_query_run.created':
        scheduled_query_run = data_object
    elif event_type == 'sku.created':
        sku = data_object
    elif event_type == 'sku.deleted':
        sku = data_object
    elif event_type == 'sku.updated':
        sku = data_object
    elif event_type == 'source.canceled':
        source = data_object
    elif event_type == 'source.chargeable':
        source = data_object
    elif event_type == 'source.failed':
        source = data_object
    elif event_type == 'source.mandate_notification':
        source = data_object
    elif event_type == 'source.refund_attributes_required':
        source = data_object
    elif event_type == 'source.transaction.created':
        transaction = data_object
    elif event_type == 'source.transaction.updated':
        transaction = data_object
    elif event_type == 'subscription_schedule.aborted':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.canceled':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.completed':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.created':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.expiring':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.released':
        subscription_schedule = data_object
    elif event_type == 'subscription_schedule.updated':
        subscription_schedule = data_object
    elif event_type == 'tax_rate.created':
        tax_rate = data_object
    elif event_type == 'tax_rate.updated':
        tax_rate = data_object
    elif event_type == 'terminal.reader.action_failed':
        reader = data_object
    elif event_type == 'terminal.reader.action_succeeded':
        reader = data_object
    elif event_type == 'test_helpers.test_clock.advancing':
        test_clock = data_object
    elif event_type == 'test_helpers.test_clock.created':
        test_clock = data_object
    elif event_type == 'test_helpers.test_clock.deleted':
        test_clock = data_object
    elif event_type == 'test_helpers.test_clock.internal_failure':
        test_clock = data_object
    elif event_type == 'test_helpers.test_clock.ready':
        test_clock = data_object
    elif event_type == 'topup.canceled':
        topup = data_object
    elif event_type == 'topup.created':
        topup = data_object
    elif event_type == 'topup.failed':
        topup = data_object
    elif event_type == 'topup.reversed':
        topup = data_object
    elif event_type == 'topup.succeeded':
        topup = data_object
    elif event_type == 'transfer.created':
        transfer = data_object
    elif event_type == 'transfer.failed':
        transfer = data_object
    elif event_type == 'transfer.paid':
        transfer = data_object
    elif event_type == 'transfer.reversed':
        transfer = data_object
    elif event_type == 'transfer.updated':
        transfer = data_object
    # ... handle other event types
    else:
        logger.warning('Unhandled event type {}'.format(event_type))

    return {"status": "success"}
