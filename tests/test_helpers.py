"""Tes fungsi tanpa database: python -m unittest discover -s tests -v"""
import unittest
from app import valid_int, to_rupiah

class HelperTests(unittest.TestCase):
    def test_valid_int(self):
        self.assertEqual(valid_int('2', 1), 2)
        self.assertIsNone(valid_int('-3', 0))
        self.assertIsNone(valid_int('1.2', 0))
        self.assertIsNone(valid_int('abc', 0))

    def test_rupiah(self):
        self.assertEqual(to_rupiah(15000), 'Rp 15.000')

if __name__ == '__main__':
    unittest.main()
