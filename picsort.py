import argparse
import filecmp
import hashlib
import logging
import os
import re

# https://github.com/ianare/exif-py
import exifread

logger = logging.getLogger('PicImport')
dateregex = re.compile(r'^(?P<year>\d{4}):(?P<month>\d{2}):(?P<day>\d{2})\s(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<seconds>\d{2})$')
hashes = {}
copycount = 0


def chunkreader(fobj, chunksize=1024):
    '''
    Generator that reads a file in chunks of bytes
    http://stackoverflow.com/questions/748675/finding-duplicate-files-and-removing-them
    '''
    while True:
        chunk = fobj.read(chunksize)
        if not chunk:
            return
        yield chunk


def hashfile(filename):
    ''' return true if hash was successful and file is unique '''
    global hashes
    hashobj = hashlib.sha1()
    result = True

    with open(filename, 'rb') as fileobj:
        for chunk in chunkreader(fileobj):
            hashobj.update(chunk)

        fileid = (hashobj.digest(), os.path.getsize(filename))
        duplicate = hashes.get(fileid, None)

        if duplicate:
            logger.error('Duplicate found: %s and %s', filename, duplicate)
            result = False
        else:
            hashes[fileid] = filename

    return result


def comparefiles(file1, file2):
    ''' Maybe I should use a hash comparison instead?  '''
    return filecmp.cmp(file1, file2)


def validatedirectory(directory):
    ''' Make sure the :param directory: exists, if not create it'''
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as err:
            logger.error('Cannot create directory %s - err', directory, err)
            return False
        else:
            logger.info('Creating directory %s', directory)

    return True


def copyimage(absolutepath, filename, library, metadata):
    librarypath = '{0}\\{1}\\{2}'.format(metadata['year'], metadata['month'], metadata['day'])
    library = os.path.join(library, librarypath)
    copyfile(absolutepath, filename, library, librarypath)


def copyvideo(absolutepath, filename, library):
    mo = re.match(r"VID_(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})_\d+\.mp4", filename)
    if not mo:
        logger.error('Unable to parse date from filename %s', filename)
        return

    metadata = mo.groupdict()
    librarypath = '{0}\\{1}\\{2}'.format(metadata['year'], metadata['month'], metadata['day'])
    library = os.path.join(library, librarypath)
    copyfile(absolutepath, filename, library, librarypath)


def copyfile(absolutepath, filename, library, librarypath):
    global copycount
    if not validatedirectory(library):
        logger.error('Directory %s for video %s not created. See previous error message', librarypath, filename)
        return

    librarypath = os.path.join(library, filename)
    i = 1
    while True:
        if os.path.exists(librarypath):
            if comparefiles(absolutepath, librarypath):
                logger.warning('%s already exists as %s. Will not copy file', absolutepath, librarypath)
                return
            else:
                newfilename = filename.split('.')
                newfilename = '{0}-{1}.{2}'.format(newfilename[0], i, newfilename[1])
                logger.info('%s is equal to %s. Renaming %s to %s', absolutepath, librarypath, filename, newfilename)
                librarypath = os.path.join(library, newfilename)
                i += 1
        else:
            break

    try:
        os.rename(absolutepath, librarypath)
    except OSError as err:
        logger.error('Cannot copy %s to %s - %s', absolutepath, librarypath, err)
    else:
        copycount += 1
        logger.info('Copy %s to %s', absolutepath, librarypath)


def importfolder(directory, library):
    '''Import images from :param directory: und copy them into the :param library:'''
    logger.info('Scanning directory %s', directory)

    for item in os.listdir(directory):
        absolutepath = os.path.join(directory, item)
        logger.debug('Joining %s and %s to %s', directory, item, absolutepath)

        if not os.path.isfile(absolutepath):
            continue

        if not hashfile(absolutepath):
            continue

        if item.endswith(".mp4"):
            copyvideo(absolutepath, item, library)
            continue

        metadata = {}
        with open(absolutepath, 'rb') as imagebuf:
            tags = exifread.process_file(imagebuf, details=False)
            if 'EXIF DateTimeOriginal' in tags:
                m = dateregex.match(tags['EXIF DateTimeOriginal'].values)
                if m:
                    metadata = m.groupdict()
                    logger.debug('Matched %s: ', item, m.groupdict())
            else:
                logger.error('Missing date taken tag in image %s', absolutepath)

        if metadata:
            copyimage(absolutepath, item, library, m.groupdict())


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%d.%m %H:%M')

    # Standard windows picture directory
    defaultImageStorage = os.path.join("e:\\", 'Pictures')

    parser = argparse.ArgumentParser(description='Import images and sort them into subfolders by date yyyy/mm/dd.')
    parser.add_argument('-r', '--recursive', action="store_true", help='Look recursively through given folder')
    parser.add_argument('-f', '--folders', metavar='folder', type=str, nargs='+',
                        required=True, help='Folders to look through')
    parser.add_argument('-l', '--library', type=str, default=defaultImageStorage,
                        help='Folder the images will be exported to')
    args = parser.parse_args()

    if not args.folders:
        logger.error('No directories given. Use --folders to add directories.')
        return -1

    for directory in args.folders:
        if not os.path.exists(directory):
            logger.error('%s does not exist. Only use existing directories' % directory)
            return -1

    for directory in args.folders:
        if args.recursive:
            for root, _, _ in os.walk(directory):
                importfolder(root, args.library)
        else:
            importfolder(directory, args.library)

    logger.info('%s unique images found. %s copied.', len(hashes), copycount)

if __name__ == '__main__':
    main()
