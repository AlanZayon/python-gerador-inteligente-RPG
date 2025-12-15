web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
worker: rq worker campaign_generation --url $REDIS_URL