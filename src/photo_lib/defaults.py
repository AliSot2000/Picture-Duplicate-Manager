import os

"""
File contains functions needed to initialize a database. To make future code changes easier, the defaults are inside
this file as opposed to the photo_db file.
"""
default_image_extensions = [".jpeg", ".jpg", ".png", '.3gp', '.dng', '.heic', '.heif', '.webp', '.tif', '.tiff']
default_video_extensions = ['.mp4', '.m4v', '.mov', '.gif']

default_extensions = set(default_image_extensions + default_video_extensions)

dipy_union_photo_db = {'.sun', '.dds', '.mp4', '.dcx', '.jpf', '.dib', '.webp', '.spider', '.iim', '.j2k', '.pcd',
                      '.3gp', '.gd2', '.heif', '.psd', '.dng', '.ppm', '.sgi', '.mpo', '.tga', '.xbm', '.msp', '.fli',
                      '.tif', '.jif', '.gd', '.m4v', '.gbr', '.imt', '.flc', '.eps', '.icb', '.jpe', '.jpm', '.fpx',
                      '.fits', '.apng', '.pbm', '.mov', '.ftex', '.png', '.icns', '.jfif', '.nc', '.heic', '.jfi',
                      '.jpx', '.tiff', '.jp2', '.pcx', '.spi', '.vst', '.mic', '.vda', '.cdf', '.pixar', '.gif',
                      '.xpm', '.bw', '.cur', '.jpg', '.jpeg', '.im', '.wal', '.ras', '.rgba', '.pgm', '.emf', '.ico',
                      '.rgb'}

default_trash_path = lambda root: os.path.join(root, '.trash')
default_thumbnails_path = lambda root: os.path.join(root, '.thumbnails')
default_temp_path = lambda root: os.path.join(root, '.temp')
default_config_path = lambda root: os.path.join(root, '.config.json')
default_db_file = ".photos.db"