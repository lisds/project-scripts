#!/usr/bin/env python3
""" Write templated document using config variables
"""

from argparse import ArgumentParser, RawDescriptionHelpFormatter

from mcpmark.mcputils import get_component_config


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('template_path',
                        help='Path containing input template')
    parser.add_argument('out_path',
                        help='Output document path')
    return parser


def main():
    args, config = get_component_config(get_parser(),
                                        multi_component=True,
                                        component_default='all',
                                        component_as_option=True)
    with open(args.template_path, 'rt') as fobj:
        content = fobj.read()
    with open(args.out_path, 'wt') as fobj:
        fobj.write(content.format(**config))


if __name__ == "__main__":
    main()
