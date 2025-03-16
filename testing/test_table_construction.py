from unittest import TestCase

from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.new_photo_db import PhotoDB
from photo_lib.db_definitions import DBVersion, DBHistorySpec, StaticDeclaration, GenericDeclaration, Version


"""
Testing the following functions
- api.db.build_definition_lookup
"""

class BuildDefTest(TestCase):
    def test_basic(self):
        """
        Test that the generic check functions. Static paths are correctly parsed.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
        }
        version = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                            all_definitions=["def_a", "def_b"],
                            definitions=base_static,
                            all_generic_definitions=[],
                            generic_definitions={})
        history = DBHistorySpec(history=[version])

        static, generic = PhotoDB.build_definition_lookup(version_override=version, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, {})

    def test_with_generics(self):
        """
        Testing the basics if also a generic table works and the parent is correctly picked up.
        """
        base_generic = {
            "list": GenericDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)"
            )
        }
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
            "list": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, value TEXT, table_name TEXT)",
                name="list",
            )
        }
        version = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                            all_definitions=["def_a", "def_b"],
                            definitions=base_static,
                            all_generic_definitions=["list"],
                            generic_definitions=base_generic)
        history = DBHistorySpec(history=[version])

        static, generic = PhotoDB.build_definition_lookup(version_override=version, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, base_generic)

    def test_history_basic(self):
        """
        Testing if the history is correctly read and the lookup works correctly.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
        }

        old = {"def_b": base_static["def_b"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b"],
                                definitions=new,
                                all_generic_definitions=[],
                                generic_definitions={})

        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        static, generic = PhotoDB.build_definition_lookup(version_override=version_new, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, {})

    def test_history_generic_new(self):
        """
        Generic Parent Table in new and generic table in new.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
            "list": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, value TEXT, table_name TEXT)",
                name="list",
            )
        }

        base_generic = {
            "list": GenericDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)"
            )
        }

        old = {"def_b": base_static["def_b"], "list": base_static["list"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b", "list"],
                                definitions=new,
                                all_generic_definitions=["list"],
                                generic_definitions=base_generic)

        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        static, generic = PhotoDB.build_definition_lookup(version_override=version_new, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, base_generic)

    def test_history_generic_old(self):
        """
        Generic Parent Table in new and generic table in new.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
            "list": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, value TEXT, table_name TEXT)",
                name="list",
            )
        }

        base_generic = {
            "list": GenericDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)"
            )
        }

        old = {"def_b": base_static["def_b"], "list": base_static["list"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b", "list"],
                                definitions=new,
                                all_generic_definitions=["list"],
                                generic_definitions={})

        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=["list"],
                                generic_definitions=base_generic)
        history = DBHistorySpec(history=[version_new, version_old])

        static, generic = PhotoDB.build_definition_lookup(version_override=version_new, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, base_generic)

    def test_missing_history_static(self):
        """
        Checking that if a static declaration is missing from the all_definitions in the history, it doesn't cause an
        error.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
        }

        old = {"def_b": base_static["def_b"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b"],
                                definitions=new,
                                all_generic_definitions=[],
                                generic_definitions={})

        # Shouldn't cause a problem, because the definitions only of the current version are inspected.
        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b", "list"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        static, generic = PhotoDB.build_definition_lookup(version_override=version_new, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, {})

    # INFO: Ignoring case when static decl is in previous and listed in current to be correct.

    def test_missing_current_static(self):
        """
        Checking that a static declaration from the all_definitions of the current version is missing, raises an Error.
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
        }

        old = {"def_b": base_static["def_b"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b", "list"],
                                definitions=new,
                                all_generic_definitions=[],
                                generic_definitions={})

        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        self.assertRaises(
            ImplementationError,
            lambda: PhotoDB.build_definition_lookup(version_override=version_new, history_override=history))

    def test_missing_history_generic(self):
        """
        Check if a version in the history specifies a generic table definition, and it's missing, in its definitions,
        it doesn't cause a problem
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
            "list": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, value TEXT, table_name TEXT)",
                name="list",
            )
        }

        base_generic = {
            "list": GenericDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)"
            )
        }

        old = {"def_b": base_static["def_b"], "list": base_static["list"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b", "list"],
                                definitions=new,
                                all_generic_definitions=["list"],
                                generic_definitions=base_generic)

        # Shouldn't cause an issue, presence is only checked with current version
        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=["list"],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        static, generic = PhotoDB.build_definition_lookup(version_override=version_new, history_override=history)

        self.assertEqual(static, base_static)
        self.assertEqual(generic, base_generic)

    # INFO: Ignoring case when generic decl is in previous and listed in current to be correct.

    def test_missing_current_generic(self):
        """
        Check if a missing generic declaration in the current_version all_generic_declarations is detected..
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            ),
            "list": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, value TEXT, table_name TEXT)",
                name="list",
            )
        }

        old = {"def_b": base_static["def_b"], "list": base_static["list"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b", "list"],
                                definitions=new,
                                all_generic_definitions=["list"],
                                generic_definitions={})

        # Shouldn't cause an issue, presence is only checked with current version
        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        self.assertRaises(
            ImplementationError,
            lambda: PhotoDB.build_definition_lookup(version_override=version_new, history_override=history))

    def test_missing_parent(self):
        """
        Check that it is correctly detected, that if a parrent is missing
        """
        base_static = {
            "def_a": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_a"),
            "def_b": StaticDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)",
                name="def_b",
            )
        }

        base_generic = {
            "list": GenericDeclaration(
                declaration_string="CREATE TABLE `%name%` (key INTEGER PRIMARY KEY, VALUE TEXT)"
            )
        }

        old = {"def_b": base_static["def_b"]}

        new = {"def_a": base_static["def_a"]}

        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["def_a", "def_b"],
                                definitions=new,
                                all_generic_definitions=["list"],
                                generic_definitions=base_generic)

        # Shouldn't cause an issue, presence is only checked with current version
        version_old = DBVersion(current_version=Version(major=0, minor=9, patch=0),
                                previous_version=None,
                                all_definitions=["def_b"],
                                definitions=old,
                                all_generic_definitions=[],
                                generic_definitions={})
        history = DBHistorySpec(history=[version_new, version_old])

        self.assertRaises(
            ImplementationError,
            lambda: PhotoDB.build_definition_lookup(version_override=version_new, history_override=history))

    def test_version_missmatch(self):
        """
        Check that the integrity of the version is checked. If the previous version in the history doesn't match, error
        """
        version_new = DBVersion(current_version=Version(major=1, minor=0, patch=0),
                                previous_version=Version(major=0, minor=9, patch=0),
                                all_definitions=["some_def"],
                                definitions={},
                                all_generic_definitions=[],
                                generic_definitions={})

        # Shouldn't cause an issue, presence is only checked with current version
        version_old = DBVersion(current_version=Version(major=0, minor=8, patch=0),
                                previous_version=None,
                                all_definitions=[],
                                definitions={},
                                all_generic_definitions=[],
                                generic_definitions={})

        history = DBHistorySpec(history=[version_new, version_old])

        self.assertRaises(
            ImplementationError,
            lambda: PhotoDB.build_definition_lookup(version_override=version_new, history_override=history))
