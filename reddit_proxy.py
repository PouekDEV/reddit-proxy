from flask import Flask, send_file, request
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import ffmpeg
import json
import os
import re
import io

load_dotenv()

app = Flask("reddit-proxy")
# We need these just in case reddit blocked our IP
cookies = {
    "csv": os.getenv("CSV"),
    "edgebucket": os.getenv("EDGEBUCKET"),
    "loid": os.getenv("LOID"),
    "rdt": os.getenv("RDT"),
    "reddit_session": os.getenv("REDDIT_SESSION"),
    "token_v2": os.getenv("TOKEN_V2"),
}
headers = {
    'User-Agent': 'linux:https://github.com/PouekDEV/reddit-proxy:v1.1.0 (by /u/Pouek_)',
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
    try:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        info = json.loads(soup.find("shreddit-player")["packaged-media-json"])["playbackMp4s"]["permutations"]
        url = info[len(info)-1]["source"]["url"]
    # Fallback to a video without sound
    except KeyError:
        r = requests.get(url=path+".json",cookies=cookies,headers=headers)
        info = json.loads(r.text)[0]["data"]["children"][0]["data"]
        url = info["media"]["reddit_video"]["fallback_url"]
        # If it's not a gif we can try and combine the audio and video ourselves
        if not info["media"]["reddit_video"]["is_gif"]:
            audio_url = info["url"]
            audio_url = audio_url + "/DASH_AUDIO_"
            r = requests.get(url=info["media"]["reddit_video"]["hls_url"])
            best_hls = ""
            for line in r.text.splitlines():
                if "#EXT-X-MEDIA" in line:
                    hls = re.search('HLS_AUDIO_(.*).m3u8',line)
                    best_hls = hls.group(1)
            audio_url = audio_url + best_hls + ".mp4"
            audio = ffmpeg.input(audio_url)
            video = ffmpeg.input(url)
            process = (
                # We need a better format for this than webm because it's slow to encode
                ffmpeg.output(audio, video, "pipe:", format="webm").run_async(pipe_stdout=True)
            )
            returnable_result = io.BytesIO()
            out = process.communicate()
            returnable_result.write(out[0])
            returnable_result.seek(0)
        else:
            raw_video = requests.get(url, stream=True).raw
            returnable_result = raw_video
    except TypeError:
        return 'This post is not a video'
    else:
        raw_video = requests.get(url, stream=True).raw
        returnable_result = raw_video
    return send_file(path_or_file=returnable_result,download_name="reddit_video.mp4")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def embed(path):
    if path == "" or path == None:
        return '<head><meta http-equiv="refresh" content="0; url=https://github.com/PouekDEV/reddit-proxy"></head>'
    try:
        path.index("https://")
    except ValueError:
        path = path.replace("https:/","https://")
    r = requests.get(url=path+".json",cookies=cookies,headers=headers)
    info = json.loads(r.text)[0]["data"]["children"][0]["data"]
    name = info["subreddit_name_prefixed"]
    title = info["title"]
    try:
        width = info["media"]["reddit_video"]["width"]
        height = info["media"]["reddit_video"]["width"]
    except TypeError:
        return 'This post is not a video'
    return '<head><meta http-equiv="refresh" content="0; url='+path+'"><meta property="og:title" content="'+name+' - '+title+'"><meta property="og:url" content="'+path+'"><meta property="og:video" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:image" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:type" content="video"><meta property="og:video:type" content="video/mp4"><meta property="og:video:width" content="'+str(width)+'"><meta property="og:video:height" content="'+str(height)+'"></head>'

if __name__ == "__main__":
    app.run(host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443)