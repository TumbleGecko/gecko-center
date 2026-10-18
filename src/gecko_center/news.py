"""openSUSE's own news and the newest Tumbleweed snapshot, read from their public addresses."""

import html
import re
import xml.etree.ElementTree as ElementTree
from email.utils import parsedate_to_datetime

NEWS_FEED = "https://news.opensuse.org/feed.xml"
# The media file names the snapshot the download servers hand out now, such as "openSUSE 20261012-1"
NEWEST_SNAPSHOT = "https://download.opensuse.org/tumbleweed/repo/oss/media.1/products"
NEWS_ITEMS = 20
SUMMARY_LENGTH = 400


def _plain(text):
	return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _date(text):
	try:
		return parsedate_to_datetime(text).date().isoformat()
	except (TypeError, ValueError):
		return ""


def items_from_feed(text):
	"""Each story with its title, date, a short summary and its link, newest first as the feed has them."""
	try:
		channel = ElementTree.fromstring(text)
	except ElementTree.ParseError:
		return []
	stories = []
	for item in channel.iter("item"):
		summary = _plain(item.findtext("description", ""))
		stories.append({
			"title": _plain(item.findtext("title", "")),
			"date": _date(item.findtext("pubDate", "")),
			"summary": summary[:SUMMARY_LENGTH],
			"link": item.findtext("link", ""),
			"tumbleweed": "tumbleweed" in (item.findtext("title", "") + summary).lower(),
		})
	return stories[:NEWS_ITEMS]


def snapshot_from_products(text):
	found = re.search(r"\b(\d{8})\b", text)
	return found.group(1) if found else ""
