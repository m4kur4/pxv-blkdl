## 起動手順
1. `/src`でvirtualenvを起動
```bash
# Windows(bash)
source Scripts/activate
# OSX
source bin/activate
```
2. _layout.pyを起動
```bash
python _layout.py
```

## 環境移行手順
1. git clone
```
$ git clone <repo>
```

2. virtualenvを構築＋起動
```bash
$ cd <cloneしたフォルダ>
$ virtualenv .
$ source bin/activate
```

3. requirement.txtからpipでパッケージを入れる
```bash
$ pip install -r requirements.txt
```
