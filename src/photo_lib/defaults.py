import os

"""
File contains functions needed to initialize a database. To make future code changes easier, the defaults are inside
this file as opposed to the photo_db file.
"""
image_extensions = [".jpeg", ".jpg", ".png", '.3gp', '.dng', '.heic', '.heif', '.webp', '.tif', '.tiff']
video_extensions = ['.mp4', '.m4v', '.mov', '.gif']

extensions = set(image_extensions + video_extensions)

dipy_union_photo_db = {'.sun', '.dds', '.mp4', '.dcx', '.jpf', '.dib', '.webp', '.spider', '.iim', '.j2k', '.pcd',
                      '.3gp', '.gd2', '.heif', '.psd', '.dng', '.ppm', '.sgi', '.mpo', '.tga', '.xbm', '.msp', '.fli',
                      '.tif', '.jif', '.gd', '.m4v', '.gbr', '.imt', '.flc', '.eps', '.icb', '.jpe', '.jpm', '.fpx',
                      '.fits', '.apng', '.pbm', '.mov', '.ftex', '.png', '.icns', '.jfif', '.nc', '.heic', '.jfi',
                      '.jpx', '.tiff', '.jp2', '.pcx', '.spi', '.vst', '.mic', '.vda', '.cdf', '.pixar', '.gif',
                      '.xpm', '.bw', '.cur', '.jpg', '.jpeg', '.im', '.wal', '.ras', '.rgba', '.pgm', '.emf', '.ico',
                      '.rgb'}

trash_path = '.trash'
thumbnails_path = '.thumbnails'
temp_path = '.temp'
config_path = '.config.json'
db_file = ".photos.db"
miniature_size = 512
thumbnail_size = 256
batch_size = 1000