
# 手話タウン to Anki

このツールは [手話タウンハンドブック](https://handbook.sign.town/ja/feed?sl=JSL) の学習資料から WebP を生成し、Anki パッケージにします。

現在、JSLにのみ対応しています。
生成されるカードは、現在確認している数で延べ 1,290 枚です。

## 依存関係

- [uv](https://github.com/astral-sh/uv)

## インストール

uv 導入済みの環境で、以下のコマンドからインストールしてください。

```zsh
uv tool install git+https://github.com/mootah/signtown_to_anki
```

## 使い方

### ヘルプ

```zsh
signtown-to-anki --help
```

### 推奨

オプションを何も指定しなければ、推奨設定で実行されます。

```zsh
signtown-to-anki
```

### 動画をダウンロードしない

```zsh
signtown-to-anki --no-download
```

## 注意事項

- 動画のファイルサイズや再生方法は、利用する環境や設定によって変わります。
- AnkiDroidではURL(非DL)でも再生できました。
- 当方は、学習資料の著作権および所有権を有していません。当ツールの利用は個人学習の範囲に限ることを想定しており、再配布や商用利用を行う場合は handbook.sign.town の利用規約や許諾を確認してください。
