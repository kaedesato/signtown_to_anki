import os, sys, json, random, time, subprocess
import concurrent.futures
import requests
import pycurl
from bs4 import BeautifulSoup
import genanki
import imageio_ffmpeg
from rich import print
from rich.progress import track
import rich_click as click

DOWNLOAD = True
MEDIA_PATH = "collection.media"

def read(file_path: str) -> str:
    try: 
        text = ""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return text
    except:
        print("ファイルが開けませんでした。", file_path)
        sys.exit(1)


def get_categories() -> list:
    json_path = f"{config["media_path"]}/categories.json"

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            jsondata = json.load(f)
    else:
        url = "https://handbook.sign.town/ja/collections?sl=JSL"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except:
            print("WEBページへのアクセスに失敗しました。")
            sys.exit(1)
    
        soup = BeautifulSoup(response.text, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")

        if not next_data:
            print("カテゴリリストが見つかりませんでした。")
            sys.exit(1)

        jsondata = json.loads(next_data.string)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(jsondata, f, ensure_ascii=False, indent=2)

    cats = jsondata["props"]["pageProps"]["initialData"]
    
    return cats


def get_signs_in_category(cat_id):
    json_path = f"{config["media_path"]}/signs_{cat_id}.json"

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            jsondata = json.load(f)
    else:
        url = f"https://handbook.sign.town/ja/collections/module/{cat_id}?sl=JSL"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except:
            print("WEBページへのアクセスに失敗しました。")
            sys.exit(1)

        soup = BeautifulSoup(response.text, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")

        if not next_data:
            print("手話リストが見つかりませんでした")
            sys.exit(1)

        jsondata = json.loads(next_data.string)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(jsondata, f, ensure_ascii=False, indent=2)

    signs = jsondata["props"]["pageProps"]["moduleData"]["signList"]
    return signs


def get_signs(cats: list) -> list:
    signs = []
    for cat in track(cats):
        time.sleep(0.2)
        signs_in_cat = get_signs_in_category(cat["id"])
        
        for sign in signs_in_cat:
            sign["category"] = cat["title"]
            sign["category_id"] = cat["id"]

        signs += signs_in_cat

    return signs


def get_ffmpeg_exe():
    global config
    if config["ffmpeg_exe"]:
        return config["ffmpeg_exe"]

    # Prefer system-installed ffmpeg
    try:
        system_ffmpeg = shutil.which("ffmpeg")
    except Exception:
        system_ffmpeg = None

    if system_ffmpeg:
        config["ffmpeg_exe"] = system_ffmpeg
        return config["ffmpeg_exe"]

    # Fall back to imageio-ffmpeg
    config["ffmpeg_exe"] = imageio_ffmpeg.get_ffmpeg_exe()
    return config["ffmpeg_exe"]


def download_video(url, video_path):
    if os.path.exists(video_path):
        return

    try:
        with open(video_path, "wb") as f:
            curl = pycurl.Curl()
            curl.setopt(curl.URL, url)
            curl.setopt(curl.WRITEDATA, f)
            curl.setopt(curl.NOPROGRESS, False)
            curl.setopt(curl.XFERINFOFUNCTION, lambda dltotal, dlnow, ultotal, ulnow: None)
            curl.perform()
            curl.close()
    except KeyboardInterrupt:
        print("ダウンロードを中断しています...")
        if os.path.exists(video_path):
            os.remove(video_path)
        sys.exit(1)
    except pycurl.error as e:
        print(f"ダウンロードできませんでした。: {e}")
        if os.path.exists(video_path):
            os.remove(video_path)
    except Exception as e:
        print(f"ダウンロードできませんでした。: {e}")
        if os.path.exists(video_path):
            os.remove(video_path)


def convert_to_mp4(input_path, output_path):
    ffmpeg_exe = get_ffmpeg_exe()

    if not os.path.exists(input_path):
        return

    if os.path.exists(output_path):
        return

    cmd = [
        "ffmpeg", "-i", url,
        "-vcodec", "libsvtav1",
        "-crf", "24",
        "-b:v", "0",
        "-preset", "12",
        "-pix_fmt", "yuv420p",
        "-an",
        "-loglevel", "error",
        filepath
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("コマンドがありません。: ffmpeg")
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)


def load_templates():
    template_path = os.path.join(os.path.dirname(__file__), "templates")
    
    templates = {}
    for filename in filenames:
        filepath = os.path.join(template_path, filename)
        data = read(filepath)
        key = filename.split(".")[0]
        templates[key] = data

    return templates

def create_notes(signs: list) -> list[dict]:
    notes = []

    for sign in signs:
        note_id     = sign["id"]
        definition  = sign["signDefinitions"]["ja"][0]["def"]
        position    = sign["signDefinitions"]["ja"][0]["pos"]
        rawvideo    = f"{note_id}.raw.mp4"
        mp4_file    = f"{note_id}.mp4"
        webm_file   = f"{note_id}.webm"
        video_file  = rawvideo

        if config["should_convert"] and config["format"] == "mp4":
            video_file = mp4_file
        elif config["should_convert"] and config["format"] == "webm":
            video_file = webm_file

        # image_file  = f"{note_id}.gif"
        image_file  = f"{note_id}.webp"
        video_url   = sign["defaultVideoUrl"]
        page_url    = f"https://handbook.sign.town/ja/signs/{note_id}?sl=JSL"
        category    = sign["category"]
        # category_id    = sign["category_id"]
        
        video_file = ""
        if DOWNLOAD:
            video_file = f"{note_id}.avif"

        notes.append({
            "id":  note_id,
            "def": definition,
            "pos": position,
            "rawvideo_file": rawvideo,
            "mp4_file": mp4_file,
            "webm_file": webm_file,
            "video": video_file,
            "video_url": video_url,
            "page_url": page_url,
            "category": category
        })
        
    return notes


def create_video_model() -> genanki.Model:
    filenames = [
        "style.css",
        "ja-jsl_video_front.template.anki",
        "ja-jsl_video_back.template.anki",
        "jsl-ja_video_front.template.anki",
        "jsl-ja_video_back.template.anki",
    ]
    template_files = load_templates(filenames)
    model_id = random.randrange(1 << 30, 1 << 31)
    templates = []

    if config["template"] in ["ja-jsl", "all"]:
        templates.append({
            "name": "JA->JSL",
            "qfmt": template_files["ja-jsl_video_front"],
            "afmt": template_files["ja-jsl_video_back"],
        })
    if config["template"] in ["jsl-ja", "all"]:
        templates.append({
            "name": "JSL->JA",
            "qfmt": template_files["jsl-ja_video_front"],
            "afmt": template_files["jsl-ja_video_back"],
        })
    model = genanki.Model(
        model_id,
        "JSL",
        fields=[
            {"name": "id"},
            {"name": "def"},
            {"name": "pos"},
            {"name": "video"},
            {"name": "video_url"},
            {"name": "page_url"},
            {"name": "category"},
        ],
        templates=[
            # {
            #     "name": "JA->JSL",
            #     "qfmt": templates["ja2jsl_front"],
            #     "afmt": templates["ja2jsl_back"],
            # },
            {
                "name": "JSL->JA",
                "qfmt": templates["jsl2ja_front"],
                "afmt": templates["jsl2ja_back"],
            },
        ],
        templates=templates,
        css=template_files["style"],
    )

    decks = {}
    for n in notes:
        category = n["category"]
        if category not in decks:
            deck_id = random.randrange(1 << 30, 1 << 31)
            deck_name = f"手話タウンハンドブック::{category}"
            decks[category] = genanki.Deck(deck_id, deck_name)

        note = genanki.Note(model=model, fields=list(n.values()))
        decks[category].add_note(note)

    package = genanki.Package(list(decks.values()))

    if DOWNLOAD:
        media = []
        os.makedirs(MEDIA_PATH, exist_ok=True)
        print("動画をダウンロードしています...")

        def download_task(n):
            download_video(n["video_url"], n["video"])
            return f"{MEDIA_PATH}/{n['video']}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            media = list(track(executor.map(download_task, notes), total=len(notes)))

        package.media_files = media

    apkg_path = f"手話タウンハンドブック.apkg"
    package.write_to_file(apkg_path)
    print("Ankiパッケージを作成しました。")


@click.command(help="handbook.sign.townをスクレイピングしてAnkiパッケージを作るコマンド")
@click.option("--no-download", is_flag=True,
    help="動画をDLしません")
def main(**kwargs):
    global DOWNLOAD
    DOWNLOAD = not kwargs["no_download"]

    print("カテゴリ一覧を読み込んでいます...")
    cats = get_categories()
    print("各カテゴリの手話一覧を読み込んでいます...")
    signs = get_signs(cats)
    notes = create_notes(signs)
    media = make_media(notes)
    print("Ankiパッケージを生成しています...")
    write_in_apkg(notes, media, cats)

if __name__ == "__main__":
    main()
