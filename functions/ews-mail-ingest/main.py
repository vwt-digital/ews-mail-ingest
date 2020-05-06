import config
import os
import logging
import json
import base64
import secrets
import datetime
import requests as py_requests
import tempfile
import defusedxml
from translate_error import TranslateError

from urllib3 import exceptions as lib_exceptions
from exchangelib import Credentials, Account, Configuration, Folder, \
    FileAttachment, errors, Version, Build, FaultTolerance
from google.auth.transport.requests import AuthorizedSession
from google.resumable_media import requests, common
from google.cloud import kms_v1, storage, pubsub_v1
from PyPDF2 import PdfFileReader, PdfFileWriter
from defusedxml import ElementTree as defusedxml_ET
from lxml import etree as ET
from lxml.html.clean import Cleaner

# Suppress warnings from exchangelib
logging.getLogger("exchangelib").setLevel(logging.ERROR)

defusedxml.defuse_stdlib()  # Force defusing vulnerable


class EWSMailMessage:
    def __init__(self, exchange_client, storage_client, bucket, bucket_name, publisher, topic_name, message, request):
        self.exchange_client = exchange_client
        self.storage_client = storage_client
        self.bucket = bucket
        self.bucket_name = bucket_name
        self.publisher = publisher
        self.topic_name = topic_name
        self.message = message
        self.request = request
        self.path, self.message_id = self.set_message_path()
        self.folder_processed = 'processed'
        self.folder_processed_failed = 'processed_failed'

        self.logger = custom_logger(self.message_id)

    def process(self):
        try:
            self.logger.info('Started processing of e-mail')

            self.process_original_message()  # Save original message to bucket
            message_attachments, complete = self.process_message_attachments()  # Save attachments
            meta = self.process_message_meta(attachments=message_attachments)  # Post meta to bucket and Pub/Sub

            if complete:
                self.publisher.publish(
                    self.topic_name, bytes(json.dumps(meta).encode('utf-8')))  # Publish message to topic
                self.move_message(True)  # Move message to other inbox

                self.logger.info('Finished processing of e-mail')
            else:
                raise TranslateError(
                            4030,
                            description="Could not successfully process mail",
                            function_name="process")
                self.move_message(False)  # Move and flag message
                self.logger.info('Finished processing of incorrect e-mail')

        except TranslateError as e:
            logging.error(json.dumps(e.properties))
        except Exception as e:
            logging.exception(e)

    def process_message_attachments(self):
        message_attachments = []
        total_count = len(self.message.attachments)
        uploaded_count = 0
        xml_count = 0
        pdf_count = 0

        self.logger.info("Started uploading attachments...")
        for attachment in self.message.attachments:
            if isinstance(attachment, FileAttachment) and attachment.content_type in ['text/xml', 'application/pdf']:
                if attachment.size > 5242880:  # 5MB limit
                    self.logger.info(
                        "Skipped file '{}' because maximum size of 5MB is exceeded".format(attachment.name))
                    continue
                elif attachment.content_type == 'text/xml' and xml_count >= 1:
                    self.logger.info(
                        "Skipped XML file '{}' because maximum file of 1 is exceeded".format(attachment.name))
                    continue
                elif attachment.content_type == 'application/pdf' and pdf_count >= 5:
                    self.logger.info(
                        "Skipped PDF file '{}' because maximum files of 5 is exceeded".format(attachment.name))
                    continue

                clean_attachment_name = attachment.name.replace(' ', '_'). \
                    replace('.', '_', attachment.name.count('.') - 1).replace('-', '_')

                try:
                    file_path = '%s/%s' % (self.path, clean_attachment_name)

                    if attachment.content_type == 'application/pdf':
                        writer = PdfFileWriter()
                        with tempfile.TemporaryFile(mode='w+b') as temp_file, attachment.fp as fp:
                            buffer = fp.read(1024)
                            while buffer:
                                temp_file.write(buffer)
                                buffer = fp.read(1024)
                            reader = PdfFileReader(temp_file)
                            [writer.addPage(reader.getPage(i)) for i in range(0, reader.getNumPages())]
                            writer.removeLinks()
                            with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_flat_file:
                                writer.write(temp_flat_file)
                                temp_flat_file.close()
                                self.write_stream_to_blob(self.bucket_name, file_path, open(temp_flat_file.name, 'rb'))
                            temp_file.close()
                        pdf_count += 1
                    else:
                        try:
                            xml_tree = self.secure_xml(attachment.content)
                        except Exception as e:
                            logging.info(
                                "Skipped XML '{}' because parsing failed: {}".format(attachment.name, str(e)))
                            continue

                        xml_temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False)  # Open
                        xml_tree.write(xml_temp_file, encoding="utf-8", method="xml", xml_declaration=True)  # Write
                        xml_temp_file.close()  # Close
                        self.write_stream_to_blob(self.bucket_name, file_path, open(xml_temp_file.name, 'rb'))  # Save
                        xml_temp_file.close()  # Close
                        os.unlink(xml_temp_file.name)  # Unlink

                        xml_count += 1

                    message_attachments.append({
                        'name': clean_attachment_name,
                        'path': f'gs://{config.GCP_BUCKET_NAME}/{file_path}',
                        'content_type': attachment.content_type,
                    })
                    uploaded_count += 1
                except Exception as exception:
                    self.logger.exception(exception)
                    continue

        if xml_count == 1 and pdf_count > 0:
            self.logger.info("Finished uploading {} of {} attachment(s)".format(uploaded_count, total_count))
            return message_attachments, True

        self.logger.info("Message has not enough correct files, " +
                         "only {} XML file(s) and {} PDF file(s) are present".format(xml_count, pdf_count))
        return message_attachments, False

    def secure_xml(self, xml_string):
        safe_xml_tree = defusedxml_ET.fromstring(xml_string)
        xml_tree = ET.fromstring(defusedxml_ET.tostring(safe_xml_tree))
        for elem in xml_tree.getiterator():
            elem.tag = ET.QName(elem).localname

        return ET.ElementTree(xml_tree)

    def write_stream_to_blob(self, bucket_name, path, content):
        with GCSObjectStreamUpload(client=self.storage_client, bucket_name=bucket_name, blob_name=path) as f,\
                content as fp:
            buffer = fp.read(1024)
            while buffer:
                f.write(buffer)
                buffer = fp.read(1024)

    def process_original_message(self):
        message_text_blob = self.bucket.blob('%s/original_email.html' % self.path)
        message_text_blob.upload_from_string(parse_html_content(self.message.unique_body))

    def move_message(self, success=True):
        self.message.is_read = True
        self.message.save(update_fields=['is_read'])
        self.message.move(self.exchange_client.inbox /
                          (self.folder_processed if success else self.folder_processed_failed))

    def process_message_meta(self, attachments):
        message_meta = {
            'gcp_project': os.environ.get('GCP_PROJECT', ''),
            'execution_id': self.request.headers.get('Function-Execution-Id', ''),
            'execution_type': 'cloud_function',
            'execution_name': os.environ.get('FUNCTION_NAME', ''),
            'execution_trigger_type': os.environ.get('FUNCTION_TRIGGER_TYPE', ''),
            'timestamp': datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }

        message_data = {
            'message_id': self.message.id,
            'sender': self.message.sender.email_address,
            'receiver': self.message.received_by.email_address,
            'subject': self.message.subject,
            'datetime_sent': self.message.datetime_sent.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            'datetime_received': self.message.datetime_received.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            'original_email': parse_html_content(self.message.unique_body),
            'attachments': attachments
        }
        meta = {'gobits': [message_meta], 'mail': message_data}

        # Save meta file to bucket
        blob = self.bucket.blob('{}/metadata.json'.format(self.path))
        blob.upload_from_string(json.dumps(meta), content_type='application/json')

        return meta

    def set_message_path(self):
        now = self.message.datetime_sent
        message_id = '%04d%02d%02dT%02d%02d%02dZ' % (now.year, now.month, now.day, now.hour, now.minute, now.second)
        path = '%s/%04d/%02d/%02d/%s' % (config.EXCHANGE_USERNAME, now.year, now.month, now.day, message_id)

        if self.check_gcs_blob_exists(f"{path}/original_email.html"):
            path = '{}_{}'.format(path, secrets.randbits(64))

        return path, path.split('/').pop()

    # Check if blob already exists
    def check_gcs_blob_exists(self, name):
        return storage.Blob(bucket=self.bucket, name=name).exists(self.storage_client)


class EWSMailIngest:
    def __init__(self, request):
        # Decode KMS encrypted password
        exchange_password_encrypted = base64.b64decode(os.environ['EXCHANGE_PASSWORD_ENCRYPTED'])
        kms_client = kms_v1.KeyManagementServiceClient()
        crypto_key_name = kms_client.crypto_key_path_path(os.environ['PROJECT_ID'], 'europe', 'ews-api',
                                                          'ews-api-credentials')
        decrypt_response = kms_client.decrypt(crypto_key_name, exchange_password_encrypted)
        exchange_password = decrypt_response.plaintext.decode("utf-8").replace('\n', '')

        # Initialize connection to Exchange Web Services
        acc_credentials = Credentials(username=config.EXCHANGE_USERNAME, password=exchange_password)
        version = Version(build=Build(config.EXCHANGE_VERSION['major'], config.EXCHANGE_VERSION['minor']))
        acc_config = Configuration(service_endpoint=config.EXCHANGE_URL, credentials=acc_credentials,
                                   auth_type='basic', version=version, retry_policy=FaultTolerance(max_wait=300))
        self.exchange_client = Account(primary_smtp_address=config.EXCHANGE_USERNAME, config=acc_config,
                                       autodiscover=False, access_type='delegate')

        self.storage_client = storage.Client()
        self.bucket = self.storage_client.get_bucket(config.GCP_BUCKET_NAME)
        self.bucket_name = config.GCP_BUCKET_NAME
        self.request = request
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_name = 'projects/{project_id}/topics/{topic}'.format(project_id=config.TOPIC_PROJECT_ID,
                                                                        topic=config.TOPIC_NAME)

    def initialize_exchange_account(self):
        # Create 'processed' folder
        try:
            processed_folder = Folder(parent=self.exchange_client.inbox, name="processed")
            processed_folder.save()
        except errors.ErrorFolderExists:
            pass

        # Create 'processed_failed' folder
        try:
            processed_folder = Folder(parent=self.exchange_client.inbox, name="processed_failed")
            processed_folder.save()
        except errors.ErrorFolderExists:
            pass

    def process(self):
        try:
            self.initialize_exchange_account()

            if self.exchange_client and self.exchange_client.inbox:
                if self.exchange_client.inbox.unread_count > 0:
                    logging.info('Found {} unread e-mail(s)'.format(self.exchange_client.inbox.unread_count))

                    inbox_query = self.exchange_client.inbox.filter(is_read=False) \
                        .order_by('-datetime_received').only('subject', 'sender', 'received_by', 'datetime_sent',
                                                             'datetime_received', 'unique_body', 'attachments')
                    inbox_query.page_size = 2

                    for message in inbox_query.iterator():
                        EWSMailMessage(exchange_client=self.exchange_client,
                                       storage_client=self.storage_client,
                                       bucket=self.bucket,
                                       bucket_name=self.bucket_name,
                                       publisher=self.publisher,
                                       topic_name=self.topic_name,
                                       message=message,
                                       request=self.request).process()
                else:
                    logging.info('No unread e-mails in mailbox')
            else:
                logging.error("Can't find the inbox")
        except (KeyError, ConnectionResetError, py_requests.exceptions.ConnectionError,
                lib_exceptions.ProtocolError) as e:
            logging.error(str(e))
        except Exception as e:
            logging.exception(e)


class GCSObjectStreamUpload(object):
    def __init__(
            self,
            client: storage.Client,
            bucket_name: str,
            blob_name: str,
            chunk_size: int = 256 * 1024
    ):
        self._client = client
        self._bucket = self._client.bucket(bucket_name)
        self._blob = self._bucket.blob(blob_name)

        self._buffer = b''
        self._buffer_size = 0
        self._chunk_size = chunk_size
        self._read = 0

        self._transport = AuthorizedSession(
            credentials=self._client._credentials
        )
        self._request = None  # type: requests.ResumableUpload

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.stop()

    def start(self):
        url = (
            f'https://www.googleapis.com/upload/storage/v1/b/'
            f'{self._bucket.name}/o?uploadType=resumable'
        )
        self._request = requests.ResumableUpload(
            upload_url=url, chunk_size=self._chunk_size
        )
        self._request.initiate(
            transport=self._transport,
            content_type='application/octet-stream',
            stream=self,
            stream_final=False,
            metadata={'name': self._blob.name},
        )

    def stop(self):
        self._request.transmit_next_chunk(self._transport)

    def write(self, data: bytes) -> int:
        data_len = len(data)
        self._buffer_size += data_len
        self._buffer += data
        del data
        while self._buffer_size >= self._chunk_size:
            try:
                self._request.transmit_next_chunk(self._transport)
            except common.InvalidResponse:
                self._request.recover(self._transport)
        return data_len

    def read(self, chunk_size: int) -> bytes:
        # I'm not good with efficient no-copy buffering so if this is
        # wrong or there's a better way to do this let me know! :-)
        to_read = min(chunk_size, self._buffer_size)
        memview = memoryview(self._buffer)
        self._buffer = memview[to_read:].tobytes()
        self._read += to_read
        self._buffer_size -= to_read
        return memview[:to_read].tobytes()

    def tell(self) -> int:
        return self._read


def parse_html_content(html):
    cleaner = Cleaner()
    cleaner.javascript = True
    cleaner.style = True

    return cleaner.clean_html(html)


def custom_logger(logger_name):
    """
    Method to return a custom logger with the given name and level
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    return logger


def ews_to_bucket(request):
    if request.method == 'POST':
        EWSMailIngest(request=request).process()


if __name__ == '__main__':
    mock_request = py_requests.session()
    mock_request.method = "POST"
    logging.getLogger().setLevel(logging.INFO)

    ews_to_bucket(mock_request)
