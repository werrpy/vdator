from dotenv import load_dotenv
import logging, os, re, requests, string, traceback
from pydash import has

# APIs
from iso639 import languages as iso639_languages
from langdetect import detect as langdetect_detect, DetectorFactory
import tmdbsimple as tmdb
from imdb import IMDb
import hunspell

# parsers
import nltk, nltk_people
from nltk_people import extract_names

# checks
from checks.mixins import SectionId, IsCommentaryTrack
from checks.remove_until_first_codec import RemoveUntilFirstCodec
from checks import *

# load environment variables
load_dotenv()

tmdb.API_KEY = os.environ.get("TMDB_API_KEY")
ia = IMDb()
logger = logging.getLogger("imdbpy")
logger.disabled = True

# make language detection deterministic
DetectorFactory.seed = 0

HUNSPELL_LANG = [x.strip() for x in os.environ.get("HUNSPELL_LANG").split(",")]
MISSPELLED_IGNORE_LIST = [
    x.strip() for x in os.environ.get("MISSPELLED_IGNORE_LIST").split(",")
]


class Checker(SectionId, IsCommentaryTrack):
    def __init__(self, codecs_parser, source_detector, reporter):
        self.codecs = codecs_parser
        self.remove_until_first_codec = RemoveUntilFirstCodec(codecs_parser)
        self.source_detector = source_detector
        self.reporter = reporter
        self.hobj = hunspell.HunSpell(HUNSPELL_LANG[0], HUNSPELL_LANG[1])

    def setup(self, bdinfo, mediainfo, eac3to, channel_name):
        self.bdinfo = bdinfo
        self.mediainfo = mediainfo
        self.eac3to = eac3to
        self.channel_name = channel_name
        self.source_detector.setup(bdinfo, mediainfo)

    def run_checks(self):
        reply = ""

        # check metadata
        reply += "> **Metadata**\n"
        reply += CheckMovieNameFormat(self.reporter, self.mediainfo).run()
        reply += CheckMetadataIds(self.reporter, self.mediainfo, tmdb, ia).run()
        reply += CheckFilename(
            self.reporter,
            self.source_detector,
            self.codecs,
            self.remove_until_first_codec,
            self.mediainfo,
            self.bdinfo,
            self.channel_name,
        ).run()
        reply += CheckTracksHaveLanguage(self.reporter, self.mediainfo).run()
        reply += CheckVideoLanguageMatchesFirstAudioLanguage(
            self.reporter, self.mediainfo
        ).run()
        reply += CheckMuxingMode(self.reporter, self.mediainfo).run()
        reply += CheckMKVMerge(self.reporter, self.mediainfo).run()
        reply += CheckDefaultFlag(self.reporter, self.mediainfo).run()

        # check video
        reply += "> **Video & Audio Tracks**\n"
        reply += CheckVideoTrack(
            self.reporter,
            self.source_detector,
            self.codecs,
            self.mediainfo,
            self.bdinfo,
        ).run()

        # check audio
        reply += CheckPrintAudioTrackNames(self.reporter, self.mediainfo).run()
        reply += CheckAudioTrackConversions(
            self.reporter,
            self.source_detector,
            self.remove_until_first_codec,
            self.mediainfo,
            self.bdinfo,
            self.eac3to
        ).run()
        # check FLAC audio using mediainfo
        reply += CheckFLACAudioTracks(
            self.reporter, self.remove_until_first_codec, self.mediainfo
        ).run()

        # TMDb and IMDb People API
        try:
            reply += self.check_people()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking IMDb/TMDb people"
            )
        try:
            reply += self.spell_check_track_name()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error spell checking track names"
            )

        # check text
        try:
            reply += self.print_text_tracks()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error printing text tracks")
        try:
            reply += self.check_text_order()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking text track order"
            )
        try:
            reply += self.check_text_default_flag()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking text track default flag"
            )

        # check chapters
        try:
            reply += self.print_chapters()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error printing chapters")
        try:
            reply += self.has_chapers()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking if should have chapters"
            )
        try:
            reply += self.chapter_language()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking chapter language"
            )
        try:
            reply += self.chapter_padding()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking chapter padding"
            )

        return reply

    def check_people(self):
        reply = ""

        # check people in audio track names
        for i, _ in enumerate(self.mediainfo["audio"]):
            if "title" in self.mediainfo["audio"][i]:
                title = self.mediainfo["audio"][i]["title"]

                # skip if has an audio codec
                _, _, found_codec = self.remove_until_first_codec.remove(title)
                if found_codec:
                    continue

                # try to match names
                matched_names = list()
                names = extract_names(title)
                search = tmdb.Search()
                for n in names:
                    # TMDb API
                    try:
                        search.person(query=n)
                        for s in search.results:
                            if n == s["name"]:
                                matched_names.append(n)
                    except:
                        reply += self.reporter.print_report(
                            "info", "Failed to get TMDb people data"
                        )
                    # IMDb API
                    try:
                        for person in ia.search_person(n):
                            if n == person["name"]:
                                matched_names.append(n)
                    except:
                        reply += self.reporter.print_report(
                            "info", "Failed to get IMDb people data"
                        )
                matched_names = set(matched_names)
                if len(matched_names) > 0:
                    reply += self.reporter.print_report(
                        "correct",
                        "Audio "
                        + self._section_id("audio", i)
                        + " People Matched: `"
                        + ", ".join(matched_names)
                        + "`",
                    )
                unmatched_names = set(names) - set(matched_names)
                if len(unmatched_names) > 0:
                    reply += self.reporter.print_report(
                        "warning",
                        "Audio "
                        + self._section_id("audio", i)
                        + " People Unmatched: `"
                        + ", ".join(unmatched_names)
                        + "`",
                    )

        return reply

    def spell_check_track_name(self):
        reply = ""

        # spellcheck audio track names
        for i, _ in enumerate(self.mediainfo["audio"]):
            if "title" in self.mediainfo["audio"][i]:
                title, title_parts, found_codec = self.remove_until_first_codec.remove(
                    self.mediainfo["audio"][i]["title"]
                )

                spellcheck_text = None
                if found_codec:
                    # spellcheck title parts before codec
                    spellcheck_text = " ".join(title_parts)
                else:
                    # spellcheck entire audio title
                    spellcheck_text = title
                if spellcheck_text:
                    # map punctuation to space
                    translator = str.maketrans(
                        string.punctuation, " " * len(string.punctuation)
                    )
                    spellcheck_text = spellcheck_text.translate(translator)

                    # ignore names
                    ignore_list = extract_names(spellcheck_text)
                    ignore_list = [a for b in ignore_list for a in b.split()]

                    # tokenize
                    tokens = nltk.word_tokenize(spellcheck_text)
                    tokens = [t for t in tokens if t not in ignore_list]

                    misspelled_words = list()
                    for t in tokens:
                        if not self.hobj.spell(t):
                            # t is misspelled
                            misspelled_words.append(t)

                    misspelled_words = set(misspelled_words)
                    misspelled_words = [
                        word
                        for word in misspelled_words
                        if word.lower() not in MISSPELLED_IGNORE_LIST
                    ]
                    if len(misspelled_words) > 0:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + " Misspelled: `"
                            + ", ".join(misspelled_words)
                            + "`",
                        )

        return reply

    def print_text_tracks(self):
        reply = "> **Text Tracks**\n"
        if len(self.mediainfo["text"]) > 0:
            reply += "```"
            for i, _ in enumerate(self.mediainfo["text"]):
                reply += self._section_id("text", i) + ":"
                if "default" in self.mediainfo["text"][i]:
                    reply += " default:" + self.mediainfo["text"][i]["default"]
                if "forced" in self.mediainfo["text"][i]:
                    reply += " forced:" + self.mediainfo["text"][i]["forced"]
                if "language" in self.mediainfo["text"][i]:
                    reply += " language:" + self.mediainfo["text"][i]["language"]
                if "title" in self.mediainfo["text"][i]:
                    reply += " title: " + self.mediainfo["text"][i]["title"]
                reply += "\n"
            reply += "```"
        else:
            reply += self.reporter.print_report("info", "No text tracks")
        return reply

    def check_text_order(self):
        reply = ""

        if len(self.mediainfo["text"]) == 0:
            return reply

        language_number = 1  # Used to keep track of first actual sub.
        forced_checked, commentary_checked = False, False
        forced_track_eng_first = False
        prev_track_language, prev_track_name = "", ""
        subs_in_order = True

        for i, _ in enumerate(self.mediainfo["text"]):
            forced_track, commentary_track = False, False
            track_language, track_name = "", ""

            if "language" in self.mediainfo["text"][i]:
                track_language = self.mediainfo["text"][i]["language"].lower()
            else:
                # Error printed elsewhere.
                subs_in_order = False
            if "forced" in self.mediainfo["text"][i]:
                forced_track = self.mediainfo["text"][i]["forced"].lower() == "yes"
            if "title" in self.mediainfo["text"][i]:
                track_name = self.mediainfo["text"][i]["title"]
                commentary_track = self._is_commentary_track(track_name)

            if i == 0 and forced_track:
                forced_track_eng_first = track_language == "english"
            elif forced_track and track_language == "english":
                subs_in_order = False
                reply += self.reporter.print_report(
                    "error",
                    "Text {} is a forced English track, it must be first".format(
                        self._section_id("text", i)
                    ),
                )
            elif not forced_checked:
                forced_checked = True
                track_name, track_language = "", ""
            elif commentary_track:
                commentary_checked = True
            elif commentary_checked:
                subs_in_order = False
                reply += self.reporter.print_report(
                    "error",
                    "Text {} came after the commentary sub(s)".format(
                        self._section_id("text", i)
                    ),
                )
            elif track_language == prev_track_language:
                if prev_track_name != "" and track_name < prev_track_name:
                    reply += self.reporter.print_report(
                        "warning",
                        "Text {} might need to come after Text {}, alphabetical within language".format(
                            self._section_id("Text", i - 1), self._section_id("Text", i)
                        ),
                    )
            elif language_number > 1 and track_language < prev_track_language:
                subs_in_order = False
                prev_track_language = ""
                reply += self.reporter.print_report(
                    "error",
                    "Text {} should come after Text {}, language order".format(
                        self._section_id("text", i - 1), self._section_id("text", i)
                    ),
                )
            elif language_number == 1 and track_language != "english":
                language_number += 1
            prev_track_language = track_language
            prev_track_name = track_name

        if subs_in_order:
            reply += self.reporter.print_report("correct", "Subtitles are in order")
        return reply

    def check_text_default_flag(self):
        # english subs for foreign films should be default=yes
        reply = ""

        if len(self.mediainfo["text"]) > 0:
            first_audio_language, has_english_subs, english_subs_default_yes = (
                False,
                False,
                False,
            )

            if has(self.mediainfo, "audio.0.language"):
                first_audio_language = self.mediainfo["audio"][0]["language"].lower()

            if first_audio_language != "english":
                # text tracks with language and default keys
                text_with_properties = [
                    item
                    for item in self.mediainfo["text"]
                    if ("language" in item and "default" in item)
                ]
                for item in text_with_properties:
                    if item["language"].lower() == "english":
                        has_english_subs = True
                    if item["default"].lower() == "yes":
                        english_subs_default_yes = True
                    if has_english_subs and english_subs_default_yes:
                        break

                if has_english_subs:
                    # foreign audio and has english subs. english subs should be default=yes
                    if english_subs_default_yes:
                        reply += self.reporter.print_report(
                            "correct",
                            "Foreign film, one of the English subtitles are `default=yes`",
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Foreign film, one of the English subtitles should be `default=yes`",
                        )

        return reply

    def print_chapters(self):
        reply = ""
        if len(self.mediainfo["menu"]) > 0:
            for i, menu in enumerate(self.mediainfo["menu"]):
                reply += f"> **Chapters {i + 1}**\n"
                numbered_chapters = True
                for ch in menu:
                    for title in ch["titles"]:
                        if not re.search(
                            r"^chapter\s\d+", title["title"], re.IGNORECASE
                        ):
                            numbered_chapters = False

                if not numbered_chapters:
                    reply += "```"
                    for ch in menu:
                        if ch["time"]:
                            reply += ch["time"] + " :"
                        for title in ch["titles"]:
                            if title["language"]:
                                reply += " lang: " + title["language"]
                            if title["title"]:
                                reply += " title: " + title["title"]
                        reply += "\n"
                    reply += "```"
                else:
                    reply += self.reporter.print_report("info", "Chapters are numbered")
                if len(menu[0]["languages"]) > 0:
                    reply += (
                        "Chapter languages: `" + ", ".join(menu[0]["languages"]) + "`\n"
                    )
        else:
            reply += self.reporter.print_report("info", "No chapters")
        return reply

    def chapter_language(self):
        reply = ""

        if "menu" in self.mediainfo and len(self.mediainfo["menu"]) > 0:
            if len(self.mediainfo["menu"]) >= 1:
                for i, chapters in enumerate(self.mediainfo["menu"]):
                    if len(chapters) >= 1:
                        # chapter numbers that have an invalid language
                        invalid_ch_lang_nums = list()
                        # chapters = list of chapters
                        # [{'time': '...', 'titles': [{'language': '...', 'title': '...'}, ...], 'languages': ['...', '...']}]
                        # {'time': '...', 'titles': [{'language': '...', 'title': '...'}, ...], 'languages': ['...', '...']}
                        ch_0 = chapters[0]
                        # concatenate all chapter titles into phrases
                        # ch_0["languages"] = ['...', '...']
                        # chapter_phrases = {'de': '...', 'en': '...'}
                        chapter_phrases = {k: "" for k in ch_0["languages"]}
                        # list of detected languages with chapter languages as keys
                        # chapter_langs = {'de': [...], 'en': [...]}
                        chapter_langs = {k: list() for k in ch_0["languages"]}

                        for ch in chapters:
                            for j, lang in enumerate(ch["languages"]):
                                if lang:
                                    try:
                                        ch_lang = iso639_languages.get(part1=lang)
                                        # store chapter language
                                        chapter_langs[lang].append(ch_lang)
                                    except KeyError:
                                        # store invalid chapter number
                                        invalid_ch_lang_nums.append(str(j + 1))
                                else:
                                    # store invalid chapter number
                                    invalid_ch_lang_nums.append(str(j + 1))

                            for title in ch["titles"]:
                                # store as key "NA" if there is no chapter language set
                                if title["language"] is None:
                                    title["language"] = "NA"
                                if title["language"] not in chapter_phrases:
                                    chapter_phrases[title["language"]] = ""
                                chapter_phrases[title["language"]] += (
                                    title["title"] + "\n"
                                )

                        if len(invalid_ch_lang_nums) > 0:
                            if len(invalid_ch_lang_nums) == len(chapters):
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: All chapters do not have a language set",
                                )
                            elif len(invalid_ch_lang_nums) > 0:
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: The following chapters do not have a language set: `"
                                    + ", ".join(invalid_ch_lang_nums)
                                    + "`",
                                )
                            else:
                                reply += self.reporter.print_report(
                                    "correct",
                                    f"Chapters {i + 1}: All chapters have a language set",
                                )

                        for k, chapter_phrase in chapter_phrases.items():
                            if k == "NA":
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: No chapter language set",
                                )
                                continue
                            if chapter_phrase:
                                chapter_langs[k] = list(set(chapter_langs[k]))
                                try:
                                    detected_lang = langdetect_detect(chapter_phrase)
                                    ch_detected_lang = iso639_languages.get(
                                        part1=detected_lang
                                    )
                                    if ch_detected_lang in chapter_langs[k]:
                                        reply += self.reporter.print_report(
                                            "correct",
                                            f"Chapters {i + 1}: Language matches detected language: `"
                                            + ch_detected_lang.name
                                            + "`",
                                        )
                                    else:
                                        chapter_langs_names = ", ".join(
                                            list(
                                                set(
                                                    [
                                                        detected_lang.name
                                                        for detected_lang in chapter_langs[
                                                            k
                                                        ]
                                                    ]
                                                )
                                            )
                                        )
                                        if chapter_langs_names:
                                            reply += self.reporter.print_report(
                                                "error",
                                                f"Chapters {i + 1}: Languages: `"
                                                + chapter_langs_names
                                                + "` do not match detected language: `"
                                                + ch_detected_lang.name
                                                + "`",
                                            )
                                        else:
                                            reply += self.reporter.print_report(
                                                "error",
                                                f"Chapters {i + 1}: No chapter languages. Detected language: `"
                                                + ch_detected_lang.name
                                                + "`",
                                            )
                                except KeyError:
                                    reply += self.reporter.print_report(
                                        "warning", "Could not detect chapters language"
                                    )
            else:
                reply += self.reporter.print_report(
                    "error", "Must have at least 1 chapter menu"
                )

        return reply

    def chapter_padding(self):
        reply, padded_correctly = "", True

        if "menu" in self.mediainfo and len(self.mediainfo["menu"]) > 0:
            if len(self.mediainfo["menu"]) >= 1:
                for i, menu in enumerate(self.mediainfo["menu"]):
                    padded_correctly = True
                    num_chapters = len(menu)
                    for ch in menu:
                        for title in ch["titles"]:
                            if re.search(
                                r"^chapter\s\d+", title["title"], re.IGNORECASE
                            ):
                                # numbered chapter
                                ch_num = "".join(re.findall(r"[\d]+", title["title"]))
                                if ch_num != ch_num.zfill(len(str(num_chapters))):
                                    padded_correctly = False
                                    break
                    if padded_correctly:
                        reply += self.reporter.print_report(
                            "correct", f"Chapters {i + 1}: Properly padded"
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error", f"Chapters {i + 1}: Incorrect padding"
                        )

        return reply

    def has_chapers(self):
        reply, should_have_chapters = "", False
        for log in self.eac3to:
            for l in log:
                if "chapters" in l:
                    should_have_chapters = True
        if should_have_chapters:
            if len(self.mediainfo["menu"]) > 0:
                reply += self.reporter.print_report(
                    "correct", "Has chapters (from eac3to log)"
                )
            else:
                reply += self.reporter.print_report(
                    "error", "Should have chapters (from eac3to log)"
                )
        return reply
