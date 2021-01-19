for EMAIL in $(python3 -c 'import config
print(" ".join([key for key,value in config.EMAIL_ADDRESSES.items()]))');
do
  echo "Scheduling job ${PROJECT_ID}-mail-ingest-job-$EMAIL"
  gcloud scheduler jobs create http "${PROJECT_ID}-mail-ingest-job-$EMAIL" \
    --schedule="*/10 * * * *" \
    --uri="https://europe-west1-${PROJECT_ID}.cloudfunctions.net/${PROJECT_ID}-mail-ingest-func?identifier=$EMAIL" \
    --project="${PROJECT_ID}" \
    --oidc-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" \
    --oidc-token-audience="https://europe-west1-${PROJECT_ID}.cloudfunctions.net/${PROJECT_ID}-mail-ingest-func" \
    --max-retry-attempts=3
done