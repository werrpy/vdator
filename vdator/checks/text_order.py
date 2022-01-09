from .check import *
from .mixins import IsCommentaryTrack, SectionId


class CheckTextOrder(Check, IsCommentaryTrack, SectionId):
    def __init__(self, reporter, mediainfo):
        super().__init__(
            reporter,
            mediainfo,
            "Error checking text track order",
        )

    # overriding abstract method
    def get_reply(self):
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
