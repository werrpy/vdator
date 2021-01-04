import re


class BDInfoParser:
    """
    Parse BDInfo
    """

    def format_track_name(self, name):
        """
        Format track name

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        str formatted track name
        """
        # remove multiple and trailing spaces
        name = " ".join(name.split()).strip()
        return name

    def format_video_track_name(self, name):
        """
        Format video track name

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        str formatted video track name
        """
        # remove 3d
        name = name.replace(" / Left Eye", "")
        name = name.replace(" / Right Eye", "")

        name = self.format_track_name(name)

        # force decimal instead of comma in fps
        name2 = name.split("/")
        if len(name2) >= 4:
            name2[3] = name2[3].replace(",", ".")
        name = "/".join(name2)

        return name

    def format_audio_track_name(self, name):
        """
        Format track name

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        str formatted audio track name
        """
        # remove dialog normalization
        if "DN" in name.upper() and " / " in name:
            name = name.rpartition(" / ")[0]

        # remove (DTS Core:...)
        name = re.sub(r"\(DTS Core:.*\)", "", name).strip()

        name = self.format_track_name(name)

        return name

    def format_audio_compatibility_track(self, audio_track):
        """
        Format audio compatibility track

        Parameters
        ----------
        audio_track : dict
            audio track
            dict{'name':'...', 'language':'...'}

        Returns
        -------
        audio track, compatibility track
        [dict{'name':'...', 'language':'...'}, dict{'name':'...', 'language':'...'}]
        """
        audio_parts = re.split(
            r"\(ac3 embedded:", audio_track["name"], flags=re.IGNORECASE
        )
        audio_track["name"] = audio_parts[0]

        compat_track = {
            "name": self.format_track_name(
                "Compatibility Track / Dolby Digital Audio / "
                + audio_parts[1].strip().rstrip(")")
            ),
            "language": audio_track["language"],
        }
        return audio_track, compat_track

    def format_audio_track(self, name):
        """
        Split audio track with name and language

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        dict{'name':'...', 'language':'...'}
        """
        track = {"name": None, "language": None}
        name = name.strip()
        if " / " in name:
            name_parts = name.split(" / ", 1)
            track["name"] = self.format_audio_track_name(name_parts[1])
            track["language"] = name_parts[0]
        return track

    def format_subtitle_track(self, name):
        """
        Format subtitle track with language and bitrate

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        dict{'language':'...', 'bitrate':'...'}
        """
        track = {"language": None, "bitrate": None}
        name = name.strip()
        if " / " in name:
            name_parts = name.split(" / ", 1)
            track["language"] = name_parts[0].strip()
            track["bitrate"] = name_parts[1].strip()
        return track

    def playlist_report_format_video_track_name(self, name):
        """
        Format playlist report video track name

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        str formatted track name
        """
        try:
            parts = name.split()
            kbps_i = parts.index("kbps")
            before = " ".join(parts[: kbps_i - 1]).strip()
            after = " ".join(parts[kbps_i + 1 :]).strip()
            track_name = (
                before + " / " + parts[kbps_i - 1] + " " + parts[kbps_i] + " / " + after
            )
            track_name = self.format_video_track_name(track_name)
            return track_name
        except ValueError:
            return False

    def playlist_report_format_audio_track(self, name):
        """
        Format playlist report audio track

        Parameters
        ----------
        name : str
            track name

        Returns
        -------
        dict{'name':'...', 'language':'...'}
        """
        track = {"name": None, "language": None}
        try:
            name = name.strip()
            name_parts = name.split(" / ")
            name_parts0 = name_parts[0].strip().split()
            name = (
                " ".join(name_parts0[:-4])
                + " / "
                + name_parts0[-1]
                + " / "
                + " / ".join(name_parts[1:]).strip()
            )
            track["name"] = self.format_track_name(name)
            track["language"] = name_parts0[3]
            return track
        except ValueError:
            return False
