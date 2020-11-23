import json

from utils import get_secret
from config import EMAIL_ADDRESSES, PROJECT_ID
from mail import EmailService
from storage import EmailAttachmentStorageService
from publish import MailPublishService


def handler(request):
    email_address = request.args.get('email', None)

    if email_address is None:
        raise ValueError("No email address specified.")

    credentials = EMAIL_ADDRESSES.get(email_address, None)

    if credentials is None:
        raise ValueError("No credentials found for given email address.")

    secret = get_secret(PROJECT_ID, credentials['secret_id'])
    password = json.dumps(secret)['password']

    storage_service = EmailAttachmentStorageService()
    publish_service = MailPublishService()

    email_service = EmailService(email_address=email_address, password=password)
    emails = email_service.retrieve_unread_emails()

    for email in emails:
        storage_service.store_attachments(email)
        publish_service.publish_email(email)
        email.mark_email_as_read(email)


if __name__ == '__main__':
    handler(None)
