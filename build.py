from genericpath import exists
import glob
import os
import os.path
import urllib2
import shutil
import csv
#from django.template import Context, Template
#from django.conf import settings
from urlparse import urlsplit
import urlparse

source_file = 'wishlist.txt'
data_file = 'wishlist-data.txt'
tmp_path = 'tmp/'
image_path = 'images/'
identify_cmd = 'identify -format %%f,%%W,%%H\\n %s'
mogrify_cmd = 'mogrify -define filter:blur=0.75 -filter cubic -resize %dx%d^> %s'
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

def read_source_file(source_file):
    '''Returns a collection of { url, image_url, description } tuples'''
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
    '''Returns a collection of [width, height] for a set of image files'''
    try:
        result = []
        for line in os.popen(identify_cmd % ' '.join(images_list)).readlines():
            parts = line.split(',')
            if len(parts) != 3: continue
            file_name, width, height = parts
            result.append([file_name.strip(), int(width.strip()), int(height.strip())])
        return result

    except Exception as ex:
        print('Error getting image resolution: ' + str(ex))
        return []

def download(url, fileName = None):
    '''Downloads and save a file from URL'''
    def getFileName(url, openUrl):
        if 'Content-Disposition' in openUrl.info():
            cd = dict(map(
                lambda x: x.strip().split('=') if '=' in x else (x.strip(),''),
                openUrl.info().split(';')))
            if 'filename' in cd:
                filename = cd['filename'].strip("\"'")
                if filename: return filename
        return os.path.basename(urlsplit(openUrl.url)[2])

    r = urllib2.urlopen(urllib2.Request(url))
    try:
        fileName = fileName or getFileName(url, r)
        with open(fileName, 'wb') as f:
            shutil.copyfileobj(r, f)
    finally:
        r.close()

def save_data(csv_file, data):
    '''Save wishlist records to CSV file'''
    def to_csv_row(record):
        try:
            return [record['url'], record['image_url'], record['image_id'],
                    record['width'], record['height'], record['desc']]
        except:
            return None

    try:
        writer = csv.writer(open(csv_file, 'wb'), delimiter = csv_delimiter, quoting = csv.QUOTE_MINIMAL)
        for row in [to_csv_row(record) for record in data]:
            if row is not None: writer.writerow(row)

    except Exception as ex:
        print('Error saving data to %s: %s' % (csv_file, str(ex)))

def load_data(csv_file):
    '''Load wishlist records from CSV file'''
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
            if record is not None: result.append(record)
        return result

    except Exception as ex:
        print('Error loading data from %s: %s' % (csv_file, str(ex)))

def merge_data(new_data, cached_data):
    '''Merge new data from source file and cached data'''
    def get_existing(cached_data):
        try:
            if cached_data is None or len(cached_data) == 0: return None
            return (r for r in cached_data if r['url'] == item['url']).next()
        except:
            return None

    result = []
    for item in new_data:
        existing = get_existing(cached_data)
        if existing is not None:
            if existing['image_url'] != item['image_url']:
                existing.update({'image_id':0, 'width':0, 'height':0})
            existing.update(item)
            result.append(existing)
        else:
            item.update({'image_id':0, 'width':0, 'height':0})
            result.append(item)
    return result

def download_images(data):
    '''Download images for wishlist records and returns { image_url => [image_id, file_name] } dict'''
    counter = 1
    result = []
    for item in data:
        if int(item['image_id']): continue
        while True:
            new_file = os.path.join(image_path, str(counter))
            if len(glob.glob(new_file + '.*')) < 1 and not os.path.exists(new_file): break;
            counter += 1
        ext = os.path.splitext(urlparse.urlparse(item['image_url']).path)[1].lower()
        save_as = os.path.join(image_path, str(counter) + ext)
        print '%s -> %s' % (item['image_url'], save_as)
        download(item['image_url'], save_as)
        item['image_id'] = counter
        result.append(save_as)
    return result

def scale_images(dir_path, max_width, max_height):
    os.popen(mogrify_cmd % (max_width, max_height, os.path.join(image_path, '*')))
    return

data = merge_data(read_source_file(source_file), load_data(data_file))
new_images = download_images(data)
scale_images(new_images, 300, 300)


# save_data('merged-data.txt', data)

#igGen = FileIdGenerator(image_path)
#print igGen.dirPath

#id_gen = new image_id_generator()
#print id_gen.new_image_id()


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

