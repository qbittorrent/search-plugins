# VERSION: 2.3
# AUTHORS: Scare! (https://Scare.ca/dl/qBittorrent/)

# modified from v1.0 by LightDestory (https://github.com/LightDestory)

import re
import urllib.parse
from helpers import retrieve_url
from novaprinter import prettyPrinter

class torrentdownload(object):
	url='https://www.torrentdownload.info'
	name='TorrentDownload w. categories'
	query='{self.url}/search?q={what}&p={page}'
	pages=10											# engine max: 20 pages

# Torrent Download doesn't let you search within categories, but it does append tags to the torrent names, which is what this plugin uses for categories. Here are the ones I've seen:

# Adult
# Adult / Porn > Animation/Hentai
# Adult / Porn > DVD
# Adult / Porn > Pictures
# Adult / Porn > Video
# Anime
# Anime > Anime - Other
# Anime > English-translated
# Applications
# Applications > Android
# Audio Books
# Books > Ebooks
# Games
# Misc
# Movies
# Movies > Action
# Music
# Music > R&B
# Other
# Other Pictures
# Other > Wallpapers
# Other XXX
# Software PC
# Television
# TV > Other
# TV > WWE - Wrestling
# TV shows
# Video Mobile
# Windows - Other
# XXX > Pictures
# XXX > Video

	supported_categories={
		'all':		'',
		'anime':	'Anime|Animation|Hentai',
					# Adult / Porn > Animation/Hentai
					# Anime
					# Anime > Anime - Other
					# Anime > English-translated
		'books':	'book',
					# Audio Books
					# Books > Ebooks
		'games':	'game',
					# Games
		'movies':	'movie',
					# Movies
					# Movies > Action
		'music':	'music',
					# Music
					# Music > R&B
		'pictures':	'Picture|Wallpaper',
					# Adult / Porn > Pictures
					# Other Pictures
					# Other > Wallpapers
					# XXX > Pictures
# You can uncomment the next line if you have added 'porn' to the CATEGORIES list in (for Ms-Windows) {user}\AppData\Local\qBittorrent\nova3\nova2.py which is 1 directory up from the "engines" directory where this file will be installed. When searching, select the blank line in the pull-down-list that starts with "All categories". Assuming you want to be able to search within only porn, of course. ;)
#		'porn':		'Adult|Porn|XXX',
					# Adult
					# Adult / Porn > Animation/Hentai
					# Adult / Porn > DVD
					# Adult / Porn > Pictures
					# Adult / Porn > Video
					# Other XXX
					# XXX > Pictures
					# XXX > Video
		'software':	'Application|Software|Windows|Linux|Android|PC',	# but not Games
					# Applications
					# Applications > Android
					# Software PC
					# Windows - Other
		'tv':		'TV|Television'
					# Television
					# TV > Other
					# TV > WWE - Wrestling
					# TV shows
	}

	row=r'<tr(?:\s[^>]*|)>\s*<td(?:\s[^>]*|)\sclass="tdleft"[^>]*>\s*<div(?:\s[^>]*|)\sclass="tt-name"[^>]*>\s*<a(?:\s[^>]*|)\shref="(?P<link>[^"]+)"[^>]*>\s*(?P<name>.+?)\s*</a>\s*<span(?:\s[^>]*|)\sclass="smallish"[^>]*>(?P<tags>[^<>]*(?:{cat})[^<>]*)</span>\s*</div>\s*.*?<td(?:\s[^>]*|)\sclass="tdnormal"[^>]*>\s*(?P<size>[\d,.]+\s*(?:TB|GB|MB|KB))\s*</td>\s*<td(?:\s[^>]*|)\sclass="tdseed"[^>]*>\s*(?P<seeds>[\d,]+)\s*</td>\s*<td(?:\s[^>]*|)\sclass="tdleech"[^>]*>\s*(?P<leech>[\d,]+)\s*</td>\s*</tr>'

	rowFlags=re.I|re.S

	def search(self,what,cat='all'):
		what=what.replace('%20','+')
		category=self.supported_categories[cat]
		r=re.compile(self.row.format(cat=category),self.rowFlags)
		for page in range(1,self.pages):
			html=retrieve_url(self.query.format(self=self,what=what,page=page))
			for x in r.finditer(html):
				linkRaw=self.url+x.group('link')
				prettyPrinter({
					'link':			urllib.parse.quote(linkRaw, safe=':/'),
					'name':			re.sub('<[^>]*>','',x.group('name')+x.group('tags')),
					'size':			x.group('size').replace(',',''),
					'seeds':		x.group('seeds').replace(',',''),
					'leech':		x.group('leech').replace(',',''),
					'engine_url':	self.url,
					'desc_link':	linkRaw
				})

	def download_torrent(self,info):
		html=retrieve_url(urllib.parse.unquote(info))
		m=re.search('"(magnet:.*?)"',html,re.I)
		if m and m.groups():
			print('{0} {1}'.format(m.groups(1),info))
		else:
			raise Exception('Error in download_torrent({info})'.format(info=info))
