from flask import Flask, send_file, request
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import json
import os

load_dotenv()

app = Flask("reddit-proxy")
# We need these just in case reddit blocked our IP
cookies = {
    "__stripe_mid": os.getenv("STRIPE_MID"),
    "csv": os.getenv("CSV"),
    "edgebucket": os.getenv("EDGEBUCKET"),
    "loid": os.getenv("LOID"),
    "pc": os.getenv("PC"),
    "rdt": os.getenv("RDT"),
    "reddit_session": os.getenv("REDDIT_SESSION"),
    "session": os.getenv("SESSION"),
    "token_v2": os.getenv("TOKEN_V2"),
    "USER": os.getenv("USER")
}
headers = {
    'User-Agent': 'linux:https://github.com/PouekDEV/reddit-proxy:v1.0.0 (by /u/Pouek_)',
    'From': 'stuff@pouekdev.one'
}

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nDisallow: /"

@app.route('/favicon.ico')
def favicon():
    return "404"

@app.route('/video/', defaults={'path': ''})
@app.route('/video/<path:path>')
def video(path):
    if path == "" or path == None:
        return '<head><meta http-equiv="refresh" content="0; url=https://github.com/PouekDEV/reddit-proxy"></head>'
    try:
        path.index("https://")
    except ValueError:
        path = path.replace("https:/","https://")
    r = requests.get(url=path,cookies=cookies,headers=headers)
    soup = BeautifulSoup(r.text, features="html.parser")
    info = json.loads(soup.find("shreddit-player")["packaged-media-json"])["playbackMp4s"]["permutations"]
    url = info[len(info)-1]["source"]["url"]
    return send_file(path_or_file=requests.get(url, stream=True).raw,download_name="reddit_video.mp4")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def embed(path):
    if path == "" or path == None:
        return '<head><meta http-equiv="refresh" content="0; url=https://github.com/PouekDEV/reddit-proxy"></head>'
    try:
        path.index("https://")
    except ValueError:
        path = path.replace("https:/","https://")
    r = requests.get(url=path,cookies=cookies,headers=headers)
    soup = BeautifulSoup(r.text, features="html.parser")
    info = json.loads(soup.find("shreddit-player")["packaged-media-json"])["playbackMp4s"]["permutations"]
    width = info[len(info)-1]["source"]["dimensions"]["width"]
    height = info[len(info)-1]["source"]["dimensions"]["height"]
    r = requests.get(url=path+".json",cookies=cookies)
    info = json.loads(r.text)[0]["data"]["children"][0]["data"]
    name = info["subreddit_name_prefixed"]
    title = info["title"]
    return '<head><meta http-equiv="refresh" content="0; url='+path+'"><meta property="og:title" content="'+name+' - '+title+'"><meta property="og:url" content="'+path+'"><meta property="og:video" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:image" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:type" content="video"><meta property="og:video:type" content="video/mp4"><meta property="og:video:width" content="'+str(width)+'"><meta property="og:video:height" content="'+str(height)+'"></head>'

if __name__ == "__main__":
    app.run(host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443)