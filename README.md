# EWS mail ingest
This function retrieves all un-read e-mails from an [Exchange Web Service (EWS)](https://docs.microsoft.com/en-us/exchange/client-developer/web-service-reference/ews-reference-for-exchange), stores these in a Google Cloud Storage bucket and then posts a message to a Pub/Sub topic. The Google Cloud Storage location for each e-mail will be defined by the e-mail's received timestamp, e.g. ```base/path/2019/11/01/20191101120000Z```

The ```config.py``` file (see [config.example.py](config/config.example.py) for an example) defines which configuration will be used and an ```exchange_password.enc``` file contains the password for the Exchange account.


## Setup
1. Make sure a ```config.py``` file exists within the ```/config``` directory, based on the [config.example.py](config/config.example.py), with the correct configuration:
    ~~~
    GCP_BUCKET_NAME = The bucket name where the e-mails will be uploaded to
    EXCHANGE_URL = The Exchange service endpoint for the mailbox
    EXCHANGE_USERNAME = Username used to login
    EXCHANGE_FOLDER_NAME = The mailbox folder where all processed e-mails will be moved to
    TOPIC_PROJECT_ID = The GCP project which houses the Pub/Sub topic defined next
    TOPIC_NAME = The GCP Pub/Sub topic all processed e-mail meta-info will be posted to
    ~~~
2. Provision an KMS-encrypted ```exchange_password.enc``` file in the ```/config``` directory that will be used to decrypt (see [Google Cloud KMS](https://cloud.google.com/kms/docs/encrypt-decrypt))
3. Make sure the GCP-project and Cloud Builder accounts have access to write to the specific GCS Bucket and GCP Pub/Sub topic
4. Deploy the function to GCP as a HTTP triggered function as shown in the [cloudbuild.example.yaml](cloudbuild.example.yaml)
5. Deploy a GCP Cloud Scheduler to call the function as shown in the [cloudbuild.example.yaml](cloudbuild.example.yaml)

## Function
The ews-mail-ingest works as follows:
1. [Google Cloud KMS](https://cloud.google.com/kms/docs/encrypt-decrypt) will decrypt an encrypted file that contains the Exchange account password
2. A connection will be made to a specific EWS endpoint url with the user credentials from the config file and the decrypted password
3. All un-read e-mails will be listed and looped over
4. Each original e-mail message will be uploaded as an HTML file to the specified GCS Bucket
5. Each e-mail attachment will be uploaded as an blob to the specified GCS Bucket
6. The [meta-info](#meta-info) of each e-mail will be posted to a specified Pub/Sub topic
7. The e-mail will be marked as ```read``` and moved to the specified mailbox folder

#### Meta-info
The meta-info object posted to a GCP Pub/Sub topic is defined as described below.
~~~json
{
    "meta": {
        "gcp_project": "",
        "function_name": "",
        "function_trigger_type": "",
        "timestamp": ""
    },
    "data": {
        "message_id": "",
        "sender": "",
        "receiver": "",
        "subject": "",
        "datetime_sent": "",
        "datetime_received": "",
        "attachments": [],
        "mail": ""
    }
}
~~~

## License
This function is licensed under the [GPL-3](https://www.gnu.org/licenses/gpl-3.0.en.html) License

