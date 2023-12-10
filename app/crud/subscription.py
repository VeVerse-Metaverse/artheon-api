import logging
import re
import uuid
from string import Template

import inject
from sqlalchemy.orm import Session

from app import models, schemas, templates
from app.crud.entity import CRUDBase, EntityParameterError, EntityAccessError
from app.services import email


class CRUDSubscription(CRUDBase[models.Subscription, schemas.Subscription, schemas.Subscription]):
    email_service = inject.attr(email.Service)

    def subscribe(self, email: str, platform: str, notes: str, type: str, name: str, *, db: Session, requester: models.User):
        if not requester:
            raise EntityParameterError('no requester')

        requester = self.prepare_user(db, user=requester)

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.fullmatch(email_regex, email):
            # Create and store a subscription
            sub = models.Subscription()
            sub.id = uuid.uuid4().hex
            sub.email = email
            sub.platform = platform
            sub.notes = notes
            sub.type = type
            sub.name = name
            db.add(sub)
            db.commit()
            db.refresh(sub)

            # Send notification
            try:
                text_template_str = templates.email.subscription_text
                text_template = Template(text_template_str)
                text = text_template.substitute(name=name, email=email, platform=platform, notes=notes, type=type, id=sub.id)

                html_template_str = templates.email.subscription_html
                html_template = Template(html_template_str)
                html = html_template.substitute(name=name, email=email, platform=platform, notes=notes, type=type, id=sub.id)

                result = self.email_service.send(subject="VeVerse - Subscription", text=text, html=html, sender_email="no-reply@veverse.com", receiver_emails="no-reply@veverse.com")
                if not result:
                    logging.warning("failed to send subscription notification email")
            except:
                logging.warning("failed to send subscription notification email")

            return sub
        else:
            raise EntityParameterError('email is not valid')


subscription = CRUDSubscription(models.Subscription)
