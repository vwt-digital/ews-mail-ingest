from mail import Email


class PublishService:
    def _publish_message(self, message):
        pass


class MailPublishService(PublishService):
    def _convert_email_to_message(self, email):
        return {}

    def publish_email(self, email: Email):
        message = self._convert_email_to_message(email)

        self._publish_message(message)
