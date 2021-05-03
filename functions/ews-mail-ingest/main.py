import logging
import os

import requests
from requests.exceptions import ConnectionError
from retry import retry

from config import (BUCKET_NAME, EMAIL_ADDRESSES, ERROR_EMAIL_ADDRESS,
                    ERROR_EMAIL_MESSAGE, PROJECT_ID, TOPIC_NAME)
from mail import EWSEmailService
from publish import MailPublishService
from storage.email_attachment_storage import EmailAttachmentStorageService
from utils import get_secret

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


@retry(ConnectionError, tries=3, delay=2, logger=None, backoff=2)
def publish_and_mark(
    storage_service: EmailAttachmentStorageService,
    publish_service: MailPublishService,
    email,
    identifier,
):
    if storage_service:
        storage_service.store_attachments(email, identifier)
    publish_service.publish_email(email)
    email.mark_as_read()
    logging.info("Marked email {} as read".format(email.uuid))


def handler(request):
    storage_service = None
    if BUCKET_NAME:
        storage_service = EmailAttachmentStorageService(BUCKET_NAME)
    publish_service = MailPublishService(TOPIC_NAME, request)

    identifier = request.args.get("identifier", None)

    if identifier is None:
        raise ValueError("No email address specified.")

    credentials = EMAIL_ADDRESSES.get(identifier, None)

    if credentials is None:
        raise ValueError("No credentials found for given email address.")

    email_address = credentials["email"]
    password = get_secret(PROJECT_ID, credentials["secret_id"])

    email_service = EWSEmailService(
        email_address=email_address,
        password=password,
        folder=credentials.get("folder", None),
        alias=credentials.get("alias", None),
    )

    emails = email_service.retrieve_unread_emails()

    for email in emails:
        logging.info(
            "Processing email {} from sender {}".format(email.subject, email.sender)
        )
        try:
            publish_and_mark(storage_service, publish_service, email, identifier)
        except Exception as e:
            if ERROR_EMAIL_ADDRESS:
                logging.info(
                    "Error processing email '{}' in mailbox {}. Forwarding to {}".format(
                        email.subject,
                        credentials.get("alias", email_address),
                        ERROR_EMAIL_ADDRESS,
                    ),
                    exc_info=True,
                )

                email.forward(ERROR_EMAIL_ADDRESS, None, ERROR_EMAIL_MESSAGE)
                email.mark_as_read()
            else:
                logging.error(
                    "Error processing email '{}' in mailbox {} because of {}".format(
                        email.subject, credentials.get("alias", email_address), e
                    ),
                    exc_info=True,
                )


if __name__ == "__main__":
    mock_request = requests.session()
    mock_request.method = "POST"
    mock_request.args = {"identifier": "mail-identifier"}
    mock_request.data = b"{}"
    handler(mock_request)
