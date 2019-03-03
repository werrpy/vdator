from enum import Enum

class MediaInfoParser():

	class MediaInfoSection(Enum):
		GENERAL = 1
		VIDEO = 2
		AUDIO = 3
		TEXT = 4

	def format_key(self, key):
		# format keys into abc_def_ghi
		return key.strip()\
			.replace(" ", "_")\
			.replace("/", "_")\
			.replace("(", "")\
			.replace(")", "")\
			.replace("*", "_")\
			.replace(",", "")\
			.lower()

	def parse(self, text):
		mediainfo = dict()
		mediainfo['general'] = dict()
		mediainfo['video'] = dict()
		mediainfo['audio'] = dict()
		mediainfo['text'] = dict()

		# starts at 0 on first loop
		index_general = index_video = index_audio = index_text = -1

		sect = None

		for l in text:
			# skip blank lines
			if not l.strip():
				continue
			# determine current section of mediainfo
			if l.strip().split()[0].strip().lower() == "general":
				index_general += 1
				sect = self.MediaInfoSection.GENERAL
				mediainfo['general'][index_general] = dict()

			if l.strip().split()[0].strip().lower() == "video":
				index_video += 1
				sect = self.MediaInfoSection.VIDEO
				mediainfo['video'][index_video] = dict()

			if l.strip().split()[0].strip().lower() == "audio":
				index_audio += 1
				sect = self.MediaInfoSection.AUDIO
				mediainfo['audio'][index_audio] = dict()

			if l.strip().split()[0].strip().lower() == "text":
				index_text += 1
				sect = self.MediaInfoSection.TEXT
				mediainfo['text'][index_text] = dict()

			if sect == self.MediaInfoSection.GENERAL:
				curr = l.split(':', 1)
				if len(curr) < 2:
					continue
				curr[0] = self.format_key(curr[0])
				curr[1] = curr[1].strip()
				mediainfo['general'][index_general][curr[0]] = curr[1]
			elif sect == self.MediaInfoSection.VIDEO:
				curr = l.split(':', 1)
				if len(curr) < 2:
					continue
				curr[0] = self.format_key(curr[0])
				curr[1] = curr[1].strip()
				mediainfo['video'][index_video][curr[0]] = curr[1]
			elif sect == self.MediaInfoSection.AUDIO:
				curr = l.split(':', 1)
				if len(curr) < 2:
					continue
				curr[0] = self.format_key(curr[0])
				curr[1] = curr[1].strip()
				mediainfo['audio'][index_audio][curr[0]] = curr[1]
			elif sect == self.MediaInfoSection.TEXT:
				curr = l.split(':', 1)
				if len(curr) < 2:
					continue
				curr[0] = self.format_key(curr[0])
				curr[1] = curr[1].strip()
				mediainfo['text'][index_text][curr[0]] = curr[1]

		return mediainfo