# vdator
Remux validator Discord bot

Takes a Pastebin link with BDInfo and MediaInfo dump, and validates the remux.

Checks:
```
Video track names
Movie name format
Video and audio track names
DTS-HD MA 1.0/2.0 to FLAC, LPCM 1.0/2.0 to FLAC, LPCM > 2.0 to DTS-HD MA
Commentary to AC-3 @ 224 kbps
Text muxing mode
Commentary track people and spellcheck
Subtitle order
Chapter languages
```

### Setup

Use [pip and virtual env](https://packaging.python.org/guides/installing-using-pip-and-virtualenv/) to run vdator.

Create a [Discord bot](https://discordapp.com/developers/docs/intro) and add it to a server.
Edit `vdator\.env` and set `DISCORD_BOT_SECRET` to your bot's token.

Request a [TMDB API Key](https://developers.themoviedb.org/3/getting-started/introduction) and set `TMDB_API_KEY`.

Don't forget to create channels on the server and set them in `vdator\.env` for `REVIEW_CHANNELS`, `REVIEW_REPLY_CHANNELS`, and `BOT_CHANNELS`.

### Install dependencies

Install [pyhunspell](https://github.com/blatinier/pyhunspell#installation)

Install dependencies

```
pip3 install -r requirements.txt
```

### Update dependencies

```
pip3 install -r requirements.txt --upgrade
pip3 freeze > requirements.txt
```

### Running with systemd

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
