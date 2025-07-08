# All ToDos until the first version is done

- [X] Detect Resize Via MouseButton -> Failed, doesn't work in QT. Desktop Env is Responsible. 

# Tiles
- [X] Tiles for year
- [X] Tiles for all
- [X] Tiles for month
- [X] Tiles for day

# Big Screen for Database

## Import View
- [X] Add import View to the main Window
- [X] When clicked, open the bigScreen Image (with comparison if possible. If not, just the bigScreen Image)
- [X] Close image with ESC
- [X] Check button needs to update the subsection the image is in.
- [X] Add button to import


## BigScreen
- [X] Create the side layout
- [X] Create separate version for import
- [X] Add button to show metadata of all duplicates along with this image
- [X] Add button to show image already in database for import
- [X] Add check button 
- [X] Show image in database when with button (show associated metadata as well)

## Carousel
- [X] Add functions to update the bigscreen
- [X] Generate Carousel
- [X] Unload images when out of view.
- [X] Simplify the widgets

## Database:
- [X] Index for main database based on the date.
- [X] Datetime in SQLite formate
- [X] Functions to update the table
- [X] Function to get number of images on a given day, month, year
- [X] Function to get info of a day, month year
- [X] Function to link files based on hashes
- [X] Function to check if all indexed images are present
- [X] Function to update hash based on file name
- [X] Add Column for path (custom folders)
- [X] Function to index database and all new files are to be labled as import
- [X] New Duplicates Table (Clusters and duplicates with known duplicates)
- [X] Grouping into rows should be done in DB not in gui (save RAM)
- [X] Grouping 
- [X] Datetime local (so local time)
- [X] Datetime in UTC

- Duplicates without Database
- Create new Database function
- 
- Test the max number of widgets we can have loaded -> determine thumbnail size and determine from that the minimum 
size you can have for images


## BigScreen
- [ ] Allow in import big screen to open the successor if the image is in the replaced table.
- [ ] In Big Screen, have button to import the currently open image.
- [ ] Actions to move to next and previous image.

# Danger Zone Actions
- [X] Recompute hashes based on File name
- [X] Recompute names and paths from file hashes
- [X] Reindex the database


## Compare Pane
- [ ] Functionality to view known duplicates to compare the metadata

## Config
- [X] Option to have custom database `path` (needs to be in config)
- [X] Config


Time Handling:
- `x.astimezone(tz=datetime.UTC)` changes UTC offset **and** HH:MM:SS value such that the point in time is consistent
- `x.replace(ZoneInfo("ZoneName"))` changes the utc offset but **not** HH:MM:SS

## Key check:
Go through all keys and check that we have all metadata keys which contain, date, time, datetime or timestamp
Question: Should the `db_name` be always not null? I guess so, to ensure we don't run into clashes in the trash right?

## FEATURES TODO:
- [ ] Add Sidecar File Option
- [ ] Add Indexes and other things to declarations (like dependant declarations)
- [ ] Add bulk move files from selection
- [X] Relocate (Move Files matching name back to the location inferred by the database)
- [X] Update location (Add or remove custom dir for files which were moved within the database)
- [X] Function to bake the current datetime into the tags. (Maybe add multiple selections for which keys to write into)
- [ ] Datetime From filename
- [ ] Add thumbnails for the import table. 
- [ ] Add Context Menu