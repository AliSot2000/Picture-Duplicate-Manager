import os.path

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict


debug = True


class Version(BaseModel):
    major: int = Field(..., ge=0,
                       description="The major version of the database declaration")
    minor: int = Field(..., ge=0,
                       description="The minor version of the database declaration")
    patch: int = Field(..., ge=0,
                       description="The patch version of the database declaration")

    model_config = ConfigDict(
        populate_by_name=True
    )


class GenericDeclaration(BaseModel):
    declaration_string: str = Field(..., description="The declaration string")
    name_placeholder: str = Field(default="%name%",
                                  description="The placeholder in the declaration string to replace "
                                              "with the actual name of the definition.")

    model_config = ConfigDict(
        populate_by_name=True
    )


class StaticDeclaration(GenericDeclaration):
    name: str = Field(..., description="The name of the static declaration")


class DBVersion(BaseModel):
    current_version: Version
    previous_version: Optional[Version] = Field(None,
                                            description="The previous version of the database declaration in sequence.")

    new_elements: Optional[List[str]] = Field(None,
                                              description="List of declarations which are new to this version and "
                                                          "didn't exist in the previous version or which existed in a "
                                                          "previous version but were changed in this one.")
    removed_elements: Optional[List[str]] = Field(None,
                                                  description="List of declarations which are removed in this version"
                                                              " compared to the old version. (So used to exist in the "
                                                              "previous version but don't anymore)")

    new_generics: Optional[List[str]] = Field(None,
                                              description="List of generic declarations which can be instantiated "
                                                          "multiple times and are new to this version."
                                                          " e.g. Import Tables")
    removed_generics: Optional[List[str]] = Field(None,
                                                  description="List of generic declarations which are removed in this "
                                                              "version that could be instantiated multiple times. e.g. "
                                                              "Import Tables")

    all_definitions: List[str] = Field(...,
                                       description="List of all definitions present in this version. "
                                                   "IMPORTANT: The order in which the definitions are listed is the "
                                                   "order in which they are created. Keep this in mind for things that "
                                                   "reference each other.")

    definitions: Dict[str, StaticDeclaration] = Field(None,
                                                      description="List of definitions which are new or changed "
                                                                  "compared to the previous version.")

    all_generic_definitions: List[str] = Field(None,
                                               description="List of all generic declarations which are instantiated ")
    generic_definitions: Dict[str, GenericDeclaration] = Field(None,
                                                               description="List of generic declarations which are new "
                                                                           "or changed.")

    model_config = ConfigDict(
        populate_by_name=True
    )


class DBHistorySpec(BaseModel):
    history: List[DBVersion] = Field(...,)


current_version = DBVersion(
    current_version=Version(major=1, minor=0, patch=0),
    previous_version=None,

    removed_elements=None,
    removed_generics=None,

    new_generics=["import_table"],
    new_elements=["hashes", "hashes_str_index", "hash_key_index",
                  "main", "main_key_index", "main_datetime_index", "main_db_name_index", "main_flag_index",
                  "hash_assoz", "hash_assoz_key_index", "hash_assoz_datetime_index",
                  "db_dir", "db_dir_key_index",
                  "gps_location", "gps_location_key_index",
                  "replaced", "replaced_key_index",
                  "import_tables",
                  "known_duplicates", "known_duplicates_key_index",
                  "duplicates", "duplicates_key_index",
                  ],
    all_generic_definitions=["import_table"],
    all_definitions=["hashes", "hashes_str_index", "hash_key_index",
                     "db_dir", "db_dir_key_index",
                     "gps_location", "gps_location_key_index",
                     "main", "main_key_index", "main_datetime_index", "main_db_name_index", "main_flag_index",
                     "hash_assoz", "hash_assoz_key_index", "hash_assoz_datetime_index",
                     "replaced", "replaced_key_index",
                     "import_tables",
                     "known_duplicates", "known_duplicates_key_index",
                     "duplicates", "duplicates_key_index",
                     ],
    definitions={
        # All definitions for the main hash lookup table
        "hashes": StaticDeclaration(
            name="hashes",
            declaration_string="CREATE TABLE `%name%` "
                               "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
                               "hash TEXT UNIQUE NOT NULL)"),
        "hashes_str_index": StaticDeclaration(
            name="hashes_str_index",
            declaration_string="CREATE INDEX `%name%` ON hashes (hash)"
        ),
        "hash_key_index": StaticDeclaration(
            name="hash_key_index",
            declaration_string="CREATE INDEX `%name%` ON hashes (key)"
        ),

        # Definitions for the directory lookup table
        "db_dir": StaticDeclaration(
            name="db_dir",
            declaration_string="CREATE TABLE `%name%` ("
                       "key INTEGER PRIMARY KEY AUTOINCREMENT, "
                       "db_local_dir TEXT NOT NULL)"
        ),
        "db_dir_key_index": StaticDeclaration(
            name="db_dir_key_index",
            declaration_string="CREATE INDEX `%name%` ON db_dir (key)"
        ),

        # GPS Table Definitions
        "gps_location": StaticDeclaration(
            name="gps_location",
            declaration_string="CREATE TABLE `%name%` ("
                               "key INTEGER PRIMARY KEY AUTOINCREMENT, "
                               "gps_latitude REAL NOT NULL, "
                               "gps_longitude REAL NOT NULL, "
                               "UNIQUE (gps_latitude, gps_longitude))"
        ),
        "gps_location_key_index": StaticDeclaration(
            name="gps_location_key_index",
            declaration_string="CREATE INDEX `%name%` ON gps_location (key)"
        ),

        # Main Table Definitions
        "main": StaticDeclaration(
            name="main",
            declaration_string="CREATE TABLE main ("
                               "key INTEGER PRIMARY KEY AUTOINCREMENT, "
                               "original_filename TEXT NOT NULL, "  
                               "metadata TEXT, "
                               "google_metadata TEXT, "
                               "datetime TEXT NOT NULL, "
                               "db_name TEXT NOT NULL, "
                               "parent INTEGER, "
                               "timezone TEXT, " # is dependent on system defaults so retained here.
                               "flags INTEGER NOT NULL,"
                               "FOREIGN KEY (parent) REFERENCES main(key))"
        ),
        "main_key_index": StaticDeclaration(
            name="main_key_index",
            declaration_string="CREATE INDEX `%name%` ON main (key)"
        ),
        "main_datetime_index": StaticDeclaration(
            name="main_datetime_index",
            declaration_string="CREATE INDEX `%name%` ON main (datetime(datetime))"
        ),
        "main_db_name_index": StaticDeclaration(
            name="main_db_name_index",
            declaration_string="CREATE INDEX `%name%` ON main (db_name)"
        ),
        "main_flag_index": StaticDeclaration(
            name="main_flag_index",
            declaration_string="CREATE INDEX `%name%` ON main (flags)"
        ),

        # Hash Assoz Table Definitions
        "hash_assoz": StaticDeclaration(
            name="hash_assoz",
            declaration_string="CREATE TABLE `%name%` ("
                               "hash_key INTEGER NOT NULL, "
                               "file_key INTEGER NOT NULL, "
                               "file_size_bytes INTEGER NOT NULL, "
                               "hash_date TEXT NOT NULL,"
                               "FOREIGN KEY (hash_key) REFERENCES hash(key),"
                               "FOREIGN KEY (file_key) REFERENCES main(key),"
                               "UNIQUE(hash_key, file_key, hash_date))"
        ),
        "hash_assoz_key_index": StaticDeclaration(
            name="hash_assoz_key_index",
            declaration_string="CREATE INDEX `%name%` ON hash_assoz (hash_key, file_key)"
        ),
        "hash_assoz_datetime_index": StaticDeclaration(
            name="hash_assoz_datetime_index",
            declaration_string="CREATE INDEX `%name%` ON hash_assoz (datetime(datetime))"
        ),

        # Metadata Table Definitions
        # Contains the columns that make define files which aren't declared replaced.
        "metadata": StaticDeclaration(
            name="metadata",
            declaration_string="CREATE TABLE `%name%` ("
                               "main_key INTEGER, "
                               "original_dirname TEXT NOT NULL, "
                               "naming_tag TEXT NOT NULL, "
                               "gps_location INTEGER, "
                               "db_dir INTEGER, "
                               "datetime_source INTEGER CHECK (`%name%`.datetime_source IN (0, 1, 2, 3, 4, 5)), "
                               "FOREIGN KEY (main_key) REFERENCES main(key), "
                               "FOREIGN KEY (gps_location) REFERENCES gps_location(key), "
                               "FOREIGN KEY (db_dir) REFERENCES db_dir(key)) "
        ),
        "metadata_key_index": StaticDeclaration(
            name="metadata_key_index",
            declaration_string="CREATE INDEX `%name%` ON metadata (key)"
        ),

        # List of import tables (so generic tables)
        "import_tables": StaticDeclaration(
            name="import_tables",
            declaration_string="CREATE TABLE `%name%` ("
                               "key INTEGER PRIMARY KEY AUTOINCREMENT, "
                               "root_path TEXT NOT NULL, "
                               "table_name TEXT UNIQUE NOT NULL, "
                               "table_description TEXT,"
                               "flags INTEGER DEFAULT 0)"
        ),

        # Duplicates and Known Duplicates Table
        "known_duplicates": StaticDeclaration(
            name="known_duplicates",
            declaration_string="CREATE TABLE `%name%` ("
                               "key_a INTEGER NOT NULL, "
                               "key_b INTEGER NOT NULL,"
                               "UNIQUE (key_a, key_b),"
                               "CHECK ( key_a < key_b ),"
                               "FOREIGN KEY (key_a) REFERENCES main (key),"
                               "FOREIGN KEY (key_b) REFERENCES main (key))"
        ),
        "known_duplicates_key_index": StaticDeclaration(
            name="known_duplicates_key_index",
            declaration_string="CREATE INDEX `%name%` ON known_duplicates (key_a, key_b)"
        ),
        "duplicates": StaticDeclaration(
            name="duplicates",
            declaration_string="CREATE TABLE `%name%` ("
                               "key_a INTEGER NOT NULL, "
                               "key_b INTEGER NOT NULL, "
                               "delta REAL NOT NULL CHECK ( `%name%`.delta >= 0 ), "
                               "UNIQUE (key_a, key_b),"
                               "CHECK ( key_a < key_b ),"
                               "FOREIGN KEY (key_a) REFERENCES main (key),"
                               "FOREIGN KEY (key_b) REFERENCES main (key))"
        ),
        "duplicates_key_index": StaticDeclaration(
            name="duplicates_key_index",
            declaration_string="CREATE INDEX `%name%` ON duplicates (key_a, key_b)"
        ),
        "duplicates_delta_index": StaticDeclaration(
            name="duplicates_delta_index",
            declaration_string="CREATE INDEX `%name%` ON duplicates (delta)"
        )
    },
    generic_definitions={
        "import_table": GenericDeclaration(
            declaration_string=f"CREATE TABLE `%name%` ("
                               f"key INTEGER PRIMARY KEY AUTOINCREMENT,"
                               f"original_filename TEXT NOT NULL,"
                               f"original_dirname TEXT NOT NULL,"
                               f"metadata TEXT,"
                               f"google_metadata TEXT,"
                               f"file_hash TEXT NOT NULL, "
                               f"file_size_bytes INTEGER NOT NULL,"
                               f"imported INTEGER DEFAULT 0 CHECK (`%name%`.imported in (0,1,2)),"
                               f"allowed INTEGER DEFAULT 0 CHECK (`%name%`.allowed in (0,1)),"
                               f"match_type INTEGER DEFAULT 0 CHECK (`%name%`.match_type in (0,1,2,3,4,5)),"
                               f"datetime TEXT,"
                               f"timezone TEXT,"
                               f"naming_tag TEXT,"
                               f"gps_latitude REAL,"
                               f"gps_longitude REAL,"
                               f"highest_match INT DEFAULT NULL, " # Highest match, the one producing the 
                               f"matches TEXT DEFAULT NULL,"  # the match found in the trash, images or replaced table
                               f"import_key INTEGER DEFAULT NULL,"  # the key may not have foreign key constraint since we 
                               # want to be able to move the image to the replaced table
                               # INFO: datetime_source in import table doesn't have CUSTOM.
                               f"datetime_source INTEGER CHECK (`%name%`.datetime_source IN (0, 1, 2, 3, 4)), "
                               f"UNIQUE (original_filename, original_dirname));"

        )
    }
)


with open(os.path.join(os.path.dirname(__file__), "previous_versions.json")) as defs:
    def_str = defs.read()
    _history = DBHistorySpec.model_validate_json(def_str)
    srt_hst = sorted(_history.history,
                     reverse=True,
                     key= lambda v: (v.current_version.major, v.current_version.minor, v.current_version.patch))
    history = DBHistorySpec(history=srt_hst)
