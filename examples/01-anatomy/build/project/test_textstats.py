import unittest

from textstats import average_word_length, word_count


class TestWordCount(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(word_count("the quick brown fox"), 4)

    def test_extra_whitespace(self):
        self.assertEqual(word_count("the  quick\nbrown fox "), 4)

    def test_empty(self):
        self.assertEqual(word_count(""), 0)


class TestAverageWordLength(unittest.TestCase):
    def test_simple(self):
        self.assertAlmostEqual(average_word_length("ab abcd"), 3.0)


if __name__ == "__main__":
    unittest.main()
