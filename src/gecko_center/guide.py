"""The guide to Linux and Tumbleweed, its topics and the words it explains, read from the language file."""

from . import paths

LANGUAGE_FILE = paths.LANG / "en.lang"
TOPIC_FIELDS = ("title", "summary", "body", "page", "action")


def read_language():
	"""Plain key=value lines in file order, with \\n standing for a line break."""
	values = {}
	for line in LANGUAGE_FILE.read_text(encoding="utf-8").splitlines():
		key, separator, value = line.partition("=")
		if separator and key.strip():
			values[key.strip()] = value.replace("\\n", "\n")
	return values


def read_guide():
	values = read_language()
	topic_ids = list(dict.fromkeys(key.split(".")[1] for key in values if key.startswith("guide.")))
	topics = [dict({"id": topic_id}, **{field: values.get(f"guide.{topic_id}.{field}", "") for field in TOPIC_FIELDS})
		for topic_id in topic_ids]
	words = [{"word": key[len("word."):], "meaning": value} for key, value in values.items() if key.startswith("word.")]
	return {"topics": topics, "words": words}
