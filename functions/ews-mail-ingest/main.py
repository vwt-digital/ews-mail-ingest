import logging
import os

import requests

from storage.email_attachment_storage import EmailAttachmentStorageService
from utils import get_secret
from config import EMAIL_ADDRESSES, PROJECT_ID, BUCKET_NAME, TOPIC_NAME, ERROR_EMAIL_ADDRESS, ERROR_EMAIL_MESSAGE
from mail import EWSEmailService
from publish import MailPublishService

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


def handler(request):
    storage_service = None
    if BUCKET_NAME:
        storage_service = EmailAttachmentStorageService(BUCKET_NAME)
    publish_service = MailPublishService(TOPIC_NAME, request)

    identifier = request.args.get('identifier', None)

    if identifier is None:
        raise ValueError("No email address specified.")

    credentials = EMAIL_ADDRESSES.get(identifier, None)

    if credentials is None:
        raise ValueError("No credentials found for given email address.")

    email_address = credentials['email']
    password = get_secret(PROJECT_ID, credentials['secret_id'])

    email_service = EWSEmailService(email_address=email_address,
                                    password=password,
                                    folder=credentials.get('folder', None),
                                    alias=credentials.get('alias', None))

    emails = email_service.retrieve_unread_emails()

    for email in emails:
        logging.info('Processing email {} from sender {}'.format(email.subject, email.sender))
        try:
            if storage_service:
                storage_service.store_attachments(email, identifier)
            publish_service.publish_email(email)
            email.mark_as_read()
            logging.info('Marked email {} as read'.format(email.uuid))
        except Exception as e:
            if ERROR_EMAIL_ADDRESS:
                logging.info("Error processing email '{}' in mailbox {}. Forwarding to {}"
                             .format(email.subject,
                                     credentials.get('alias', email_address),
                                     ERROR_EMAIL_ADDRESS),
                             exc_info=True)

                email.forward(ERROR_EMAIL_ADDRESS,
                              None,
                              ERROR_EMAIL_MESSAGE)
                email.mark_as_read()
            else:
                logging.error("Error processing email '{}' in mailbox {} because of {}"
                              .format(email.subject,
                                      credentials.get('alias', email_address),
                                      e),
                              exc_info=True)


if __name__ == '__main__':
    mock_request = requests.session()
    mock_request.method = "POST"
    mock_request.args = {
        'identifier': 'invoicetest200'
    }
    mock_request.data = b'{}'
    handler(mock_request)
