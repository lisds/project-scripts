#!/usr/bin/env python3
""" Write templated document using config variables
"""

from argparse import ArgumentParser, RawDescriptionHelpFormatter

import yaml



def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('config_path', default='projects.yaml',
                        help='Path to YAML file containing variables')
    parser.add_argument('template_path',
                        help='Path containing input template')
    parser.add_argument('--out_path', default='-',
                        help='Output document path or - for stdout (default)')
    return parser


def main():
    args = get_parser().parse_args()
    with open(args.config_path, 'rt') as fobj:
        config = yaml.load(fobj, Loader=yaml.SafeLoader)
    with open(args.template_path, 'rt') as fobj:
        content = fobj.read()
    output = content.format(**config)
    if args.out_path == '-':
        print(output)
    else:
        with open(args.out_path, 'wt') as fobj:
            fobj.write(output)


if __name__ == "__main__":
    main()
