import json
import logging

from gobits import Gobits
from google.cloud.pubsub_v1 import PublisherClient
from requests import Request

from mail import Email, Attachment


class PublishService:
    publisher: PublisherClient
    topic_name: str
    request: Request

    def __init__(self, topic_name: str, request: Request):
        self.publisher = PublisherClient()
        self.topic_name = topic_name
        self.request = request

    def _publish_message(self, message_name, message):
        bits = Gobits(request=self.request)
        message_to_publish = {'gobits': [bits.to_json()], message_name: message}
        self.publisher.publish(self.topic_name, bytes(json.dumps(message_to_publish).encode('utf-8')))


class MailPublishService(PublishService):
    def _convert_email_to_message(self, email: Email):
        return {
            'received_on': email.time_received.isoformat(),
            'sender': email.sender,
            'recipient': email.receiver,
            'title': email.subject,
            'body': email.body,
            'attachments': [self._convert_attachment_to_message(attachment) for attachment in email.attachments]
        }

    def _convert_attachment_to_message(self, attachment: Attachment):
        return {
            'mimetype': attachment.content_type,
            'bucket': attachment.storage_bucket,
            'file_name':  attachment.storage_filename,
            'full_path': '{}/{}'.format(attachment.storage_bucket, attachment.storage_filename)
        }

    def publish_email(self, email: Email):
        message = self._convert_email_to_message(email)

        self._publish_message('email', message)

        logging.info('Published message for email {}'.format(email.uuid))
