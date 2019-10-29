import config
import os
import datetime
import threading
import logging
import string

from google.cloud import storage
from exchangelib import Credentials, Account, Configuration, FileAttachment


# Process individual message
def process_message(account, bucket, message):
    logging.info('Started uploading of e-mail')
    
    now = datetime.datetime.date(message.datetime_sent)
    destination_path = '%04d/%02d/%02d/%s' % (now.year, now.month, now.day,
                                              format_filename(message.id))

    # Write original e-mail message to GCS storage
    try:
        message_text_blob = bucket.blob('%s/original_email.html' % (
            destination_path))
        message_text_blob.upload_from_string(message.unique_body)
    finally:
        logging.info("Finished upload of original e-mail content")

    # Write attachments to GCS storage
    for attachment in message.attachments:
        if isinstance(attachment, FileAttachment):
            try:
                path = '%s/%s' % (destination_path, attachment.name)

                blob = bucket.blob(path)
                blob.upload_from_string(attachment.content,
                                        content_type=attachment.content_type)
            finally:
                logging.info("Finished upload of attachment '{}'".format(
                    attachment.name))

    logging.info('Finished uploading of e-mail')


# Initialize exchangelib account
def main():
    # Initialize connection to Exchange Web Services
    acc_credentials = Credentials(username=config.EXCHANGE_USERNAME,
                                  password=config.EXCHANGE_PASSWORD)
    acc_config = Configuration(
        service_endpoint=config.EXCHANGE_URL, credentials=acc_credentials,
        auth_type='basic')
    account = Account(primary_smtp_address=config.EXCHANGE_USERNAME,
                      config=acc_config, autodiscover=False,
                      access_type='delegate')

    # Initialise GCP bucket
    client = storage.Client()
    bucket = client.get_bucket(config.GCP_BUCKET_NAME)

    if account.inbox.unread_count > 0:
        for message in account.inbox.filter(is_read=False).order_by(
                '-datetime_received')[:100]:
            process_message(account=account, bucket=bucket, message=message)


def format_filename(s):
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ', '_') 
    return filename


if __name__ == '__main__':
    main()
