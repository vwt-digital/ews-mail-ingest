import logging
import mimetypes

from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage
from google.resumable_media import requests, common

from config import ATTACHMENTS_TO_STORE
from mail import Email, Attachment


class GCSObjectStreamUpload(object):
    def __init__(
            self,
            client: storage.Client,
            bucket_name: str,
            blob_name: str,
            content_type: str,
            chunk_size: int = 256 * 1024
    ):
        self._client = client
        self._bucket = self._client.bucket(bucket_name)
        self._blob = self._bucket.blob(blob_name)
        self._content_type = content_type

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
            content_type=self._content_type,
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
        to_read = min(chunk_size, self._buffer_size)
        memview = memoryview(self._buffer)
        self._buffer = memview[to_read:].tobytes()
        self._read += to_read
        self._buffer_size -= to_read
        return memview[:to_read].tobytes()

    def tell(self) -> int:
        return self._read


class StorageService:
    bucket: str
    credentials = None

    def __init__(self, bucket: str):
        self.bucket = bucket
        self.storage_client = storage.Client()

    def _store_file(self, file, filename: str, content_type: str = None):

        # bucket = storage_client.get_bucket(self.bucket)
        # blob = bucket.blob(filename)
        # blob.content_type = content_type
        with GCSObjectStreamUpload(client=self.storage_client,
                                   bucket_name=self.bucket,
                                   blob_name=filename,
                                   content_type=content_type) as f,\
                file as fp:
            buffer = fp.read(1024)
            while buffer:
                f.write(buffer)
                buffer = fp.read(1024)

        print(
            "File uploaded to bucket {} with filename {}.".format(
                self.bucket,
                filename
            )
        )

        return


class EmailAttachmentStorageService(StorageService):
    def get_file_name(self, email: Email, attachment: Attachment, identifier: str):
        return '{identifier}/{year}/{month}/{day}/{uuid}/{file_name}'.format(identifier=identifier,
                                                                             year=email.time_received.year,
                                                                             month=email.time_received.month,
                                                                             day=email.time_received.day,
                                                                             uuid=email.uuid,
                                                                             file_name=attachment.name)

    def store_attachments(self, email: Email, identifier: str):
        """
        :param email:
        :param identifier:
        :return: the number of actual attachments stored.
        """
        number_of_attachments = 0
        for attachment in email.attachments:
            if attachment.content_type not in ATTACHMENTS_TO_STORE:
                # Sometimes the mimetype of a file is application/octet-stream,
                # while the file itself is actually a different type.
                if attachment.content_type == 'application/octet-stream' \
                        and mimetypes.guess_type(attachment.name)[0] in ATTACHMENTS_TO_STORE:
                    attachment.content_type = mimetypes.guess_type(attachment.name)[0]
                else:
                    # If the content-type and guessed mimetype are not allowed, we skip downloading this attachment.
                    logging.info('Skipped attachment {} for email {}. content-type {} unknown'.format(
                        attachment.name, email.uuid, attachment.content_type
                    ))
                    continue

            self._store_file(file=attachment.file,
                             filename=self.get_file_name(email, attachment, identifier),
                             content_type=attachment.content_type)
            attachment.storage_bucket = self.bucket
            attachment.storage_filename = self.get_file_name(email, attachment, identifier)
            number_of_attachments = number_of_attachments + 1

        return number_of_attachments
