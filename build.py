import ConfigParser
import glob
import os
import os.path
import urllib2
import shutil
import csv
#from django.template import Context, Template
#from django.conf import settings

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


class WishlistConf:
    def __init__(self, conf_file, section_name):
        try:
            conf = ConfigParser.ConfigParser()
            conf.read(conf_file)

            self.sourceFile = conf.get(section_name, 'source_file')
            self.dataFile = conf.get(section_name, 'data_file')
            self.tmpPath = conf.get(section_name, 'tmp_path')
            self.imagePath = conf.get(section_name, 'image_path')
            self.identifyCmd = conf.get(section_name, 'identify_cmd')
            self.mogrifyCmd = conf.get(section_name, 'mogrify_cmd')
            self.csvDelimiter = conf.get(section_name, 'csv_delimiter')
            self.maxImageWidth = int(conf.get(section_name, 'max_image_width'))
            self.maxImageHeight = int(conf.get(section_name, 'max_image_height'))

        except:
            print "Error reading configuration file '%s' (section: '%s')" % (conf_file, section_name)
            raise

class Logger:
    def __init__(self, file_name, show_messages = False):
        self.file_name = file_name
        self._show = show_messages

    def write(self, message):
        if self._show: print(message)

class Wishlist:
    def __init__(self, conf, log):
        self._conf = conf
        self._log = log

    def generate(self):
        self._data = self.merge_data(self.read_source(), self.load_data())
        self.download_new_images()
        self.process_images()
        self.save_data()
        return

    def read_source(self):
        '''Returns a collection of { url, image_url, description } tuples'''
        if not os.path.exists(self._conf.sourceFile):
            print('Source file does not exists: ' + self._conf.sourceFile)
            return []

        try:
            result = []
            for item in open(self._conf.sourceFile, 'r').read().strip().split('\n\n'):
                parts = item.split('\n')
                if len(parts) != 3: continue
                description, url, image_url = parts
                result.append({ 'url':url.strip(), 'image_url':image_url.strip(), 'desc':description.strip() })
            return result

        except Exception as ex:
            print('Error reading source file: ' + str(ex))
            return []

    def save_data(self):
        '''Save wishlist records to CSV file'''
        def to_csv_row(record):
            try:
                return [record['url'], record['image_url'], record['image_file'],
                        record['width'], record['height'], record['desc']]
            except:
                return None

        try:
            writer = csv.writer(open(self._conf.dataFile, 'wb'), delimiter = self._conf.csvDelimiter, quoting = csv.QUOTE_MINIMAL)
            for row in [to_csv_row(record) for record in self._data]:
                if row is not None: writer.writerow(row)

        except Exception as ex:
            print('Error saving data to %s: %s' % (self._conf.dataFile, str(ex)))

    def load_data(self):
        '''Load wishlist records from CSV file'''
        def to_dict(row):
            try:
                return { 'url':row[0], 'image_url':row[1], 'image_file':row[2],
                         'width':int(row[3]), 'height':int(row[4]), 'desc':row[5] }
            except:
                return None

        try:
            result = []
            reader = csv.reader(open(self._conf.dataFile, 'rb'), delimiter = self._conf.csvDelimiter)
            for record in [to_dict(row) for row in reader]:
                if record is not None: result.append(record)
            return result

        except Exception as ex:
            print('Error loading data from %s: %s' % (self._conf.dataFile, str(ex)))

    def merge_data(self, new_data, cached_data):
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
                    existing.update({'image_file':'', 'width':0, 'height':0})
                existing.update(item)
                result.append(existing)
            else:
                item.update({'image_file':'', 'width':0, 'height':0})
                result.append(item)
        return result

    def download_new_images(self):
        '''Download images for wishlist records and returns a collection of new image IDs'''

        def download(url, file_name):
            '''Downloads and save a file from URL'''
            r = urllib2.urlopen(urllib2.Request(url))
            ext = r.headers.subtype.lower()
            if ext not in ['jpeg', 'png', 'gif']: return None
            save_as = '%s.%s' % (file_name, ext)

            try:
                with open(save_as, 'wb') as f: shutil.copyfileobj(r, f)
            finally:
                r.close()

            return save_as

        counter = 1
        result = []
        for item in self._data:
            if len(item['image_file']): continue
            while True:
                new_file = os.path.join(self._conf.imagePath, str(counter))
                if len(glob.glob(new_file + '.*')) < 1 and not os.path.exists(new_file): break;
                counter += 1
            print 'Downloading %s (%d)' % (item['image_url'], counter)
            new_image = download(item['image_url'], os.path.join(self._conf.imagePath, str(counter)))
            if new_image:
                result.append(new_image)
                item['image_file'] = os.path.basename(new_image)
            else:
                print('Error downloading file')

        return result

    def process_images(self):
        '''Scales new images and retrieves image sizes'''

        def set_image_size(image_file, width, height):
            for item in self._data:
                if item['image_file'] == image_file:
                    item['width'] = width
                    item['height'] = height
                    break

        try:
            image_files = [self._conf.imagePath + item['image_file'] for item in self._data
                if (item['width'] == 0 or item['height'] == 0) and item['image_file']]
            self.execute(self._conf.mogrifyCmd % (self._conf.maxImageWidth,
                self._conf.maxImageHeight, os.path.join(self._conf.imagePath, '*')))

            lines = self.execute(self._conf.identifyCmd % ' '.join(image_files), True)
            for line in lines:
                parts = line.strip().split(',')
                if len(parts) != 3: continue
                set_image_size(parts[0], int(parts[1]), int(parts[2]))

        except Exception as ex:
            print('Error getting image resolution: ' + str(ex))
            return []

    def execute(self, command, get_output = False):
        print 'Executing command: ' + command
        h = os.popen(command)
        if get_output: return h.readlines()

#    def get_image_size(self, image_file):
#        try:
#            output = os.popen(self._conf.identifyCmd % image_file).readlines()
#            parts = output[0].strip().split(',')
#            if len(parts) != 3: raise Exception('Identify output: "%s"' % output)
#            width, height = parts[1], parts[2]
#            return int(width), int(height)
#
#        except Exception as ex:
#            print('Error getting image size for "%s": %s' % (image_file, str(ex)))
#            return 0, 0



Wishlist(WishlistConf('build.conf', 'wishlist-builder'), Logger('wishlist.log')).generate()




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

