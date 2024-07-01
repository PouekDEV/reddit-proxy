from dotenv import load_dotenv
from reddit_proxy import app
from waitress import serve
import os

load_dotenv()

serve(app, host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443, ssl_context=('cert.pem', 'privkey.pem'))