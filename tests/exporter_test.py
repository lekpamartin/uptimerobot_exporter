# SPDX-FileCopyrightText: 2022 Robin Schneider <ro.schneider@senec.com>
#
# SPDX-License-Identifier: Apache-2.0

import unittest

import exporter


class Test(unittest.TestCase):
    def test_escape_backslash(self):
        self.assertEqual(
            exporter._escape_strings({"backslash": r"test\sdf"}),
            {"backslash": r"test\\sdf"},
        )

    def test_escape_quote(self):
        self.assertEqual(
            exporter._escape_strings({"quote": '"test"'}),
            {"quote": '\\"test\\"'},
        )

    def test_escape_newline(self):
        self.assertEqual(
            exporter._escape_strings({"newline": "test\ntest"}),
            {"newline": r"test\ntest"},
        )

    def test_escape_all_special_chars(self):
        self.assertEqual(
            exporter._escape_strings(
                {
                    "all": 'One backslash \\ and one ASCII newline \n and one double-quote ".'
                }
            ),
            {
                "all": 'One backslash \\\\ and one ASCII newline \\n and one double-quote \\".'
            },
        )


if __name__ == "__main__":
    unittest.main()
