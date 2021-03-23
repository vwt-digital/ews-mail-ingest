import json
import logging

from gobits import Gobits
from google.cloud.pubsub_v1 import PublisherClient
from requests import Request

from bleach import Cleaner, sanitizer
from config import ALLOWED_HTML_BODY_TAGS, ATTACHMENTS_TO_STORE
from mail import Attachment, Email


class PublishService:
    _publisher: PublisherClient
    _topic_name: str
    _request: Request

    def __init__(self, topic_name: str, request: Request):
        self._publisher = PublisherClient()
        self._topic_name = topic_name
        self._request = request

    def _publish_message(self, message_name, message):
        metadata = Gobits.from_request(request=self._request)
        try:
            my_gobits = [metadata.to_json()]
        except:  # noqa: E722
            my_gobits = []
        message_to_publish = {"gobits": my_gobits, message_name: message}
        print(json.dumps(message_to_publish))
        self._publisher.publish(
            self._topic_name, bytes(json.dumps(message_to_publish).encode("utf-8"))
        )


class MailPublishService(PublishService):
    def _convert_email_to_message(self, email: Email):
        allowed_html_body_tags = sanitizer.ALLOWED_TAGS + ALLOWED_HTML_BODY_TAGS

        if ATTACHMENTS_TO_STORE:
            return {
                "sent_on": email.time_sent.isoformat(),
                "received_on": email.time_received.isoformat(),
                "subject": self.parse_html_content(email.subject, tags=[]),
                "sender": email.sender,
                "recipient": email.receiver,
                "body": self.parse_html_content(
                    email.body, tags=allowed_html_body_tags
                ),
                "attachments": [
                    self._convert_attachment_to_message(attachment)
                    for attachment in email.attachments
                    if attachment.content_type in ATTACHMENTS_TO_STORE
                ],
            }

        return {
            "sent_on": email.time_sent.isoformat(),
            "received_on": email.time_received.isoformat(),
            "subject": self.parse_html_content(email.subject, tags=[]),
            "sender": email.sender,
            "recipient": email.receiver,
            "body": self.parse_html_content(email.body, tags=allowed_html_body_tags),
            "attachments": [],
        }

    def _convert_attachment_to_message(self, attachment: Attachment):
        return {
            "mimetype": attachment.content_type,
            "bucket": attachment.storage_bucket,
            "file_name": attachment.name,
            "full_path": attachment.storage_filename,
        }

    def publish_email(self, email: Email):
        message = self._convert_email_to_message(email)

        self._publish_message("email", message)

        logging.info("Published message for email {}".format(email.uuid))

    def parse_html_content(self, html, **kwargs):
        if html is None:
            return None
        cleaner = Cleaner(**kwargs, strip=True)
        return cleaner.clean(html)
