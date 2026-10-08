# VERSION: 4.2
# AUTHORS: Scare! (https://Scare.ca/dl/qBittorrent/)

# added categories to v1.0 by LightDestory https://github.com/LightDestory

import urllib.parse
import json
import re
from helpers import retrieve_url,download_file
from novaprinter import prettyPrinter


class thepiratebay(object):
	url='https://thepiratebay.org'
	api='https://apibay.org'
	name='The Pirate Bay w. categories'

	# uncomment appropriate lines to include TPB category in qBittorrent search category
	# currently set to include only HD video for "movies" & "tv"
	supported_categories={
		'all':		[0],
		'anime':
		[
			207,	# Video > HD - Movies
			208,	# Video > HD - TV shows
			201,	# Video > Movies
			202,	# Video > Movies DVDR
			205,	# Video > TV shows
			206,	# Video > Handheld
			209,	# Video > 3D
			299,	# Video > Other
			501,	# Porn > Movies
			502,	# Porn > Movies DVDR
			505,	# Porn > HD - Movies
			599,	# Porn > Other			!!! comma after each number...
			699		# Other > Other			!!! ...except the last!
		],
		'books':
		[
#			102,	# Audio > Audio books
			601,	# Other > E-books
			602		# Other > Comics
		],
		'games':
		[
			400,	# Games
			504		# Porn > Games
		],
		'movies':
		[
#			201,	# Video > Movies
#			202,	# Video > Movies DVDR
#			209,	# Video > 3D
			207		# Video > HD - Movies
		],
		'music':
		[
#			203,	# Video > Music videos
			101,	# Audio > Music
			104		# Audio > FLAC
		],
		'pictures':
		[
			603,	# Other > Pictures
			604,	# Other > Covers
			503		# Porn > Pictures
		],
		'software':	# but not games
		[
			300		# Applications
		],
		'tv':
		[
#			205,	# Video > TV shows
			208		# Video > HD - TV shows
		]
	}

	torrent='{self.url}/description.php?id={id}'
	download='{self.api}/t.php?id={id}'
	magnet='magnet:?xt=urn:btih:{hash}&dn={name}&{trackers} {info}'
	query='{self.api}/q.php?q={what}&cat={category}'

	trackers=[
		'udp://tracker.coppersurfer.tk:6969/announce',
		'udp://tracker.openbittorrent.com:6969/announce',
		'udp://9.rarbg.to:2710/announce',
		'udp://9.rarbg.me:2780/announce',
		'udp://9.rarbg.to:2730/announce',
		'udp://tracker.opentrackr.org:1337',
		'http://p4p.arenabg.com:1337/announce',
		'udp://tracker.torrent.eu.org:451/announce',
		'udp://tracker.tiny-vps.com:6969/announce',
		'udp://open.stealth.si:80/announce']

	def download_torrent(self,info):
		torrent_id=urllib.parse.unquote(info).split('=')[-1]
		url=self.download.format(self=self,id=torrent_id)
		data=json.loads(retrieve_url(url))
		if data:
			name=urllib.parse.quote(data['name'],safe='')
			trs=urllib.parse.urlencode({'tr':self.trackers},True)
			print(self.magnet.format(hash		=data['info_hash'],
									 name		=name,
									 trackers	=trs,
									 info		=info))
		else:
			raise Exception('Error in "'+self.name+'" search plugin, download_torrent()')

	def search(self,what,cat='all'):
		x=[]
		for category in self.supported_categories[cat]:
			url=self.query.format(self=self,what=what,category=category)
			x+=json.loads(retrieve_url(url))
		self.parseJSON(x)

	def parseJSON(self,collection):
		for torrent in collection:
			info_hash=torrent.get('info_hash', '')
			if not re.fullmatch(r'[0-9a-f]{40}', info_hash, re.IGNORECASE) or info_hash == '0' * 40:
				continue
			torrent_id=self.torrent.format(self=self,id=torrent['id'])
			magnet='magnet:?xt=urn:btih:' + info_hash + '&' + urllib.parse.urlencode({'dn': torrent['name'], 'tr': self.trackers}, doseq=True)
			data={
				'link':			magnet,
				'name':			torrent['name'],
				'size':			torrent['size'],
				'seeds':		torrent['seeders'],
				'leech':		torrent['leechers'],
				'engine_url':	self.url,
				'desc_link':	torrent_id,
				'pub_date':	torrent.get('added', -1)
			}
			prettyPrinter(data)
