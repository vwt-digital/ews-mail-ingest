import logging

from dataclasses import dataclass
from datetime import datetime
from typing import List, Any
from uuid import uuid4

from exchangelib import Credentials, Account
from exchangelib.folders import Messages

# Suppress warnings from exchangelib
logging.getLogger("exchangelib").setLevel(logging.ERROR)


@dataclass
class Attachment:
    file: Any
    name: str
    content_type: str
    content_id: str

    # TODO: It's cleaner to move this to a separate subclass.
    storage_bucket: str
    storage_filename: str


@dataclass
class Email:
    uuid: str
    subject: str
    sender: str
    receiver: str
    time_sent: datetime
    time_received: datetime
    body: str
    attachments: List[Attachment]

    def mark_as_read(self):
        pass


class EmailService:
    def __init__(self, email_address, *args, **kwargs):
        pass

    def retrieve_unread_emails(self) -> List[Email]:
        pass


@dataclass
class ExchangeEmail(Email):
    original_message: Any

    def mark_as_read(self):
        self.original_message.is_read = True
        self.original_message.save(update_fields=['is_read'])


class EWSEmailService:
    email_address: str
    alias: str
    exchange_client: Account
    folder: Messages

    def __init__(self, email_address, password=None, folder=None, alias=None, *args, **kwargs):
        self.email_address = email_address
        self.alias = alias
        credentials = Credentials(username=email_address, password=password)
        self.exchange_client = Account(email_address, credentials=credentials, autodiscover=True)

        if folder is None:
            self.folder = self.exchange_client.inbox
        else:
            self.folder = self.exchange_client.inbox / folder

    def retrieve_unread_emails(self) -> List[Email]:
        if self.folder:
            if self.folder.unread_count > 0:
                logging.info('Found {} unread e-mail(s)'.format(self.folder.unread_count))

                inbox_query = self.folder.filter(is_read=False) \
                    .order_by('-datetime_received').only('subject', 'sender', 'received_by', 'datetime_sent',
                                                         'datetime_received', 'unique_body', 'attachments')
                inbox_query.page_size = 2

                unread_mails = []
                for message in inbox_query.iterator():
                    try:
                        if self.alias is None:
                            received_by = self.email_address
                        else:
                            received_by = self.alias

                        attachments = [Attachment(attachment.fp,
                                                  attachment.name,
                                                  attachment.content_type,
                                                  attachment.content_id,
                                                  storage_bucket=None,
                                                  storage_filename=None)
                                       for attachment in message.attachments
                                       if not attachment.is_inline]

                        email = ExchangeEmail(uuid=uuid4(),
                                              subject=message.subject,
                                              sender=str(message.sender.email_address),
                                              receiver=received_by,
                                              time_sent=message.datetime_sent,
                                              time_received=message.datetime_received,
                                              body=message.unique_body,
                                              attachments=attachments,
                                              original_message=message)
                        unread_mails.append(email)
                    except Exception:
                        logging.info("Error retrieving email", exc_info=True)
                return unread_mails
            else:
                logging.info('No unread e-mails in mailbox')
        else:
            raise Exception('Can\'t find the inbox')

        return []
