from gevent import monkey
monkey.patch_all()
from flask import Flask, send_file, request, redirect
from flask_compress import Compress
from flask_caching import Cache
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import ffmpeg
import base64
import json
import os
import re
import io

load_dotenv()

# We need these just in case reddit blocked our IP
cookies = {
    "reddit_session": os.getenv("REDDIT_SESSION"),
    "token_v2": os.getenv("TOKEN_V2"),
    "loid": os.getenv("LOID"), # This is a temporary solution... until it stops working
}
headers = {
    "User-Agent": "linux:https://github.com/PouekDEV/reddit-proxy:v1.5.0 (by /u/Pouek_)",
    "From": "stuff@pouekdev.one"
}
config = {
    "DEBUG": False,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}
ffmpeg_headers = f"User-Agent: {headers['User-Agent']}\r\n"
combine_audio_video = os.getenv("COMBINE_AUDIO_VIDEO", "False").lower() in ("true", "1", "t")
directory = os.getenv("DIRECTORY")

# Remove cached files on boot
files = os.listdir(directory)
for file in files:
    if ".mp4" in file:
        if os.path.exists(directory+file):
            os.remove(directory+file)

def make_key(path=None):
    if path == None:
        path = request.url
    user_agent = request.headers.get("User-Agent")
    return f"{path}{user_agent}"

app = Flask("reddit-proxy")
app.config.from_mapping(config)
cache = Cache(app)
compress = Compress(app)
compress.cache = cache
compress.cache_key = make_key

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nDisallow: /"

@app.route('/favicon.ico')
def favicon():
    return "404"

@app.route('/oembed')
@cache.cached(make_cache_key=make_key)
def oembed():
    embed = request.args.get("embed")
    if embed != None:
        try:
            data = json.loads(base64.b64decode(embed.encode()).decode())
            # Check if the keys are present just in case somebody would use this as their personal base64 decoder
            if "type" in data and "author_name" in data and "author_url" in data and "provider_name" in data and "version" in data:
                return json.dumps(data)
            else:
                return "Invalid data"
        except Exception:
            return "Error while decoding the string"
    else:
        return "No parameter provided"

@app.route('/video/', defaults={'path': ''})
@app.route('/video/<path:path>')
def video(path):
    if path == "" or path == None:
        return redirect("https://github.com/PouekDEV/reddit-proxy", code=302)
    if not "reddit" in path:
        return "Not a reddit link"
    if not "https://" in path:
        if not "https:/" in path:
            path = f"https://{path}"
        else:
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
                    audio_url = info["url"]
                    audio_source = "/DASH_AUDIO_"
                    r = requests.get(url=info["media"]["reddit_video"]["hls_url"],cookies=cookies,headers=headers)
                    best_hls = 0
                    for line in r.text.splitlines():
                        if "#EXT-X-MEDIA" in line:
                            hls = re.search('HLS_AUDIO_(.*).m3u8',line)
                            if hls == None:
                                audio_source = "/CMAF_AUDIO_"
                                hls = re.search('CMAF_AUDIO_(.*).m3u8',line)
                                if int(hls.group(1)) > best_hls:
                                    best_hls = int(hls.group(1))
                            else:
                                best_hls = hls.group(1)
                    audio_url = audio_url + audio_source + str(best_hls) + ".mp4"
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
                    return "There was an error finding media in this post"
    return redirect(url, code=302)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@cache.cached(make_cache_key=make_key)
def embed(path):
    if path == "" or path == None:
        return redirect("https://github.com/PouekDEV/reddit-proxy", code=302)
    if not "reddit" in path:
        return "Not a reddit link"
    if not "https://" in path:
        if not "https:/" in path:
            path = f"https://{path}"
        else:
            path = path.replace("https:/","https://")
    if not "Discordbot" in request.headers.get("User-Agent"):
        return redirect(path, code=302)
    if not "comments" in path:
        r = requests.get(url=path,cookies=cookies,headers=headers)
        soup = BeautifulSoup(r.text, features="html.parser")
        path = soup.find("div", {"id": "canonical-url-updater"})["value"]
    if "/" == path[-1]:
        json_path = path[:-1] + ".json"
    else:
        json_path = path + ".json"
    r = requests.get(url=json_path,cookies=cookies,headers=headers)
    info = json.loads(r.text)[0]["data"]["children"][0]["data"]
    try:
        thumbnail = info["preview"]["images"][0]["source"]["url"]
        thumbnail = thumbnail.replace("&amp;","&")
    except (TypeError, KeyError):
        thumbnail = ""
    name = info["subreddit_name_prefixed"]
    user = info["author"]
    description = info["selftext"]
    gallery_text = ""
    title = info["title"]
    title = title.replace('"',"&quot;")
    url = info["url"]
    tags = ""
    image_count = -1
    oembed_data = {
        "type": "link",
        "author_name": title,
        "author_url": path,
        "provider_name": "r.pouekdev.one",
        "version": "1.0"
    }
    oembed_data = json.dumps(oembed_data)
    oembed_data = base64.b64encode(oembed_data.encode()).decode()
    oembed_link = f"https://{request.host}/oembed?embed={oembed_data}"
    text_only = False
    if "gallery" in url:
        try:
            if len(info["media_metadata"]) > 4:
                image_count = 4
            else:
                image_count = len(info["media_metadata"])
            tags = '<meta property="og:type" content="photo">' \
                '<meta name="twitter:card" content="summary_large_image">'
            gallery_text = f"Gallery: {len(info['media_metadata'])} images\n\n"
            gallery = []
            for i in range(image_count):
                gallery.append(info["gallery_data"]["items"][i]["media_id"])
            for image in gallery:
                try:
                    img = info["media_metadata"][image]
                    tags = tags + f'<meta property="og:image" content="{img["s"]["u"]}">' \
                            f'<meta property="og:image:width" content="{img["s"]["x"]}">' \
                            f'<meta property="og:image:height" content="{img["s"]["y"]}">' \
                            f'<meta name="twitter:image:src" content="{img["s"]["u"]}">'
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
                    if thumbnail != "":
                        tags = f'<meta property="og:image" content="{thumbnail}">'
                    else:
                        text_only = True
    if image_count < 0 and not text_only:
        if not ".gif" in info["url"][-4:] and not ".jpeg" in info["url"][-5:] and not ".jpg" in info["url"][-4:] and not ".png" in info["url"][-4:]:
            tags = f'<meta property="og:video" content="/video/{path}">' \
                f'<meta property="og:video:secure_url" content="/video/{path}">' \
                f'<meta property="twitter:player" content="/video/{path}">' \
                '<meta property="og:type" content="video.other">' \
                f'<meta property="og:image" content="{thumbnail}">' \
                '<meta property="og:video:type" content="video/mp4">' \
                f'<meta property="og:video:width" content="{width}">' \
                f'<meta property="og:video:height" content="{height}">' \
                f'<meta property="twitter:player:width" content="{width}">' \
                f'<meta property="twitter:player:height" content="{height}">'
        else:
            tags = f'<meta property="og:image" content="{url}">' \
                f'<meta name="twitter:image:src" content="{url}">' \
                '<meta property="og:type" content="photo">' \
                f'<meta property="og:image:width" content="{width}">' \
                f'<meta property="og:image:height" content="{height}">' \
                '<meta name="twitter:card" content="summary_large_image">'
    if len(description) > 0 or len(gallery_text) > 0:
        tags = tags + f'<meta property="og:description" content="{gallery_text}{description}">' \
                f'<meta property="twitter:description" content="{gallery_text}{description}">'
    return '<html>' \
        '<head>' \
        '<meta name="theme-color" content="#FF4500">' \
        f'<meta property="og:title" content="u/{user} on {name}">' \
        f'<meta property="twitter:title" content="u/{user} on {name}">' \
        f'<meta property="twitter:creator" content="{title}">' \
        f'<meta property="og:url" content="{path}">' \
        f'<link rel="alternate" type="application/json+oembed" title="u/{user} on {name}" href="{oembed_link}">' \
        f'<link rel="canonical" href="{path}">' \
        '<meta name="og:site_name" content="r.pouekdev.one">' \
        '<meta name="twitter:site" content="r.pouekdev.one">' \
        f"{tags}" \
        '</head>' \
        '</html>'

if __name__ == "__main__":
    app.run(host=os.getenv("HOST") or '0.0.0.0', port=os.getenv("PORT") or 4443)