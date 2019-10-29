import config

from exchangelib import Credentials, Account, Configuration, FileAttachment


# Process individual message
def process_message(account, message):
    for attachment in message.attachments:
        if isinstance(attachment, FileAttachment):
            print('Found attachment with name {}'.format(attachment.name))


# Initialize exchangelib account
def main():
    acc_credentials = Credentials(username=config.EXCHANGE_USERNAME,
                                  password=config.EXCHANGE_PASSWORD)
    acc_config = Configuration(
        service_endpoint=config.EXCHANGE_URL, credentials=acc_credentials,
        auth_type='basic')
    account = Account(primary_smtp_address=config.EXCHANGE_USERNAME,
                      config=acc_config, autodiscover=False,
                      access_type='delegate')

    if account.inbox.unread_count > 0:
        for message in account.inbox.filter(is_read=False).order_by(
                '-datetime_received')[:100]:
            process_message(account=account, message=message)


if __name__ == '__main__':
    main()
