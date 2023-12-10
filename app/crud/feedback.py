import re
import uuid
from string import Template
from typing import Any

import inject
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app import crud, models, templates
from app.config import settings
from app.crud.entity import CRUDBase, EntityParameterError, EntityAccessError
from app.models import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate
from app.services import email


class CRUDFeedback(CRUDBase[Feedback, FeedbackCreate, FeedbackUpdate]):
    email_service = inject.attr(email.Service)

    def create_by_user(self, db: Session, *, source_object: FeedbackCreate, requester: models.User) -> Feedback:
        if not source_object:
            raise EntityParameterError('no fields')

        if not requester:
            raise EntityParameterError('no requester')

        if not requester.is_active:
            raise EntityAccessError('inactive')

        if requester.is_banned:
            raise EntityAccessError('banned')

        source_data = jsonable_encoder(source_object, by_alias=False)
        # Create a model object
        model_object = self.model(**source_data)
        if not model_object.id:
            model_object.id = uuid.uuid4().hex
        if not model_object.email or not crud.user.check_email(model_object.email):
            if not crud.user.check_email(requester.email):
                raise EntityParameterError('invalid email')
            model_object.email = requester.email
        model_object.user_id = requester.id
        db.add(model_object)
        db.commit()
        db.refresh(model_object)

        text_template_str = templates.email.feedback_text
        text_template = Template(text_template_str)
        text = text_template.substitute(name=requester.name, id=requester.id, email=model_object.email, text=model_object.text)

        html_template_str = templates.email.feedback_html
        html_template = Template(html_template_str)
        html = html_template.substitute(name=requester.name, id=requester.id, email=model_object.email, text=model_object.text)

        self.email_service.send(subject="Feedback", text=text, html=html,
                                sender_email="no-reply@artheon.co", receiver_emails=["feedback@artheon.co"])

        crud.user.grant_experience(db, requester=requester, experience=settings.experience.rewards.feedback)

        return model_object


feedback = CRUDFeedback(Feedback)
