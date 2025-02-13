import logging
from sqlite3 import Connection, Cursor
from typing import Union, Dict, List, Optional
import os


class BaseSQliteDB:
    db_path: Union[str, None]

    sq_con: Union[Connection, None]
    sq_cur: Union[Cursor, None]
    __extra_cur: Dict[str, Cursor]

    logger: Optional[logging.Logger] = None

    def __init__(self, db_path: str):
        """
        Base class for sqlite3 database access.

        :param db_path: path to db
        """
        self.db_path = None
        self.sq_con = None
        self.sq_cur = None
        self.__extra_cur = {}

        self.connect(db_path)
        self.gc = self.get_cursor

    def connect(self, db_path: str):
        """
        Connect to the database, set the path of the object and create a cursor
        """
        self.db_path = os.path.abspath(db_path)

        self.sq_con = Connection(self.db_path)
        self.sq_cur = self.sq_con.cursor()

    def debug_execute(self, stmt: str, args: Union[tuple, dict, None] = None, cur: str = None):
        """
        Function executes statement in database and in case of an exception prints the offending statement.

        User ? for placeholder by index or :name for placeholder by name.

        :param stmt: Statement to execute
        :param args: Substitution arguments to pass to the statement
        :param cur: string to get an extra named cursor from the extra cursors.

        :return:
        """
        sq_cur = self.sq_cur if cur is None else self.__extra_cur[cur]
        san_args = self.sanitize_string(args)
        try:
            if args is not None:
                sq_cur.execute(stmt, san_args)
            else:
                sq_cur.execute(stmt)
        except Exception as e:
            if self.logger is None:
                print(f"Failed to execute:\n{stmt}\n{san_args}")
            else:
                self.logger.exception(f"Failed to execute:\n{stmt}\n{san_args}", exc_info=e)
            raise e

    def debug_execute_many(self, stmt: str, args: List[Union[tuple, dict]], cur: str = None):
        """
        Function executes statement in database and in case of an exception prints the offending statement.
        """
        sq_cur = self.sq_cur if cur is None else self.__extra_cur[cur]
        san_args = [self.sanitize_string(arg) for arg in args]
        try:
            sq_cur.executemany(stmt, san_args)
        except Exception as e:
            if self.logger is None:
                print(f"Failed to execute:\n{stmt}\n{san_args}")
            else:
                self.logger.exception(f"Failed to execute:\n{stmt}\n{san_args}", exc_info=e)
            raise e

    def add_extra_cursor(self, name: str ) -> Cursor:
        """
        Create another cursor. Will store it in the cursor in the class and return the cursor on success

        :param name: Name of the cursor

        :return: newly created Cursor
        """
        if self.__extra_cur.get(name) is not None:
            return self.__extra_cur[name]

        cur = self.sq_con.cursor()
        self.__extra_cur[name] = cur
        return cur

    def remove_extra_cursor(self, name: str):
        """
        Remove a previously created extra cursor

        :param name: Name of the cursor to remove

        :return: None
        """
        cur = self.__extra_cur.get(name)
        if cur is None:
            return

        cur: Cursor
        cur.close()

        del self.__extra_cur[name]

    def list_extra_cursors(self) -> List[str]:
        """
        Function returns a list of all cursors.

        :return: List of names of cursors
        """
        return list(self.__extra_cur.keys())

    def get_cursor(self, name: str) -> Cursor:
        """
        Get a named cursor.

        :param name: Name of cursor

        :return: Cursor associated with name

        :raise ValueError: If there's no cursor with that name
        """
        cur = self.__extra_cur.get(name)
        if cur is None:
            raise ValueError(f"Cursor {name} doesn't exist")

        return cur

    def cleanup(self):
        """
        Actions performed:
        - Commit the changes
        - Close the connection
        - clear the variables
        """
        self.sq_con.commit()

        for cur in self.__extra_cur.values():
            cur.close()

        self.sq_con.close()
        self.db_path = None

        self.sq_con = None
        self.sq_cur = None

    def gc(self, name: str):
        """
        Shorthand for get_cursor.

        :param name:
        :return:
        """
        ...

    def commit(self):
        """
        Commit the changes
        """
        self.sq_con.commit()

    def close(self):
        """
        Close the connection
        """
        self.sq_con.close()
        self.sq_con = None
        self.sq_cur = None

    def vacuum(self):
        self.sq_cur.execute("VACUUM")

    @staticmethod
    def sanitize_string(args: Union[tuple, dict, None]) -> Union[tuple, dict, None]:
        """
        Sanitize strings by replacing all ' with ''

        :param args: arguments to sanitize

        :return: arguments with sanitized strings
        """
        if isinstance(args, tuple):
            san_args = []

            # Sanitize args
            for a in args:
                if isinstance(a, str):
                    san_args.append(a.replace("'", "''"))
                else:
                    san_args.append(a)

            return tuple(san_args)

        elif isinstance(args, dict):
            san_args = {}

            for key, value in args.items():
                if isinstance(value, str):
                    san_args[key] = value.replace("'", "''")
                else:
                    san_args[key] = value

            return san_args

        else:
            assert args is None, "Unexpected arguments"
            return None
