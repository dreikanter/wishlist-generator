import os
import urllib2
import shutil
import csv
import pickle
from django.template import Context, Template
from django.conf import settings

source_file = 'wishlist.txt'
data_file = 'wishlist-data.txt'
tmp_path = 'tmp/'
image_path = 'images/'
identify_cmd = 'd:/bin/imagemagick/identify -format %%f,%%W,%%H\\n %s'

csv_delimiter = ';'

# read source file
# read cache if exists
# merge
# find new files
# download to tmp
# resize in tmp
# get a list of {name,size} for each processed picture
# drop unused images
# add new files to images
# clear tmp
# store new image IDs
# save data
# generate html

# Returns a collection of { url, image_url, description } tuples
def read_source_file(source_file):
	if not os.path.exists(source_file):
		print('Source file does not exists: ' + source_file)
		return []
	
	try:
		result = []
		for item in open(source_file, 'r').read().strip().split('\n\n'):
			parts = item.split('\n')
			if len(parts) != 3: continue
			description, url, image_url = parts
			result.append({ 'url':url.strip(), 
							'image_url':image_url.strip(), 
							'desc':description.strip() })
		return result
		
	except Exception as ex:
		print('Error reading source file: ' + str(ex))
		return []

def get_image_size(images_list):
	try:
		result = []
		for line in os.popen(identify_cmd % ' '.join(images_list)).readlines():
			parts = line.split(',')
			if len(parts) != 3: continue
			file_name, width, height = parts
			result.append([file_name.strip(), int(width.strip()), int(height.strip())])
		return result
	
	except Exception as ex:
		print('Error reading source file: ' + str(ex))
		return []

def download(url, fileName = None):
    def getFileName(url, openUrl):
        if 'Content-Disposition' in openUrl.info():
            cd = dict(map(
                lambda x: x.strip().split('=') if '=' in x else (x.strip(),''),
                openUrl.info().split(';')))
            if 'filename' in cd:
                filename = cd['filename'].strip("\"'")
                if filename: return filename
        return basename(urlsplit(openUrl.url)[2])

    r = urllib2.urlopen(urllib2.Request(url))
    try:
        fileName = fileName or getFileName(url, r)
        with open(fileName, 'wb') as f:
            shutil.copyfileobj(r, f)
    finally:
        r.close()

def save_data(csv_file, data):
	
	def to_csv_row(record):
		try:
			return [record['url'], record['image_url'], record['image_id'], 
					record['width'], record['height'], record['desc']]
		except:
			return None
		
	try:
		writer = csv.writer(open(csv_file, 'wb'), delimiter = csv_delimiter, quoting = csv.QUOTE_MINIMAL)
		for row in [to_csv_row(record) for record in data]:
			if row != None: writer.writerow(row)
		
	except Exception as ex:
		print('Error saving data to %s: %s' % (csv_file, str(ex)))

def load_data(csv_file):
	
	def to_dict(row):
		try:
			return { 'url':row[0], 'image_url':row[1], 'image_id':row[2], 
					 'width':row[3], 'height':row[4], 'desc':row[5] }
		except:
			return None
	
	try:
		result = []
		reader = csv.reader(open(csv_file, 'rb'), delimiter = csv_delimiter)
		for record in [to_dict(row) for row in reader]:
			if record != None: result.append(record)
		return result
		
	except Exception as ex:
		print('Error loading data from %s: %s' % (csv_file, str(ex)))

# Merge new data from source file and cached data
def merge_data(new_data, cached_data):
	
	def get_existing(cached_data):
		try:
			if cached_data == None or len(cached_data) == 0: return None
			return (r for r in cached_data if r['url'] == item['url']).next()
		except:
			return None
	
	result = []
	for item in new_data:
		existing = get_existing(cached_data)
		if existing != None:
			existing.update(item)
			result.append()
		else:
			item.update({'image_id':0, 'width':0, 'height':0})
			result.append(item)
	return result


data = read_source_file(source_file)
data = merge_data(data, [])
save_data(data_file, data)
save_data('wishlist-data2.txt', load_data(data_file))



#save_data(data_file, 1)

#i = 0
#for item in read_source_file(source_file):
#	i += 1
#	print download(item[2], tmp_path + str(i))
#
#print get_image_size([tmp_path + file_name for file_name in os.listdir(tmp_path)])


#	map_file = ''
#	
#	images = {}
#	
#	max_id = -1;
#	
#	def __init__(self, source_file):
#		self.map_file = image_map_file
#		if exists(self.map_file):
#			self.items = open(self.map_file, 'r').read().strip().split('\n')
#			for item in self.items:
#				parts = item.split(':', 2)
#				if len(parts) == 2:
#					id = int(parts[0])
#					self.images[id] = parts[1]
#					if id > self.max_id: self.max_id = id
#	
#	def get_id(self, url):
#		id = self.find_id(url)
#		if id >= 0:
#			return id
#		else:
#			self.images[++max_id] = url
#			return max_id
#		return
#		
#	def find_id(self, search_url):
#		for id, url in self.images:
#			if url == search_url: return id
#		return -1
#		
#
#
#w = Wishlist('wishlist.txt')


#settings.configure(DEBUG=True, TEMPLATE_DEBUG=True, TEMPLATE_DIRS=(''))

#data_file = 'wishlist.txt'
#template_file = 'template.html'

#f = open(data_file, 'r')
#items = f.read().split('\n\n')
#parsed_items = []
#for item in items:
#	parts = item.strip().split('\n')
#	if len(parts) == 3:
#		parsed_items.append({'title':parts[0], 'url':parts[1], 'image':parts[2]})

#f = open(template_file, 'r')
#t = Template(f.read())
#print(t.render(Context({'item_list':parsed_items})))

