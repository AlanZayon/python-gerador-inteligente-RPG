#!/bin/bash
gunicorn --workers 4 --timeout 600 -b 0.0.0.0:10000 app:app
