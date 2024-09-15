#VERSION: 1.00
# AUTHORS: Qwerty <qwerty@qwerty.xyz>
# This plugin is useful when you are configuring a VPN and need to verify that it works!

from html.parser import HTMLParser
from helpers import retrieve_url
from novaprinter import prettyPrinter

class whats_my_ip(object):

	url = 'https://qwerty.xyz/'
	name = "What's my IP?"
	supported_categories = {'all': '0'}

	service_url = 'http://ipip.cz/'

	def search(self, what, cat='all'):
		response = retrieve_url(self.service_url)

		parser = IPParser()
		parser.feed(response)

		prettyPrinter({
			'link': self.service_url,
			'name': f"IP Address: {parser.ip_address}",
      # Says "Unknown" and can be sorted to the top by smallest size
			'size': -1,
			# Sort the result to the top by Seeds
			'seeds': 1000001,
			'leech': 1337,
			'engine_url': self.service_url,
			'desc_link': self.service_url,
			'pub_date': -1
		})

		prettyPrinter({
			'link': self.service_url,
			'name': f"Hostname: {parser.hostname}",
      # Says "Unknown" and can be sorted to the top by smallest size
			'size': -1,
			# Sort the result to the top by Seeds
			'seeds': 1000000,
			'leech': 1337,
			'engine_url': self.service_url,
			'desc_link': self.service_url,
			'pub_date': -1
		})

class IPParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.in_ip_div = False
		self.ip_address = ""
		self.hostname = ""
		self.data_buffer = []

	def handle_starttag(self, tag, attrs):
		if tag == 'div':
			for attr in attrs:
				if attr[0] == 'class' and attr[1] == 'ip':
					self.in_ip_div = True

	def handle_endtag(self, tag):
		if tag == 'div' and self.in_ip_div:
			self.in_ip_div = False
			data_str = ''.join(self.data_buffer)
			self.data_buffer = []
			if 'Moje IP adresa:' in data_str:
				parts = data_str.split('Moje IP adresa:')
				ip_part = parts[1].split('Hostname:')
				self.ip_address = ip_part[0].strip()
				self.hostname = ip_part[1].strip()

	def handle_data(self, data):
		if self.in_ip_div:
			self.data_buffer.append(data)
