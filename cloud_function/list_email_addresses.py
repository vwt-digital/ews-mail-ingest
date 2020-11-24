from config import EMAIL_ADDRESSES


def print_email_identifiers():
    email_identifiers = [key for key, value in EMAIL_ADDRESSES.items()]
    print(' '.join(email_identifiers))


if __name__ == '__main__':
    print_email_identifiers()
