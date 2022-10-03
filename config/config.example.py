EMAIL_ADDRESSES = {
    'inbox1': {
        'email': 'inbox1@vwtelecom.com',
        'secret_id': '<SECRET_ID_HERE>'
    },
    'inbox_with_alias': {
        'email': 'inbox2@vwtelecom.com',
        'alias': 'alias@vwtelecom.com',
        'secret_id': '<SECRET_ID_HERE>'
    },
    'inbox_with_folder': {
        'email': 'inbox2@vwtelecom.com',
        'folder': '<FOLDER_NAME_HERE>',
        'secret_id': '<SECRET_ID_HERE>'
    },
    'inbox_with_oauth': {
        'email': 'inbox2@vwtelecom.com',
        'folder': '<FOLDER_NAME_HERE>',
        'client_id': '<APP_REGISTRATION_CLIENT_ID>',
        'client_secret_id': '<APP_REGISTRATION_SECRET_MANAGER_ID_HERE>',
        'tenant_id': '<APP_REGISTRATION_TENANT_ID>'
    }
}

EXCHANGE_URL = 'https://outlook.office365.com/ews/exchange.asmx'
EXCHANGE_VERSION = {'major': 15, 'minor': 20}

PROJECT_ID = '<PROJECT_ID>'
BUCKET_NAME = '<BUCKET_NAME>'
TOPIC_NAME = '<TOPIC_NAME>'

ATTACHMENTS_TO_STORE = ['application/pdf']

ALLOWED_HTML_BODY_TAGS = ['html-tag1', 'html-tag2']

ERROR_EMAIL_ADDRESS = 'support@vwtelecom.com'
ERROR_EMAIL_MESSAGE = 'This is an error message'
