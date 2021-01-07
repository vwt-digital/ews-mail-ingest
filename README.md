[![CodeFactor](https://www.codefactor.io/repository/github/vwt-digital/ews-mail-ingest/badge)](https://www.codefactor.io/repository/github/vwt-digital/ews-mail-ingest)

# EWS mail ingest
This function retrieves all un-read e-mails from an [Exchange Web Service (EWS)](https://docs.microsoft.com/en-us/exchange/client-developer/web-service-reference/ews-reference-for-exchange), stores these in a Google Cloud Storage bucket and then posts a message to a Pub/Sub topic. The Google Cloud Storage location for each e-mail will be defined by the e-mail's received timestamp, e.g. ```base/path/2019/11/01/20191101120000Z```

The ```config.py``` file (see [config.example.py](config/config.example.py) for an example) defines which configuration will be used.


## Setup
1. Make sure a ```config.py``` file exists within the function directory, based on the [config.example.py](config/config.example.py), with the correct configuration:
    ~~~
    EXCHANGE_URL = The Exchange service endpoint for the mailbox
    EXCHANGE_USERNAME = Username used to login
    EXCHANGE_VERSION = An object containing the 'major' and 'minor' Exchange server versions
    TOPIC_PROJECT_ID = The GCP project which houses the Pub/Sub topic defined next
    TOPIC_NAME = The GCP Pub/Sub topic all processed e-mail meta-info will be posted to
    GCP_BUCKET_NAME = The bucket name where the e-mail attachments (if there are any) will be uploaded to
    ATTACHMENTS_TO_STORE = List of possible mime-types for e-mail attachments. These mimetypes determine which type of files will be stored in the associated bucket. Unknown mime-types will be ignored.
    ERROR_EMAIL_ADDRESS = E-mail address where an error message will be send to if an e-mail cannot be send
    ERROR_EMAIL_MESSAGE = Message that will be send to the aforementioned e-mail address
    EMAIL_ADDRESSES = A dictionary containing mailboxes to be read by the mailingest function. Each mailbox should contain a secret_id of the secret contained in the secret manager, and the email. Optionally an alias field can be added (ews-mail-ingest will publish emails as if they were received by the alias.), as well as a folder field, which will instruct ews-mail-ingest to read a different folder than the default inbox. (Subfolders can be defined with backslashes. 'inbox/today' is a valid folder.)
    ~~~

    If no attachments are ever send along with the email, ```GCP_BUCKET_NAME``` should be an empty string and ```ATTACHMENTS_TO_STORE```
    should be an empty list.

    If no error message should be send to an e-mail address if an e-mail cannot be send, ```ERROR_EMAIL_ADDRESS``` and
    ```ERROR_EMAIL_MESSAGE``` can be empty strings.
2. Provision a secret in the project's secret manager containing the password for each defined mailbox. This secret should be a json with a password field:
    ~~~
    {
        "password": "<PASSWORD_HERE>"
    }
3. Make sure the GCP-project and Cloud Builder accounts have access to write to the specific GCS Bucket and GCP Pub/Sub topic
4. Deploy the function to GCP as a HTTP triggered function as shown in the [cloudbuild.example.yaml](config/cloudbuild.example.yaml)
5. Deploy a GCP Cloud Scheduler to call the function as shown in the [cloudbuild.example.yaml](config/cloudbuild.example.yaml). For each email in EMAIL_ADDRESSES, you should schedule a function, passing the key in the dictionary as a GET argument. You can also use [schedule_email_address_functions.sh](config/schedule_email_address_functions.sh) to do this for you. [cloudbuild.example.yaml](config/cloudbuild.example.yaml) for an example usage of this script.

## Function
The ews-mail-ingest works as follows:
1. [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs/reference/libraries) will retrieve a secret that contains the Exchange account password
2. A connection will be made to a specific EWS endpoint url with the user credentials from the config file and the decrypted password
3. All un-read e-mails will be listed and looped over
5. If e-mail attachments are configured, each e-mail attachment will be uploaded as an blob to the specified GCS Bucket
6. The actual body and [meta-info](#meta-info) of each e-mail will be posted to a specified Pub/Sub topic
7. The e-mail will be marked as ```read```.

#### Meta-info
The meta-info object posted to a GCP Pub/Sub topic is defined as described below. For the gobits field, refer to [this](https://github.com/vwt-digital/gobits) repository.
~~~json
{
  "gobits": [gobits],
  "mail": {
    "sent_on": "",
    "recipient": "",
    "subject": "",
    "body"
    "sent_on": "",
    "received_on": "",
    "attachments": []
  }
}
~~~

## License
This function is licensed under the [GPL-3](https://www.gnu.org/licenses/gpl-3.0.en.html) License
