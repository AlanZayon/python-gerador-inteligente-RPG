"""
Worker RQ para processamento assíncrono de campanhas de RPG
Execute com: python worker.py
"""

import os
import redis
from rq import Worker, Queue
from dotenv import load_dotenv

load_dotenv()

# Configurar Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

listen = ['campaign_generation']

if __name__ == '__main__':
    redis_conn = redis.from_url(REDIS_URL)

    queues = [Queue(name, connection=redis_conn) for name in listen]

    worker = Worker(queues, connection=redis_conn)
    worker.work()
