import logging

from dataclasses import dataclass
from datetime import datetime
from typing import List, Any
from uuid import uuid4

from exchangelib import Credentials, Version, Configuration, Build, Account, FaultTolerance

from config import EXCHANGE_VERSION, EXCHANGE_URL

# Suppress warnings from exchangelib
logging.getLogger("exchangelib").setLevel(logging.ERROR)


@dataclass
class Attachment:
    file: Any
    name: str
    content_type: str
    content_id: str


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


@dataclass
class ExchangeEmail(Email):
    original_message: Any

    def mark_as_read(self):
        self.original_message.is_read = True
        self.original_message.save(update_fields=['is_read'])


class EmailService:
    def __init__(self, email_address, *args, **kwargs):
        pass

    def retrieve_unread_emails(self) -> List[Email]:
        pass


class EWSEmailService:
    exchange_client: Account

    def __init__(self, email_address, secret_id=None, password=None, *args, **kwargs):
        # TODO check if secret is supplied through password or secret id.

        acc_credentials = Credentials(username=email_address, password=password)
        version = Version(build=Build(EXCHANGE_VERSION['major'], EXCHANGE_VERSION['minor']))
        acc_config = Configuration(service_endpoint=EXCHANGE_URL, credentials=acc_credentials,
                                   auth_type='basic', version=version, retry_policy=FaultTolerance(max_wait=300))
        self.exchange_client = Account(primary_smtp_address=email_address, config=acc_config,
                                       autodiscover=False, access_type='delegate')

    def retrieve_unread_emails(self) -> List[Email]:
        if self.exchange_client.inbox:
            if self.exchange_client.inbox.unread_count > 0:
                logging.info('Found {} unread e-mail(s)'.format(self.exchange_client.inbox.unread_count))

                inbox_query = self.exchange_client.inbox.filter(is_read=False) \
                    .order_by('-datetime_received').only('subject', 'sender', 'received_by', 'datetime_sent',
                                                         'datetime_received', 'unique_body', 'attachments')
                inbox_query.page_size = 2

                unread_mails = []
                for message in inbox_query.iterator():
                    attachments = []
                    email = ExchangeEmail(uuid=uuid4(),
                                          subject=message.subject,
                                          sender=message.sender,
                                          receiver=message.received_by,
                                          time_sent=message.datetime_sent,
                                          time_received=message.datetime_reveived,
                                          body=message.unique_body,
                                          attachments=attachments,
                                          original_message=message)

                    unread_mails.append(email)
                return unread_mails
            else:
                logging.info('No unread e-mails in mailbox')
        else:
            raise Exception("Can't find the inbox")

        return []
