import os, sys, json, random, time, subprocess
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import genanki
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


def get_categories() -> dict:
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
    cats = jsondata["props"]["pageProps"]["initialData"]
    
    return cats


def get_signs_in_category(cat_id):
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


def download_video(url, filename):
    filepath = f"{MEDIA_PATH}/{filename}"

    if os.path.exists(filepath):
        return

    cmd = [
        "ffmpeg", "-i", url,
        "-vcodec", "libsvtav1",
        "-crf", "22",
        "-b:v", "0",
        "-preset", "4",
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
    filenames = [
        "style.css",
        "ja2jsl_front.template.anki",
        "ja2jsl_back.template.anki",
        "jsl2ja_front.template.anki",
        "jsl2ja_back.template.anki",
    ]
    
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
            "video": video_file,
            "video_url": video_url,
            "page_url": page_url,
            "category": category
        })
        
    return notes


def write_in_apkg(notes: list):
    templates = load_templates()
    model_id = random.randrange(1 << 30, 1 << 31)
    
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
            {
                "name": "JA->JSL",
                "qfmt": templates["ja2jsl_front"],
                "afmt": templates["ja2jsl_back"],
            },
            {
                "name": "JSL->JA",
                "qfmt": templates["jsl2ja_front"],
                "afmt": templates["jsl2ja_back"],
            },
        ],
        css=templates["style"],
    )

    decks = {}
    for n in notes:
        category = n["category"]
        if category not in decks:
            deck_id = random.randrange(1 << 30, 1 << 31)
            deck_name = f"手話タウンハンドブック::{category}"
            decks[category] = genanki.Deck(deck_id, deck_name)

        # 変更点: videoフィールド（インデックス3）がある場合、<img>タグで囲む
        fields = list(n.values())
        if fields[3]:
            fields[3] = f'<img src="{fields[3]}">'

        note = genanki.Note(model=model, fields=fields)
        decks[category].add_note(note)

    package = genanki.Package(list(decks.values()))

    if DOWNLOAD:
        media = []
        os.makedirs(MEDIA_PATH, exist_ok=True)
        print("動画をダウンロードしています...")

        def download_task(n):
            download_video(n["video_url"], n["video"])
            return f"{MEDIA_PATH}/{n['video']}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
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
    write_in_apkg(notes)

if __name__ == "__main__":
    main()
