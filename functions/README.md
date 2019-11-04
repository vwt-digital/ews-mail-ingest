# EWS to Bucket
This function retrieves all un-read e-mails from an [Exchange Web Service (EWS)](https://docs.microsoft.com/en-us/exchange/client-developer/web-service-reference/ews-reference-for-exchange) and stores these in a Google Cloud Storage bucket. The storage location for each e-mail will be defined by the e-mail's received timestamp followed by the e-mail's ID, e.g. ```2019/04/08/ebefa6f80c97833ba96c```

The ```config.py``` file (see [config.example.py](config.example.py) for an example) defines which configuration will be used.

## Function
The 'EWS to Bucket' function works as follows:
1. Google Cloud KMS will decrypt an encrypted file with the Exchange account password 
2. A connection will be made to a specific EWS endpoint url with the user credentials from the config file and the decrypted password
3. All un-read e-mails will be listed and looped over
4. Each original e-mail message will be uploaded as an HTML file
5. Each e-mail attachment will be uploaded as an blob
6. The e-mail will be marked as ```read``` and moved to a specific inbox folder

## License
This function is licensed under the [GPL-3](https://www.gnu.org/licenses/gpl-3.0.en.html) License

