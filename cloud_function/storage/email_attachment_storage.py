import logging
import mimetypes

from config import ATTACHMENTS_TO_STORE
from mail import Email, Attachment
from storage.base import StorageService


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
                    logging.info('Converted attachment {} for email {}. Original content-type {} to {}'.format(
                        attachment.name, email.uuid, attachment.content_type, mimetypes.guess_type(attachment.name)[0])
                    )
                    attachment.content_type = mimetypes.guess_type(attachment.name)[0]

                else:
                    # If the content-type and guessed mimetype are not allowed, we skip downloading this attachment.
                    logging.info('Skipped attachment {} for email {}. content-type {} unknown'.format(
                        attachment.name, email.uuid, attachment.content_type
                    ))
                    continue
            logging.info('Storing file {} for email {}'.format(attachment.name, email.uuid))

            self._store_file(file=attachment.file,
                             filename=self.get_file_name(email, attachment, identifier),
                             content_type=attachment.content_type)
            attachment.storage_bucket = self.bucket
            attachment.storage_filename = self.get_file_name(email, attachment, identifier)
            number_of_attachments = number_of_attachments + 1
        logging.info('Stored {} attachments for email {}'.format(number_of_attachments, email.uuid))

        return number_of_attachments
