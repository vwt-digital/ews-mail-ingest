import config
import os
import logging
import json
import base64
import secrets
import datetime

from exchangelib import Credentials, Account, Configuration, Folder, \
    FileAttachment, errors
from google.cloud import kms_v1, storage, pubsub_v1


# Upload original e-mail message to GCS storage
def process_message_original(bucket, message, path):
    try:
        message_text_blob = bucket.blob('%s/original_email.html' % (
            path))
        message_text_blob.upload_from_string(message.unique_body)
    finally:
        logging.info("Finished upload of original e-mail content")


# Upload attachments to GCS storage
def process_message_attachments(bucket, message, path):
    message_attachments = []
    for attachment in message.attachments:
        if isinstance(attachment, FileAttachment):

            clean_attachment_name = attachment.name.\
                replace(' ', '_').\
                replace('.', '_', attachment.name.count('.') - 1).\
                replace('-', '_')

            try:

                file_path = '%s/%s' % (path, clean_attachment_name)

                blob = bucket.blob(file_path)
                blob.upload_from_string(attachment.content,
                                        content_type=attachment.content_type)

                message_attachments.append({
                    'name': clean_attachment_name,
                    'path': f'gs://{config.GCP_BUCKET_NAME}/{file_path}',
                    'content_type': attachment.content_type,
                })
            finally:
                logging.info("Finished upload of attachment '{}'".format(
                    clean_attachment_name))

    return message_attachments


# Mark e-mail as 'read' and move to specified Inbox folder
def process_message_status(account, message):
    try:
        message.is_read = True
        message.save(update_fields=['is_read'])

        to_folder = account.inbox / config.EXCHANGE_FOLDER_NAME
        message.move(to_folder)
    finally:
        logging.info('Finished moving of e-mail')


# Post message meta info to Pub/Sub topic
def process_message_meta(message, attachments, path, bucket,
                         publisher, topic_name, request):
    try:
        message_meta = {
            'gcp_project': os.environ.get('GCP_PROJECT', ''),
            'execution_id': request.headers.get(
                'Function-Execution-Id', ''),
            'execution_type': 'cloud_function',
            'execution_name': os.environ.get('FUNCTION_NAME', ''),
            'execution_trigger_type': os.environ.get('FUNCTION_TRIGGER_TYPE',
                                                     ''),
            'timestamp': datetime.datetime.utcnow().strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ")
        }

        message_data = {
            'message_id': message.id,
            'sender': message.sender.email_address,
            'receiver': message.received_by.email_address,
            'subject': message.subject,
            'datetime_sent': message.datetime_sent.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"),
            'datetime_received': message.datetime_received.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"),
            'original_email': message.unique_body,
            'attachments': attachments
        }
        meta = {'gobits': [message_meta], 'mail': message_data}

        # Save meta file to bucket
        blob = bucket.blob('{}/metadata.json'.format(path))
        blob.upload_from_string(json.dumps(meta),
                                content_type='application/json')

        # Publish message to topic
        publisher.publish(topic_name,
                          bytes(json.dumps(meta).encode('utf-8')))
    finally:
        logging.info('Finished posting of e-mail meta to Pub/Sub')


# Setup Exchange account and add sub-folder if not existing
def initialize_exchange_account():
    # Decode KMS encrypted password
    exchange_password_encrypted = base64.b64decode(
        os.environ['EXCHANGE_PASSWORD_ENCRYPTED'])
    kms_client = kms_v1.KeyManagementServiceClient()
    crypto_key_name = kms_client.crypto_key_path_path(
        os.environ['PROJECT_ID'], 'europe',
        'ews-api', 'ews-api-credentials')
    decrypt_response = kms_client.decrypt(
        crypto_key_name, exchange_password_encrypted)
    exchange_password = decrypt_response.plaintext \
        .decode("utf-8").replace('\n', '')

    # Initialize connection to Exchange Web Services
    acc_credentials = Credentials(username=config.EXCHANGE_USERNAME,
                                  password=exchange_password)
    acc_config = Configuration(
        service_endpoint=config.EXCHANGE_URL, credentials=acc_credentials,
        auth_type='basic')
    account = Account(primary_smtp_address=config.EXCHANGE_USERNAME,
                      config=acc_config, autodiscover=False,
                      access_type='delegate')

    # Create sub folder for processed e-mails
    try:
        processed_folder = Folder(parent=account.inbox,
                                  name=config.EXCHANGE_FOLDER_NAME)
        processed_folder.save()
    except errors.ErrorFolderExists:
        pass

    return account


# Set message path for GCP bucket
def set_message_path(client, bucket, message):
    now = message.datetime_sent
    message_id = '%04d%02d%02dT%02d%02d%02dZ' % (now.year, now.month, now.day,
                                                 now.hour, now.minute,
                                                 now.second)
    path = '%s/%04d/%02d/%02d/%s' % (config.EXCHANGE_USERNAME, now.year,
                                     now.month, now.day, message_id)

    if check_gcs_blob_exists(f"{path}/original_email.html", client, bucket):
        path = '{}_{}'.format(path, secrets.randbits(64))

    return path


# Check if blob already exists
def check_gcs_blob_exists(filename, client, bucket):
    return storage.Blob(bucket=bucket, name=filename).exists(client)


def ews_to_bucket(request):
    if request.method == 'POST':
        # Initialize Exchange account
        account = initialize_exchange_account()

        if account.inbox.unread_count > 0:
            # Initialise GCP bucket
            client = storage.Client()
            bucket = client.get_bucket(config.GCP_BUCKET_NAME)

            # Initialise Pub/Sub topic
            publisher = pubsub_v1.PublisherClient()
            topic_name = 'projects/{project_id}/topics/{topic}'.format(
                project_id=config.TOPIC_PROJECT_ID, topic=config.TOPIC_NAME)

            inbox_query = account.inbox.filter(
                    is_read=False).order_by('-datetime_received')
            inbox_query.page_size = 2

            for message in inbox_query.iterator():
                logging.info('Started processing of e-mail')

                # Set message path
                path = set_message_path(client=client, bucket=bucket,
                                        message=message)

                # Save original message to bucket
                process_message_original(bucket=bucket, message=message,
                                         path=path)

                # Save message attachments to bucket
                message_attachments = \
                    process_message_attachments(bucket=bucket,
                                                message=message, path=path)

                # Mark message as 'read' and move to folder
                process_message_status(account=account, message=message)

                # Post message meta info to Pub/Sub Topic
                process_message_meta(message=message,
                                     attachments=message_attachments,
                                     path=path, bucket=bucket,
                                     publisher=publisher,
                                     topic_name=topic_name, request=request)

                logging.info('Finished processing of e-mail')
