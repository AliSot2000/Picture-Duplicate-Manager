import datetime
from unittest import TestCase

from photo_lib.data_objects import Selection, SelectionType


"""
Test the Selection Object and it's constructor
- Selection.__init__
"""


class TestSelection(TestCase):
    def test_sel_a_or_sel_b(self):
        """
        Check start, end and duration are correctly rejected for sel_a and sel_b
        """
        self.assertRaises(ValueError, lambda : Selection(selection_type=SelectionType.SELECTION_A,
                                                         start=datetime.datetime.now(datetime.timezone.utc)))

        self.assertRaises(ValueError, lambda : Selection(selection_type=SelectionType.SELECTION_B,
                                                         end=datetime.datetime.now(datetime.timezone.utc)))

        self.assertRaises(ValueError, lambda : Selection(selection_type=SelectionType.SELECTION_A,
                                                         duration=datetime.timedelta(hours=4)))

    def test_presence_duration(self):
        """
        Check that the start, end and duration are correctly requested for time-range
        """
        # start
        self.assertRaises(ValueError, lambda : Selection(selection_type=SelectionType.TIME_RANGE))

        # end and duration none
        self.assertRaises(ValueError, lambda : Selection(selection_type=SelectionType.TIME_RANGE,
                                                         start=datetime.datetime.now(datetime.timezone.utc)))

        # end and duration both not none
        self.assertRaises(ValueError, lambda: Selection(selection_type=SelectionType.TIME_RANGE,
                                                        start=datetime.datetime.now(datetime.timezone.utc),
                                                        end=datetime.datetime.now(datetime.timezone.utc),
                                                        duration=datetime.timedelta(hours=4)))

        # tzinfo needed
        self.assertRaises(TypeError, lambda : Selection(selection_type=SelectionType.TIME_RANGE,
                                                        start=datetime.datetime.now(),
                                                        end=datetime.datetime.now()))

        # tzinfo needed
        self.assertRaises(TypeError, lambda : Selection(selection_type=SelectionType.TIME_RANGE,
                                                        start=datetime.datetime.now(datetime.timezone.utc),
                                                        end=datetime.datetime.now()))
    def test_correct_instances(self):
        """
        Check that the instances are created correctly
        """
        sel_1 = Selection(selection_type=SelectionType.SELECTION_A)

        self.assertEqual(sel_1.selection_type, SelectionType.SELECTION_A)
        self.assertIsNone(sel_1.start)
        self.assertIsNone(sel_1.end)


        sel_2 = Selection(selection_type=SelectionType.SELECTION_B)

        self.assertEqual(sel_2.selection_type, SelectionType.SELECTION_B)
        self.assertIsNone(sel_2.start)
        self.assertIsNone(sel_2.end)

        start = datetime.datetime.now(datetime.timezone.utc)
        end = datetime.datetime.now(datetime.timezone.utc)

        dur = datetime.timedelta(hours=4)

        end2 = start + dur

        sel_3 = Selection(selection_type=SelectionType.TIME_RANGE,
                          start=start, end=end)

        self.assertEqual(sel_3.selection_type, SelectionType.TIME_RANGE)
        self.assertEqual(sel_3.start, start)
        self.assertEqual(sel_3.end, end)

        sel_4 = Selection(selection_type=SelectionType.TIME_RANGE,
                          start=start, duration=dur)

        self.assertEqual(sel_4.selection_type, SelectionType.TIME_RANGE)
        self.assertEqual(sel_4.start, start)
        self.assertEqual(sel_4.end, end2)