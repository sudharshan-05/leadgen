bot: python main.py --service bot
worker: celery -A workers.celery_app worker --loglevel=info --concurrency=1
scheduler: python main.py --service scheduler
watchdog: python main.py --service agent
api: python main.py --service api
