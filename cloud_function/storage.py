from google.cloud import storage
from mail import Email, Attachment


class StorageService:
    bucket: str
    credentials = None

    def __init(self, bucket: str, credentials=None):
        self.bucket = bucket
        self.credentials = credentials

    def _store_file(self, file, filename: str):
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(self.bucket)
        blob = bucket.blob(filename)
        blob.upload_from_file(file)

        print(
            "File uploaded to bucket {} with filename {}.".format(
                bucket,
                filename
            )
        )


class EmailAttachmentStorageService(StorageService):
    def get_file_name(self, email: Email, attachment: Attachment):
        return '{receiver}/{year}/{month}/{day}/{uuid}/{file_name}'.format(receiver=email.receiver,
                                                                           year=email.time_received.year,
                                                                           month=email.time_received.month,
                                                                           day=email.time_received.day,
                                                                           uuid=email.uuid,
                                                                           file_name=attachment.file_name)

    def store_attachments(self, email: Email):
        for attachment in email.attachments:
            self._store_file(file=attachment.file,
                             filename=self.get_file_name(email, attachment))
