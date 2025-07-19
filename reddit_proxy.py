from gevent import monkey
monkey.patch_all()
from flask import Flask, send_file, request, redirect
from flask_caching import Cache
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

config = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}
# We need these just in case reddit blocked our IP
cookies = {
    "reddit_session": os.getenv("REDDIT_SESSION"),
    "token_v2": os.getenv("TOKEN_V2"),
}
headers = {
    'User-Agent': 'linux:https://github.com/PouekDEV/reddit-proxy:v1.3.0 (by /u/Pouek_)',
    'From': 'stuff@pouekdev.one'
}
ffmpeg_headers = "User-Agent: "+headers["User-Agent"]+"\r\n"
encoding = os.getenv("ENCODING", 'False').lower() in ('true', '1', 't')
combine_audio_video = os.getenv("COMBINE_AUDIO_VIDEO", 'False').lower() in ('true', '1', 't')
directory = os.getenv("DIRECTORY")
ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=mp4]/mp4+best[height<=720]',
    'ignoreerrors': True,
    'extract_flat': True,
    'restrictfilenames': True,
    'noplaylist': True,
    'outtmpl': directory+"%(id)s.%(ext)s"
}

# Remove cached files on boot
files = os.listdir(directory)
for file in files:
    if ".mp4" in file:
        os.remove(directory+file)

app = Flask("reddit-proxy")
app.config.from_mapping(config)
cache = Cache(app)

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
        path = soup.find("div", {"id": "canonical-url-updater"})["value"]
    try:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        info = json.loads(soup.find("shreddit-player-2")["packaged-media-json"])["playbackMp4s"]["permutations"]
        url = info[len(info)-1]["source"]["url"]
    # Fallback to a video without sound
    except (TypeError, KeyError):
        if "/" == path[-1]:
            json_path = path[:-1] + ".json"
        else:
            json_path = path + ".json"
        r = requests.get(url=json_path,cookies=cookies,headers=headers)
        info = json.loads(r.text)[0]["data"]["children"][0]["data"]
        try:
            name = info["url"].replace("https://v.redd.it/","")
            url = info["media"]["reddit_video"]["fallback_url"]
            # If it's not a gif we can try and combine the audio and video ourselves
            if combine_audio_video and not info["media"]["reddit_video"]["is_gif"]:
                if not os.path.exists(directory+name+".mp4"):
                    if encoding:
                        audio_url = info["url"]
                        audio_url = audio_url + "/DASH_AUDIO_"
                        r = requests.get(url=info["media"]["reddit_video"]["hls_url"],cookies=cookies,headers=headers)
                        best_hls = ""
                        for line in r.text.splitlines():
                            if "#EXT-X-MEDIA" in line:
                                hls = re.search('HLS_AUDIO_(.*).m3u8',line)
                                best_hls = hls.group(1)
                        audio_url = audio_url + best_hls + ".mp4"
                        audio = ffmpeg.input(audio_url,headers=ffmpeg_headers)
                        video = ffmpeg.input(url,headers=ffmpeg_headers)
                        try:
                            ffmpeg.output(audio, video, directory+name+".mp4", format="mp4", vcodec="copy", acodec="copy", crf=27, preset="veryfast").run(overwrite_output=True)
                        except ffmpeg.Error:
                            return redirect(url, code=302)
                        file = open(directory+name+".mp4", "rb")
                        returnable_result = io.BytesIO(file.read())
                        file.close()
                        return send_file(path_or_file=returnable_result,download_name=name+".mp4")
                    # In case of disabled encoding utilize yt-dlp
                    else:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(path, download=False)
                            title = ydl.prepare_filename(info)
                            ydl.download(path)
                        try:
                            file = open(title, "rb")
                            returnable_result = io.BytesIO(file.read())
                            file.close()
                            return send_file(path_or_file=returnable_result,download_name=name+".mp4")
                        # Reddit blocked us so proceed with the file without audio
                        except FileNotFoundError:
                            pass
                else:
                    file = open(directory+name+".mp4", "rb")
                    returnable_result = io.BytesIO(file.read())
                    file.close()
                    return send_file(path_or_file=returnable_result,download_name=name+".mp4")
        except (TypeError, KeyError):
            try:
                url = info["preview"]["reddit_video_preview"]["fallback_url"]
            except (TypeError, KeyError):
                try:
                    url = soup.find("shreddit-player-2")["src"]
                except (TypeError, KeyError):
                    return 'There was an error finding media in this post'
    return redirect(url, code=302)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@cache.cached()
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
        path = soup.find("div", {"id": "canonical-url-updater"})["value"]
    if not "Discordbot" in request.headers.get("User-Agent"):
        return redirect(path, code=302)
    if "/" == path[-1]:
        json_path = path[:-1] + ".json"
    else:
        json_path = path + ".json"
    r = requests.get(url=json_path,cookies=cookies,headers=headers)
    info = json.loads(r.text)[0]["data"]["children"][0]["data"]
    try:
        thumbnail = info["preview"]["images"][0]["source"]["url"]
    except (TypeError, KeyError):
        thumbnail = ""
    name = info["subreddit_name_prefixed"]
    title = info["title"]
    title = title.replace('"',"&quot;")
    url = info["url"]
    tags = ""
    image_count = -1
    if "gallery" in url:
        try:
            if len(info["media_metadata"]) > 4:
                image_count = 4
            else:
                image_count = len(info["media_metadata"])
            tags = '<meta property="og:type" content="image"><meta name="twitter:card" content="summary_large_image"><meta property="og:description" content="Gallery: '+str(len(info["media_metadata"]))+' Images">'
            gallery = []
            for i in range(image_count):
                gallery.append(info["gallery_data"]["items"][i]["media_id"])
            for image in gallery:
                try:
                    img = info["media_metadata"][image]
                    tags = tags + '<meta property="og:image" content="'+img["s"]["u"]+'"><meta property="og:image:width" content="'+str(img["s"]["x"])+'"><meta property="og:image:height" content="'+str(img["s"]["y"])+'"><meta name="twitter:image:src" content="'+str(img["s"]["u"])+'">'
                except (TypeError, KeyError):
                    pass
        except (TypeError, KeyError):
            pass
    else:
        try:
            width = info["media"]["reddit_video"]["width"]
            height = info["media"]["reddit_video"]["height"]
        except (TypeError, KeyError):
            try:
                width = info["preview"]["images"][0]["source"]["width"]
                height = info["preview"]["images"][0]["source"]["height"]
            except (TypeError, KeyError):
                try:
                    width = info["preview"]["reddit_video_preview"]["width"]
                    height = info["preview"]["reddit_video_preview"]["height"]
                except (TypeError, KeyError):
                    tags = '<meta property="og:image" content="'+thumbnail+'">'
    if image_count < 0:
        if not ".gif" in info["url"][-4:] and not ".jpeg" in info["url"][-5:] and not ".jpg" in info["url"][-4:] and not ".png" in info["url"][-4:]:
            tags = '<meta property="og:video" content="https://'+str(request.host)+'/video/'+path+'"><meta property="og:type" content="video"><meta property="og:image" content="'+thumbnail+'"><meta property="og:video:type" content="video/mp4"><meta property="og:video:width" content="'+str(width)+'"><meta property="og:video:height" content="'+str(height)+'">'
        else:
            tags = '<meta property="og:image" content="'+url+'"><meta property="og:type" content="image"><meta property="og:image:type" content="image/gif"><meta property="og:image:width" content="'+str(width)+'"><meta property="og:image:height" content="'+str(height)+'"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image:src" content="'+url+'">'
    return '<head><meta name="theme-color" content="#FF4500"><meta property="og:title" content="'+name+' - '+title+'"><meta property="og:url" content="'+path+'"><meta name="og:site_name" content="r.pouekdev.one">'+tags+'</head>'

if __name__ == "__main__":
    app.run(host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443)