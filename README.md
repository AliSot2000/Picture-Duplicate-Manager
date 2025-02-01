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

Convention regarding the existence of Thumbnails and Miniatures. Files moved to the `replaced table` are don't need the 
Display Files and rely on their parent for those files.