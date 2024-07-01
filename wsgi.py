from dotenv import load_dotenv
from reddit_proxy import app
from gevent import pywsgi
import os

load_dotenv()

http_server = pywsgi.WSGIServer((os.getenv("HOST") or '0.0.0.0', int(os.getenv("PORT")) or 4443), app, keyfile='privkey.pem', certfile='cert.pem')
http_server.serve_forever()