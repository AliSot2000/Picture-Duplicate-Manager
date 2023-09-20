# All ToDos until the first version is done

# Tiles
- [ ] Tiles for year
- [ ] Tiles for all
- [ ] Tiles for month
- [ ] Tiles for day

# Big Screen for Database

## Import View
- [X] Add import View to the main Window
- [X] When clicked, open the bigScreen Image (with with comparison if possible. If not, just the bigScreen Image)
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

## Caroussell
- [X] Add functions to update the bigscreen
- [X] Generate Carousel
- [X] Unload images when out of view.
- [X] Simplify the widgets

## Database:
- [ ] Index for main database based on the date.
- [X] Datetime in SQLite formate
- [ ] Functions to update the table
- [X] Function to get number of images on a given day, month, year
- [X] Function to get info of a day, month year
- [ ] Function to link files based on hashes
- [ ] Function to check if all indexed images are present
- [ ] Function to update hash based on file name
- [ ] Add Column for path (custom folders)
- [ ] Function to index database and all new files are to be labled as import
- [ ] New Duplicates Table (Clusters and duplicates with known duplicates)

- New Version of Fast DiffPy with new Version of MP Library
- Duplicates without Database
- Create new Database function
- 

# Features
- [ ] Danger zone

## BigScreen
- [ ] Allow in import big screen to open the successor if the image is in the replaced table.
- [ ] In Big Screen, have button to import the currently open image.
- [ ] Actions to move to next and previous image.

# Danger Zone Actions
- [ ] Recompute hashes based on File name
- [ ] Recompute names and paths from file hashes
- [ ] Reindex the database


## Compare Pane
- [ ] Functionality to view known duplicates to compare the metadata
