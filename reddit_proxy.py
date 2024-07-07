from flask import Flask, send_file, request, redirect
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
encoding = os.getenv("ENCODING", 'False').lower() in ('true', '1', 't')

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
        return redirect("https://github.com/PouekDEV/reddit-proxy", code=302)
    if not "reddit" in path:
        return 'Not a reddit link'
    if not "https://" in path:
        path = path.replace("https:/","https://")
    try:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        info = json.loads(soup.find("shreddit-player")["packaged-media-json"])["playbackMp4s"]["permutations"]
        url = info[len(info)-1]["source"]["url"]
    # Fallback to a video without sound
    except (TypeError, KeyError):
        r = requests.get(url=path+".json",cookies=cookies,headers=headers)
        info = json.loads(r.text)[0]["data"]["children"][0]["data"]
        try:
            url = info["media"]["reddit_video"]["fallback_url"]
            # If it's not a gif we can try and combine the audio and video ourselves
            # The encoding still seems to be too slow for discord to display it
            # As an alternative maybe add downloading the video from yt-dlp?
            if not info["media"]["reddit_video"]["is_gif"] and encoding:
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
                ffmpeg.output(audio, video, "temp.mp4", format="mp4", vcodec="libx264", acodec="copy", crf=27, preset="veryfast").run(overwrite_output=True)
                file = open("./temp.mp4", "rb")
                returnable_result = io.BytesIO(file.read())
                file.close()
                return send_file(path_or_file=returnable_result,download_name="reddit_video.mp4")
        except (TypeError, KeyError):
            try:
                url = info["preview"]["reddit_video_preview"]["fallback_url"]
            except (TypeError, KeyError):
                try:
                    url = soup.find("shreddit-player")["src"]
                except (TypeError, KeyError):
                    return 'Video is not hosted on reddit or the post is not a video'
    return redirect(url, code=302)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def embed(path):
    if path == "" or path == None:
        return redirect("https://github.com/PouekDEV/reddit-proxy", code=302)
    if not "reddit" in path:
        return 'Not a reddit link'
    if not "https://" in path:
        path = path.replace("https:/","https://")
    r = requests.get(url=path+".json",cookies=cookies,headers=headers)
    info = json.loads(r.text)[0]["data"]["children"][0]["data"]
    name = info["subreddit_name_prefixed"]
    title = info["title"]
    try:
        width = info["media"]["reddit_video"]["width"]
        height = info["media"]["reddit_video"]["height"]
    except (TypeError, KeyError):
        try:
            width = info["preview"]["images"][0]["variants"]["gif"]["source"]["width"]
            height = info["preview"]["images"][0]["variants"]["gif"]["source"]["height"]
        except (TypeError, KeyError):
            try:
                width = info["preview"]["reddit_video_preview"]["width"]
                height = info["preview"]["reddit_video_preview"]["height"]
            except (TypeError, KeyError):
                return 'This post is not a video or the video is not hosted on reddit'
    return '<head><meta name="theme-color" content="#FF4500"><meta http-equiv="refresh" content="0; url='+path+'"><meta property="og:title" content="'+name+' - '+title+'"><meta property="og:url" content="'+path+'"><meta property="og:video" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:image" content="http://'+str(request.host)+'/video'+str(request.full_path)+'"><meta property="og:type" content="video"><meta property="og:video:type" content="video/mp4"><meta property="og:video:width" content="'+str(width)+'"><meta property="og:video:height" content="'+str(height)+'"></head>'

if __name__ == "__main__":
    app.run(host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443)