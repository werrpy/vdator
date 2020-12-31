# vdator
Remux validator Discord bot

Takes a Pastebin link with BDInfo and MediaInfo dump, and validates the remux.

Checks:
```
Video track names
Movie/TV name format
IMDB/TMDB ids
Filename
Video language matches first audio language
No muxing mode
Uses latest mkvtoolnix
Video and audio track names match
DTS-HD MA 1.0/2.0 to FLAC, LPCM 1.0/2.0 to FLAC, LPCM > 2.0 to DTS-HD MA
Commentary to AC-3 @ 224 kbps
Commentary track people and spellcheck
Subtitle order
Subtitle default flag
Should have chapters
Chapter languages
Chapter padding
```

### Table of Contents
- [Supported pastebin sites](#supported-pastebin-sites)
- [Setup](#setup)
  * [Create a python3 virtual environment](#create-a-python3-virtual-environment)
  * [Installing dependencies](#installing-dependencies)
  * [Updating dependencies](#updating-dependencies)
  * [Running with systemd](#running-manually)
  * [Running with systemd](#running-with-systemd)
- [Using](#using)
- [Adding a pastebin site](#adding-a-pastebin-site)

### Supported pastebin sites

- [Pastebin](https://pastebin.com/)
- [Hastebin](https://hastebin.com/)
- [termbin](https://termbin.com/)
- [{d}paste](https://dpaste.com/)
- [ghostbin.co](https://ghostbin.co/)
- [Hey! Paste it](https://www.heypasteit.com/)
- [CentOS Pastebin Service](https://paste.centos.org/)
- [Paste.ee](https://paste.ee/)
- [openSUSE Paste](https://paste.opensuse.org/)

### Setup

Create a [Discord bot](https://discordapp.com/developers/docs/intro) and add it to a server.
Edit `vdator/.env` and set `DISCORD_BOT_SECRET` to your bot's token.

Request a [TMDB API Key](https://developers.themoviedb.org/3/getting-started/introduction) and set `TMDB_API_KEY`.

Don't forget to create channels on the server and set them in `vdator/.env` for `REVIEW_CHANNELS`, `REVIEW_REPLY_CHANNELS`, and `BOT_CHANNELS`.

#### Create a python3 virtual environment:

Use [pip and virtual env](https://packaging.python.org/guides/installing-using-pip-and-virtualenv/) to run vdator.

In the `vdator` directory run:
```
python3 -m venv .
```

If the command fails to install pip, you will see an error similar to:
```
Error: Command '['python3', '-Im', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.
```
Start over by creating a virutal environment without pip, and then install pip manually inside it:
```
python3 -m venv --without-pip .
source bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
deactivate
```

#### Installing dependencies

Install [pyhunspell](https://github.com/blatinier/pyhunspell#installation)

Install dependencies

```
source bin/activate
pip3 install -r requirements.txt
deactivate
```

#### Updating dependencies

```
source bin/activate
pip3 install -r requirements.txt --upgrade
pip3 freeze > requirements.txt
deactivate
```

#### Running manually

Run the bot manually for testing, exceptions will get printed:
```
source bin/activate
python3 main.py
```

#### Running with systemd

Create a systemd service to run vdator, `/etc/systemd/system/vdator.service`

```
[Unit]
Description=vdator
After=multi-user.target

[Service]
WorkingDirectory=/home/USER/vdator/venv/vdator
User=
Group=
ExecStart=/home/USER/vdator/venv/bin/python3 /home/USER/vdator/venv/vdator/main.py
Type=idle
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

Set `User` to the user to run vdator as, and `Group` to the user's group (list with `groups`), usually both are the username.
Replace `/home/USER/vdator/venv/` with the full path to your venv.

Run `systemctl enable vdator` to start on boot. Use systemctl to start/stop vdator, `systemctl start vdator`, `systemctl stop vdator`, `systemctl restart vdator`

### Using

Type `!help` in one of the bot channels for more information.

### Adding a pastebin site

Edit `vdator/data/urls.json` and add your pastebin site.

```
# hostname
'example.com': {
    # regex to get paste's unique identifier
    'slug_regex': 'https://example.com/(.*)',
    
    # link to raw text using {} in place of the unique identifier
    'raw_url': 'https://example.com/raw/{}'
}
```
