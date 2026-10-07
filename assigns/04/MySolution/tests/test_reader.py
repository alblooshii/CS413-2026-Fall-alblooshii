"""Restricted constructor reader."""
import unittest

from lambda1 import D0Eint, D0Elam, D0Eop2, D0Evar
import lambda1
from lambda_ui.reader import CONSTRUCTORS, ReadError, read_d0exp


class Reader(unittest.TestCase):
    def test_simple_and_nested(self):
        self.assertEqual(read_d0exp('D0Eop2("+", D0Eint(20), D0Eint(22))'),
                         D0Eop2("+", D0Eint(20), D0Eint(22)))

    def test_comments_and_multiline(self):
        text = '# leading comment\nD0Elam("x",   # trailing\n   D0Evar("x")\n)\n# end\n'
        self.assertEqual(read_d0exp(text), D0Elam("x", D0Evar("x")))

    def test_negative_int_and_keywords(self):
        self.assertEqual(read_d0exp("D0Eint(-5)"), D0Eint(-5))
        self.assertEqual(read_d0exp('D0Elam(arg1="x", arg2=D0Evar("x"))'),
                         D0Elam("x", D0Evar("x")))

    def test_table_matches_dataclasses(self):
        for name, (cls, kinds) in CONSTRUCTORS.items():
            self.assertIs(getattr(lambda1, name), cls)
            self.assertEqual(len(kinds), len(cls.__dataclass_fields__), name)

    def test_rejects_arbitrary_python(self):
        bad = ['__import__("os").system("echo hi")', 'open("/etc/passwd")',
               'D0Eint(1).__class__', 'D0Eint(len("ab"))', 'D0Eint(1 + 2)',
               'print(1)', 'lambda: 1', '[D0Eint(1)]', 'D0Eint(*[1])',
               'D0Evar(f"{1}")', 'D0Eint(__import__("os"))', 'x', '1', '',
               'import os', 'D0Eint(1); D0Eint(2)', 'D0Eint(1)\nD0Eint(2)']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ReadError):
                read_d0exp(text)

    def test_validates_arity_and_types(self):
        for text in ['D0Eint("1")', 'D0Eint(True)', 'D0Ebtf(1)', 'D0Evar(3)',
                     'D0Eint()', 'D0Eint(1, 2)', 'D0Eop2("+", D0Eint(1))',
                     'D0Eop2(1, D0Eint(1), D0Eint(1))', 'D0Elam("x", 3)',
                     'D0Elam("x", "y")', 'D0Eint(1.5)', 'D0Eint(arg1=1, arg1=2)',
                     'D0Eint(nope=1)', 'D0Eint(None)']:
            with self.subTest(text=text), self.assertRaises(ReadError):
                read_d0exp(text)

    def test_unterminated_and_deep(self):
        with self.assertRaises(ReadError):
            read_d0exp('D0Eop2("+", D0Eint(1), D0Eint(2)')
        deep = "D0Epfst(" * 500 + 'D0Evar("x")' + ")" * 500
        with self.assertRaises(ReadError):
            read_d0exp(deep)

    def test_null_byte(self):
        with self.assertRaises(ReadError):
            read_d0exp('D0Eint(1)\x00')


if __name__ == "__main__":
    unittest.main()
