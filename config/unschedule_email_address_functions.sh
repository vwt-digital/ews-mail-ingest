for JOB in $(gcloud scheduler jobs list --uri | grep mail-ingest-job-)
do
	echo "Deleting job ${JOB}"
	gcloud scheduler jobs delete --quiet "${JOB}" || exit 0
done