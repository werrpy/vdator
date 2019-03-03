# vdator
Remux validator Discord bot

### Setup

Use [pip and virtual env](https://packaging.python.org/guides/installing-using-pip-and-virtualenv/) to run vdator.

Create a [Discord bot](https://discordapp.com/developers/docs/intro) and add it to a server.
Edit `vdator\.env` and set `DISCORD_BOT_SECRET` to your bot's token.

Request a [TMDB API Key](https://developers.themoviedb.org/3/getting-started/introduction) and set `TMDB_API_KEY`.

Don't forget to create channels on the server and set them in `vdator\.env` for `REVIEW_CHANNELS`, `REVIEW_REPLY_CHANNELS`, and `BOT_CHANNELS`.

### Install dependencies

Install [pyhunspell](https://github.com/blatinier/pyhunspell#installation)

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
