### Conventions:
##### Generic Tables
Each `generic_definitions` from the `db_definitions.py` must have an associated table which contains at least the 
columns `key`, `table_name` which keeps track of the generic tables created with this definition.
This is needed for table verification in the initialization as well as deletion of tables and presentation to the user.
Everytime a new Generic Table is created:
1. A new row is added to the table keeping track of the generic tables 
2. The CREATE TABLE statement is executed.

Everytime a Generic Table is deleted:
1. The table is dropped from the database.
2. The row with that table name is dropped from the table keeping track of the generic tables.

##### Folder Structure
If no path is provided in the `db_dir` table, the path the images get stored at is `db_root/YYYY/MM/DD`. 
(Reminder think: Does UTC Offset have an effect?). Otherwise, it is `db_root/db_local_dir` where `db_local_dir` is a 
relative path which is within the database to the file.


##### File Naming Convention:
Files are in nothing is selected named like `YYYY-MM-DDTHH-MM-SS_key:04[_org_file_name].ext`.

Convention regarding the existence of Thumbnails and Miniatures. Files moved to the marked as duplicates don't need the 
Display Files and rely on their parent for those files.

### Hash assoz table convention:
The Hash assoz table contains a specifically labeled hash (initial) which is the hash obtained while computing the
metadata in the source directory of the import. For all non-initial hashes, the database records every occurrence of a 
given hash. Say you had in the history file_hash_1, file_hash_2, file_hash_3, file_hash_1 and the database was updated
every time the file changed, the fact, that the file had file_hash_1 was the earliest hash is lost, and the order of 
the hashes will be file_hash_2, file_hash_3, file_hash_1. This is done to allow for file changes back and forth due to
another application making modifications and to reduce the pollution of the hash_assoz table due to changes in the 
file datetime recorded in the db.

# SQLite Max Size of INTEGER is 2**63 - 1

# Motivation
- Why retain duplicates and have the duplicate hierarchy when you could _just_ use the trash functionality? 
The point is, if we have a duplicate, we want to retain the metadata of that file and keep it associated with the 
parent. That way, we have more information about the parent. That is not always something we _really_ want, but it is
useful in cases when we have images without a timestamp.


# Workflow:
- This library _only_ takes care of duplicates and checking that imported files aren't imported twice. 
That's to say, there's no album feature. There's no share feature. All this library is supposed to do, is keep track of 
duplicates and manage metadata of the files. It is suggested, that you use another program on top of the structure in 
the file system to handle everything else (albums, sharing, geolocation, face recognition, ...). However, keep in mind
that this library relies on files staying where they were imported at originally and retaining their filename given by 
the db. In the odd occurrence that you need to rename files, move files or change their timezones, the database provides 
functions to do that. It is advised, that you perform these actions through the gui or use the photo_api. 
Should you have modified the files in the database, it numerous functions to reestablish consistency. However, 
keep in mind that these functions make assumptions and that you should always check their output prior to applying it.

### Modifying files before importing
Modifying filename, file datetime, timezone and location can be done through the gui or the api. If you are aware that 
you need to do that, and you do not enforce a custom directory structure. You must do it before importing the new files 
in any other database. Performing changes to the datetime of the file, when it is in the default directory YYYY/MM/DD
**will** move it to the new directory, depending on the changed timezone and or changed datetime. So you would have to 
relink the files in any other database when you do these changes after the fact. Modifying timezone is not always an 
issue, as long as you do not modify the file name. 

### Modifying files after importing. 
It might be very well possible that you imported files and then imported them in another database and you discover, that 
for example, you forgot to set the correct timezone on your camera, when you were on vacation. You can reset the 
timezone of the images. If you don't rename them and you have all images of that trip in a custom directory, 
nothing will happen to the files and they stay in the correct directory and don't have to be relinked.

### Methods to reestablish a correct state of the database
- `check_presence`: The database keeps in mind (also for files in the main directory, not only the trash) whether they 
are present. (This is for example useful, when you have part of your database on a different drive, that isn't 
connected at the moment.) You can update the presence and subsequently perform a deduplication action and it won't run 
into errors because files weren't found. If you sorted the files out by hand in the filesystem or with another database
it is possible ot update all files (or a subset of them) which aren't present to be marked as in the trash. Keep in mind
that, if you didn't generate thumbnails, you won't have a image representation when you attempt to reimport these files 
and it will only show an empty picture.
- 