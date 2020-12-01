import json
import logging
import os

import requests

from utils import get_secret
from config import EMAIL_ADDRESSES, PROJECT_ID, BUCKET_NAME, TOPIC_NAME
from mail import EWSEmailService
from storage import EmailAttachmentStorageService
from publish import MailPublishService

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


def handler(request):
    storage_service = EmailAttachmentStorageService(BUCKET_NAME)
    publish_service = MailPublishService(TOPIC_NAME, request)

    identifier = request.args.get('identifier', None)

    if identifier is None:
        raise ValueError("No email address specified.")

    credentials = EMAIL_ADDRESSES.get(identifier, None)

    if credentials is None:
        raise ValueError("No credentials found for given email address.")

    email_address = credentials['email']
    password = json.loads(get_secret(PROJECT_ID, credentials['secret_id'])).get('password')
 
    email_service = EWSEmailService(email_address=email_address,
                                    password=password,
                                    folder=credentials.get('folder', None),
                                    alias=credentials.get('alias', None))

    emails = email_service.retrieve_unread_emails()

    for email in emails:
        if storage_service.store_attachments(email, identifier) > 0:
            publish_service.publish_email(email)
        else:
            logging.info('Skip publishing of email {} for inbox {}. No supported attachments found.'
                         .format(email.uuid, identifier))

        # email.mark_email_as_read(email)
        logging.info('Marked email {} as read'.format(email.uuid))


if __name__ == '__main__':
    mock_request = requests.session()
    mock_request.method = "POST"
    mock_request.args = {
        'email': 'invoicetest001'
    }
    mock_request.data = b'{}'
    handler(mock_request)
