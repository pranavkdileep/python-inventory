from python:3.9

workdir /app

copy . /app

run pip install -r requirements.txt

EXPOSE 5000

cmd ["python3", "app.py"]