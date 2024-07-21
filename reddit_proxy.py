from flask import Flask, send_file, request, redirect
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import ffmpeg
import yt_dlp
import json
import os
import re
import io

load_dotenv()

app = Flask("reddit-proxy")
# We need these just in case reddit blocked our IP
cookies = {
    "reddit_session": os.getenv("REDDIT_SESSION"),
    "token_v2": os.getenv("TOKEN_V2"),
}
headers = {
    'User-Agent': 'linux:https://github.com/PouekDEV/reddit-proxy:v1.1.0 (by /u/Pouek_)',
    'From': 'stuff@pouekdev.one'
}
encoding = os.getenv("ENCODING", 'False').lower() in ('true', '1', 't')
combine_audio_video = os.getenv("COMBINE_AUDIO_VIDEO", 'False').lower() in ('true', '1', 't')
directory = os.getenv("DIRECTORY")
ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=mp4]/mp4+best[height<=720]',
    'ignoreerrors': True,
    'extract_flat': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'outtmpl': directory+"%(title)s.%(ext)s"
}

# Remove cached files on boot
files = os.listdir(directory)
for file in files:
    if ".mp4" in file:
        os.remove(directory+file)

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
    if not "comments" in path:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        path = soup.find("shreddit-canonical-url-updater")["value"]
    try:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        info = json.loads(soup.find("shreddit-player")["packaged-media-json"])["playbackMp4s"]["permutations"]
        url = info[len(info)-1]["source"]["url"]
    # Fallback to a video without sound
    except (TypeError, KeyError):
        if "/" == path[-1]:
            json_path = path[:-1]
            json_path = json_path + ".json"
        else:
            json_path = path + ".json"
        r = requests.get(url=json_path,cookies=cookies,headers=headers)
        info = json.loads(r.text)[0]["data"]["children"][0]["data"]
        try:
            url = info["media"]["reddit_video"]["fallback_url"]
            name = info["id"]
            if combine_audio_video:
                # If it's not a gif we can try and combine the audio and video ourselves
                if not info["media"]["reddit_video"]["is_gif"] and encoding:
                    audio_url = info["url"]
                    audio_url = audio_url + "/DASH_AUDIO_"
                    r = requests.get(url=info["media"]["reddit_video"]["hls_url"],cookies=cookies,headers=headers)
                    best_hls = ""
                    for line in r.text.splitlines():
                        if "#EXT-X-MEDIA" in line:
                            hls = re.search('HLS_AUDIO_(.*).m3u8',line)
                            best_hls = hls.group(1)
                    audio_url = audio_url + best_hls + ".mp4"
                    if not os.path.exists(directory+name+".mp4"):
                        audio = ffmpeg.input(audio_url)
                        video = ffmpeg.input(url)
                        try:
                            ffmpeg.output(audio, video, directory+name+".mp4", format="mp4", vcodec="libx264", acodec="copy", crf=27, preset="veryfast").run(overwrite_output=True)
                        except ffmpeg.Error:
                            return redirect(url, code=302)
                    file = open(directory+name+".mp4", "rb")
                    returnable_result = io.BytesIO(file.read())
                    file.close()
                    return send_file(path_or_file=returnable_result,download_name="reddit_video.mp4")
                # In case of disabled encoding utilize yt-dlp
                elif not info["media"]["reddit_video"]["is_gif"]:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(path, download=False)
                        title = ydl.prepare_filename(info)
                        if not os.path.exists(title):
                            ydl.download(path)
                    try:
                        file = open(title, "rb")
                        returnable_result = io.BytesIO(file.read())
                        file.close()
                        return send_file(path_or_file=returnable_result,download_name="reddit_video.mp4")
                    # Reddit blocked us so proceed with the file without audio
                    except FileNotFoundError:
                        pass
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
    if not "comments" in path:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        path = soup.find("shreddit-canonical-url-updater")["value"]
    if "/" == path[-1]:
        json_path = path[:-1]
        json_path = json_path + ".json"
    else:
        json_path = path + ".json"
    r = requests.get(url=json_path,cookies=cookies,headers=headers)
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