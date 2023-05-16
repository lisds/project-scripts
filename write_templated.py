#!/usr/bin/env python3
""" Write templated text
"""

from argparse import ArgumentParser, RawDescriptionHelpFormatter


def args2dict(args):
    out = {}
    for m in dir(args):
        if not m.startswith('_'):
            val = getattr(args, m)
            if val is not None:
                out[m] = val
    return out


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('in_fname',
                        help='Text for templating')
    parser.add_argument('--hub-url', default='https://ds.lis.2i2c.cloud',
                        help='Base URL for JupyterHub')
    parser.add_argument('--hub-sdir', default='projects',
                        help="Subdirectory for marked files in user's system")
    parser.add_argument('--marker-email', default='matthew.brett@lis.ac.uk',
                        help="Contact email for feedback.")
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    with open(args.in_fname, 'rt') as fobj:
        out_markdown = fobj.read().format(**args2dict(args))
    print(out_markdown)


if __name__ == '__main__':
    main()
