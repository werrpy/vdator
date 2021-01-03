"""
Experimental REST API

> python3 api.py
GET http://127.0.0.1:5000/paste?url=[ENCODED_URL_HERE]
{"reply":"..."}

GET http://127.0.0.1:5000/parse?url=[ENCODED_URL_HERE]
{"reply":"..."}
"""

import json, os, traceback
from urllib.parse import unquote
from flask import Flask, jsonify, request

# APIs
import discord
from discord.utils import get

# parsers
from helpers import balanced_blockquotes, split_string
from url_parser import URLParser
from bdinfo_parser import BDInfoParser
from paste_parser import PasteParser
from media_info_parser import MediaInfoParser
from codecs_parser import CodecsParser
from source_detector import SourceDetector
from reporter import Reporter, add_status_reactions
from checker import Checker

# initialize parsers
with open('data/urls.json') as f:
  urls = json.load(f)['urls']
  url_parser = URLParser(urls)

bdinfo_parser = BDInfoParser()
paste_parser = PasteParser(bdinfo_parser)
mediainfo_parser = MediaInfoParser()

with open('data/codecs.json') as f:
  codecs = json.load(f)
  codecs_parser = CodecsParser(codecs)

source_detector = SourceDetector()
reporter = Reporter()
checker = Checker(codecs_parser, source_detector, reporter)

app = Flask(__name__)

@app.route('/paste', methods=['GET'])
def parse_url():
    """
    This is the language awesomeness API
    Call this api passing a language name and get back its features
    ---
    tags:
      - Awesomeness Language API
    parameters:
      - name: url
        in: path
        type: string
        required: true
        description: The pastebin url
    responses:
      200:
        description: A language with its awesomeness
        schema:
          id: awesome
          properties:
            language:
              type: string
              description: The language name
              default: Lua
            features:
              type: array
              description: The awesomeness list
              items:
                type: string
              default: ["perfect", "simple", "lovely"]

    """

    url = unquote(request.args.get('url'))

    paste = url_parser.get_paste(url)
    bdinfo, mediainfo, eac3to = paste_parser.parse(paste)
    
    reply = "<" + url + ">" + "\n"

    try:
      # parse mediainfo
      mediainfo = mediainfo_parser.parse(mediainfo)

      # setup/reset reporter
      reporter.setup()
      # setup checker
      checker.setup(bdinfo, mediainfo, eac3to, 'remux-bot')

      # run all checks
      reply += checker.run_checks()
      
      # report
      reply += reporter.display_report()
    except:
      traceback.print_exc()
      reply += "\n[ERROR] vdator failed to parse\n"

    return jsonify({'reply': reply})

@app.route('/text', methods=['POST'])
def parse_text():
    '''
    POST http://127.0.0.1:5000/text
    Body, raw
    [INSERT TEXT HERE]
    '''

    text = request.get_data().decode("utf-8")
    bdinfo, mediainfo, eac3to = paste_parser.parse(text)
    
    reply = ""

    try:
      # parse mediainfo
      mediainfo = mediainfo_parser.parse(mediainfo)

      # setup/reset reporter
      reporter.setup()
      # setup checker
      checker.setup(bdinfo, mediainfo, eac3to, 'remux-bot')

      # run all checks
      reply += checker.run_checks()
      
      # report
      reply += reporter.display_report()
    except:
      traceback.print_exc()
      reply += "\n[ERROR] vdator failed to parse\n"

    return jsonify({'reply': reply})


app.run()
