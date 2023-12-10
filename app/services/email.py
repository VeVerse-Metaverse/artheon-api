import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Union

from app import models
from app.crud.entity import EntityParameterError

SMTP_URL = "xxx"
SMTP_PORT = 465
# noinspection SpellCheckingInspection
SMTP_USER = "xxx"
# noinspection SpellCheckingInspection
SMTP_PASS = "xxx"


class Service:
    def send_to_user(self, subject: str, text: str, html: str, receiver: models.User, sender_email: str = "no-reply@veverse.com"):
        if not receiver.email:
            raise EntityParameterError('no email')

        if not receiver.allow_emails:
            raise EntityParameterError('user disabled emails')

        self.send(subject=subject, text=text, html=html, sender_email=sender_email, receiver_emails=receiver.email)

    def check_email(self, email):
        regex = '^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,63}$'
        if (re.search(regex, email)):
            return True
        else:
            return False

    # noinspection PyMethodMayBeStatic
    def send(self, subject: str, text: str, html: str, sender_email: str, receiver_emails: Union[str, List[str]]):
        if not self.check_email(sender_email):
            return False

        if isinstance(receiver_emails, str):
            if not self.check_email(receiver_emails):
                return False
        elif isinstance(receiver_emails, list):
            for email in receiver_emails:
                if not self.check_email(email):
                    return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        if isinstance(receiver_emails, list):
            message["To"] = ",".join(receiver_emails)
        elif isinstance(receiver_emails, str):
            message["To"] = receiver_emails
        else:
            return False

        text_payload = MIMEText(text, "plain")
        html_payload = MIMEText(html, "html")

        message.attach(text_payload)
        message.attach(html_payload)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_URL, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            result: Dict = server.sendmail(
                sender_email, receiver_emails, message.as_string()
            )
            if len(result) == 0:
                return True

        return False
