import ConfigParser
from datetime import datetime
import glob
import os
import os.path
import sys
import urllib2
import shutil
import csv
from django.template import Context, Template
from django.conf import settings

class WishlistConf:
    '''configuration parameters container'''

    def __init__(self, conf_file = None, section = 'wishlist-builder'):
        try:
            conf = ConfigParser.ConfigParser({
                    'source_file':'wishlist.txt',
                    'images_path':'public_html/wishlist/images/',
                    'images_url':'/wishlist/images/',
                    'template_file':'wish-template.html',
                    'html_file':'public_html/wishlist/index.html',
                    'identify_cmd':'identify -format %%f,%%W,%%H\\n %s',
                    'mogrify_cmd':'mogrify -define filter:blur=0.75 -filter cubic -resize %dx%d^> %s',
                    'csv_delimiter':';',
                    'max_image_width':300,
                    'max_image_height':300,
                    'data_file':'cache.csv',
                    'log_file':'wish.log',
                })

            conf.read(os.path.splitext(os.path.realpath(__file__))[0] + '.conf' if conf_file is None else conf_file)

            self.sourceFile = conf.get(section, 'source_file')
            self.dataFile = conf.get(section, 'data_file')
            self.imagesPath = conf.get(section, 'images_path')
            self.imagesUrl = conf.get(section, 'images_url')
            self.identifyCmd = conf.get(section, 'identify_cmd')
            self.mogrifyCmd = conf.get(section, 'mogrify_cmd')
            self.csvDelimiter = conf.get(section, 'csv_delimiter')
            self.maxImageWidth = int(conf.get(section, 'max_image_width'))
            self.maxImageHeight = int(conf.get(section, 'max_image_height'))
            self.logFile = conf.get(section, 'log_file')
            self.templateFile = conf.get(section, 'template_file')
            self.htmlFile = conf.get(section, 'html_file')

            self.ready = True

        except:
            print("Error reading configuration file '%s' (section: '%s')" % (conf_file, section))
            self.Ready = False

class Logger:
    '''Basic logger'''

    def __init__(self, file_name, show_messages = False):
        self.file_name = file_name
        self._show = show_messages

        try:
            self._file = open(file_name, 'at')
        except:
            print('Error initializing logger ("%s")' % file_name)
            raise

    def __del__(self):
        self._file.close()

    def write(self, message):
        m = '[%s] %s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message)
        if self._show: print(m)
        self._file.write(m + '\n')

class Wishlist:
    '''Generates a wishlist web page using data from a text file, images from the web and Django template'''

    def __init__(self, conf):
        self._conf = conf
        self._log = Logger(self._conf.logFile, True)

    def log(self, message):
        self._log.write(message)

    def generate(self):
        '''Does everything!'''
        self._log.write('Generating wishlist')
        self._data = self.merge_data(self.read_source(), self.load_data())
        self.download_new_images()
        self.process_images()
        self.save_data()
        self.build_html()
        self.cleanup()
        return

    def read_source(self):
        '''Returns a collection of { url, image_url, description } tuples'''
        self.log('Loading ' + self._conf.sourceFile)
        if not os.path.exists(self._conf.sourceFile):
            self.log('Source file does not exists: ' + self._conf.sourceFile)
            return []

        try:
            result = []
            for item in open(self._conf.sourceFile, 'r').read().strip().split('\n\n'):
                parts = item.split('\n')
                if len(parts) != 3: continue
                description, url, image_url = parts
                result.append({ 'url':url.strip(), 'image_url':image_url.strip(), 'desc':description.strip() })
            self.log('Got %d records' % len(result))
            return result

        except:
            self.log('Error reading source file')
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
            self.log('Saving %d records' % self._data)
            writer = csv.writer(open(self._conf.dataFile, 'wb'), delimiter = self._conf.csvDelimiter, quoting = csv.QUOTE_MINIMAL)
            for row in [to_csv_row(record) for record in self._data]:
                if row is not None: writer.writerow(row)

        except:
            self.log('Error saving data to ' + self._conf.dataFile)

    def load_data(self):
        '''Load wishlist records from CSV file'''
        def to_dict(row):
            try:
                return { 'url':row[0], 'image_url':row[1], 'image_file':row[2],
                         'width':int(row[3]), 'height':int(row[4]), 'desc':row[5] }
            except:
                return None

        result = []

        try:
            if os.path.exists(self._conf.dataFile):
                self.log('Loading cached data')
                reader = csv.reader(open(self._conf.dataFile, 'rb'), delimiter = self._conf.csvDelimiter)
                for record in [to_dict(row) for row in reader]:
                    if record is not None: result.append(record)
                self.log('Got %d records' % len(result))
        except:
            self.log('Error loading data from ' + self._conf.dataFile)

        return result

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
            try:
                r = urllib2.urlopen(urllib2.Request(url))
            except:
                return None

            ext = r.headers.subtype.lower()
            if ext not in ['jpeg', 'png', 'gif']: return None
            save_as = '%s.%s' % (file_name, ext)

            try:
                f = open(save_as, 'wb')
                shutil.copyfileobj(r, f)
                f.close()
            finally:
                r.close()

            return save_as

        counter = 1
        result = []
        for item in self._data:
            if len(item['image_file']): continue
            while True:
                new_file = os.path.join(self._conf.imagesPath, str(counter))
                if len(glob.glob(new_file + '.*')) < 1 and not os.path.exists(new_file): break;
                counter += 1
            self.log('Getting %s (new image ID is %d)' % (item['image_url'], counter))
            new_image = download(item['image_url'], os.path.join(self._conf.imagesPath, str(counter)))
            if new_image:
                result.append(new_image)
                item['image_file'] = os.path.basename(new_image)
            else:
                self.log('Error downloading file')

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
            image_files = [self._conf.imagesPath + item['image_file'] for item in self._data
                if (item['width'] == 0 or item['height'] == 0) and item['image_file']]
            if not image_files: return
            self.log('Processing %d images' % len(image_files))

            self.execute(self._conf.mogrifyCmd % (self._conf.maxImageWidth,
                self._conf.maxImageHeight, os.path.join(self._conf.imagesPath, '*')))

            lines = self.execute(self._conf.identifyCmd % ' '.join(image_files), True)
            for line in lines:
                parts = line.strip().split(',')
                if len(parts) != 3: continue
                set_image_size(parts[0], int(parts[1]), int(parts[2]))

        except:
            self.log('Error getting image resolution')
            return []

    def execute(self, command, get_output = False):
        '''Executes a system command with a log message and optional output retrieving'''
        self.log('Executing command: ' + command)

        h = os.popen(command)
        return None if not get_output else h.readlines()

    def build_html(self):
        '''Generates an HTML file with Django template'''
        try:
            self.log('Generating HTML (template: %s)' % os.path.basename(self._conf.templateFile))
            settings.configure(DEBUG=True, TEMPLATE_DEBUG=True, TEMPLATE_DIRS=(''))
            t = Template(open(self._conf.templateFile, 'r').read())
            o = open(self._conf.htmlFile, 'wt')
            o.write(t.render(Context({'items':self._data, 'images_url':self._conf.imagesUrl})))
            o.close()

        except:
            self.log('Error generating HTML')

    def cleanup(self):
        '''Delete unused image files'''
        deleted = []
        actual_images = [item['image_file'] for item in self._data]
        for image_file in glob.glob(os.path.join(self._conf.imagesPath, '*')):
            if os.path.basename(image_file) in actual_images: continue
            try:
                deleted.append(os.path.join(self._conf.imagesPath, image_file))
                os.remove(image_file)
            except:
                self.log('Error deleting "%s"' % image_file)

        if len(deleted):
            self.log('Old images were deleted: ' + ', '.join(deleted))


Wishlist(WishlistConf(None if len(sys.argv) < 2 else sys.argv[1])).generate()
