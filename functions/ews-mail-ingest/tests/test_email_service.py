import unittest
from datetime import datetime

from mail import Email, ExchangeEmail, Attachment


class TestMailModule(unittest.TestCase):
    def test_email_creation(self):
        email = Email('uuid', 'subject', 'sender', 'receiver',
                      datetime.now(), datetime.now(), 'body', [])

        self.assertEqual(hasattr(email, 'forward'), True)
        self.assertEqual(hasattr(email, 'mark_as_read'), True)

    def test_exchange_mail_creation(self):
        """
        Assert that the ExchangeMail is created as expected.
        """

        email = ExchangeEmail('uuid', 'subject', 'sender', 'receiver',
                              datetime.now(), datetime.now(), 'body', [], None)

        self.assertEqual(isinstance(email, Email), True)

    def test_attachment_creation(self):
        """
        Assert that the Attachment class is created as expected.
        """
        attachment = Attachment(None, 'name', 'content_type', 'content_id', 'storage_bucket', 'storage_filename')

        self.assertEqual(attachment.name, 'name')
