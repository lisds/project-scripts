#!/usr/bin/env python3
""" Various actions on student project files.
"""

import os
import os.path as op
import shutil
from pathlib import Path
import re
from subprocess import run as prun
from collections import Counter
from pprint import pprint
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import yaml
import pandas as pd
import nbformat as nbf

import mcpmark.mcputils as mcu

GITIGNORE = """
.ipynb_checkpoints/
*.Rmd
__pycache__/
"""

MARK_CATEGORIES = ('Questions', 'Analysis', 'Results', 'Readability',
                   'Writing', 'Reproducibility')


ACTIONS = ('check',
           'report',
           'split-projects',
           'make-repos',
           'pull-repos',
           'add-submodules',
           'write-gitignore',
           'write-marks',
           'write-project-list',
           'write-perscon',
           'write-feedback',
          )


def read_yaml(fname):
    with open(fname, 'rt') as fobj:
        config = yaml.load(fobj, Loader=yaml.SafeLoader)
    return config


def get_class_list(config):
    handler = mcu.make_submission_handler(config)
    df = handler.read_student_data()
    # Used in Birmingham mixed masters, UG class.
    if not 'UGPG' in df:
        df['UGPG'] = 'UG'
    df['id'] = df.index
    return df.set_index(config['student_id_col'],
                        drop=False)


def check_config(config, write_missing=True):
    all_members = set()
    class_list = get_class_list(config)
    known_students = set(class_list.index)
    for name, pconfig in config.get('projects', {}).items():
        members = member_logins(pconfig)
        unknown = members.difference(known_students)
        if len(unknown):
            raise ValueError(f"Unknown students {', '.join(unknown)} in {name}")
        if len(all_members.intersection(members)):
            raise ValueError(f'Students in {name} overlap with other project')
        all_members.update(members)
    missing = known_students.difference(all_members)
    mdf = class_list.loc[list(missing)]
    print('Missing students')
    print(mdf)
    if write_missing:
        mdf.to_csv('missing.csv', index=None)


def member_logins(pconfig):
    members = pconfig['members']
    return set(m.split('@')[0] for m in members)


def report(config):
    class_list = get_class_list(config)
    for name, pconfig in config.get('projects', {}).items():
        print(name)
        print('=' * len(name))
        members = member_logins(pconfig)
        print(class_list.loc[list(members)])
        print()


def split_projects(config):
    class_list = get_class_list(config)
    ug_pg = class_list['UGPG']
    types = set(ug_pg)
    project_lists = {k: [] for k in types}
    login_col = config['student_id_col']
    type_lists = {k: list(class_list.loc[ug_pg == k, login_col])
                  for k in types}
    member_counts = Counter()
    for name, pconfig in config.get('projects', {}).items():
        members = member_logins(pconfig)
        for t in types:
            if len(members.intersection(type_lists[t])):
                project_lists[t].append(name)
        member_counts[name] = len(members)
    # Remove UG projects from PGT project list
    project_lists['PGT'] = set(project_lists['PGT']).difference(
        project_lists['UG'])
    project_lists = {k: sorted(v) for k, v in project_lists.items()}
    pprint(project_lists)
    for name, plist in project_lists.items():
        n_students = sum([member_counts[p] for p in plist])
        print(name, len(plist), n_students)


def make_repos(config, check=True):
    for name in config.get('projects', {}):
        if op.isdir(name):
            continue
        os.mkdir(name)
        prun(['git', 'init'], cwd=name, check=check)
        prun(['hub', 'create', f'cfd2020-projects/{name}', '--private'],
            cwd=name, check=check)


def pull_repos(config, check=True, rebase=False, push=False):
    cmd = ['git', 'pull'] + (['--rebase'] if rebase else [])
    for name in config.get('projects', {}):
        print(f'Pull for {name}')
        prun(cmd, cwd=name, check=check)
        if push and rebase:
            prun(['git', 'push'], cwd=name, check=check)


def add_submodules(config, org_url, check=True):
    for name in config.get('projects', {}):
        prun(['git', 'submodule', 'add', f'{org_url}/{name}',
             name], check=check)


def write_gitignore(config, check=True):
    for name in config.get('projects', {}):
        fname = op.join(name, '.gitignore')
        with open(fname, 'wt') as fobj:
            fobj.write(GITIGNORE)
        prun(['git', 'add', '.gitignore'], cwd=name, check=check)
        prun(['git', 'commit', '-m', 'Add .gitignore'],
            cwd=name, check=check)


def get_proj_marks(path):
    path = Path(path)
    nb_paths = path.glob('*.ipynb')
    for nb_fname in nb_paths:
        nb = nbf.read(nb_fname, nbf.NO_CONVERT)
        if len(nb.cells) == 0:
            continue
        last_cell = nb.cells[-1]
        if last_cell['cell_type'] != 'markdown':
            continue
        last_lines = last_cell['source'].splitlines()
        if len(last_lines) < 2 or last_lines.pop(0) != '## Marks':
            continue
        marks = {}
        for L in last_lines[1:]:
            if (m := re.match(r'\*\s*(\w*)\s*:\s*([0-9.]+)\s*$', L)):
                k, v = m.groups()
                marks[k] = float(v)
        return marks


def get_marks(config, student_type=None, allow_missing=False):
    class_list = get_class_list(config)
    proj_col = config.get('marks_col', 'Project %')
    project_root = Path(config.get('projects_path', '.'))
    for name, pconfig in config.get('projects', {}).items():
        marks = {'Project name': name,
                 'Presentation': pconfig['presentation']}
        proj_marks = get_proj_marks(project_root / name)
        if proj_marks is None:
            msg = f'Missing project marks for {name}'
            if not allow_missing:
                raise RuntimeError(msg)
            print(msg)
            continue
        assert set(proj_marks) == set(MARK_CATEGORIES)
        marks.update(proj_marks)
        for member, contrib_score in pconfig['members'].items():
            marks['Contribution'] = contrib_score
            class_list.loc[member, list(marks)] = marks
    class_list[proj_col] = (
        class_list.loc[:, ('Presentation',) + MARK_CATEGORIES]
        .mean(axis=1))
    if config.get('round_final'):
        class_list[proj_col] = class_list[proj_col].round()
    if student_type:
        class_list = class_list[class_list['UGPG'] == student_type]
    return class_list


def write_marks(config, student_type=None, allow_missing=False):
    marks_froot = config.get('marks_froot', 'project_marks')
    suffix = f'_{student_type.lower()}' if student_type else ''
    marks_fname = f"{marks_froot}{suffix}.csv"
    class_list = get_marks(config, student_type, allow_missing)
    class_list.to_csv(marks_fname, index=None)


def write_project_list(config, student_type=None):
    class_list = get_class_list(config)
    class_list['project'] = ''
    for name, pconfig in config.get('projects', {}).items():
        members = member_logins(pconfig)
        class_list.loc[members, 'project'] = name
    if student_type:
        class_list = class_list[class_list['UGPG'] == student_type]
    suffix = f'_{student_type.lower()}' if student_type else ''
    out_fname = f'project_list{suffix}.csv'
    class_list.to_csv(out_fname, index=None)


def write_perscon(config, student_type=None):
    suffix = f'_{student_type.lower()}' if student_type else ''
    in_fname = f'project_list{suffix}.csv'
    login_col = config['student_id_col']
    in_df = pd.read_csv(in_fname).set_index(login_col)
    class_list = get_class_list(config)
    if student_type is not None:
        class_list = class_list[class_list['UGPG'] == student_type]
    class_list[config['pc_marks_col']] = in_df['mark']
    pc_marks_froot = config.get('pc_marks_froot', 'perscon_marks')
    out_fname = f'{pc_marks_froot}{suffix}.csv'
    class_list.drop(columns='ID').to_csv(out_fname, index=None)



def get_member2project(projects):
    recoder = {}
    for p, p_dict in projects.items():
        for m in p_dict['members']:
            recoder[m] = p
    return recoder


def write_feedback(config, out_path, student_type=None):
    class_list = get_marks(config, student_type)
    marks_col = config['marks_col']
    if config.get('round_final', False):
        class_list[marks_col] = class_list[marks_col].round()
    handler = mcu.make_submission_handler(config)
    m2proj = get_member2project(config['projects'])
    project_root = Path(config.get('projects_path', '.'))
    out_path = Path(out_path)
    for user, row in class_list.iterrows():
        if not (project := m2proj.get(user)):
            continue
        login = row[config['feedback_id_col']]
        jh_user = handler.login2jh(login)
        fb_in_path = project_root / project
        fb_out_path = out_path / jh_user / 'project'
        shutil.copytree(fb_in_path, fb_out_path)
        marks = row.loc['Presentation':]
        (fb_out_path / 'marks.md').write_text(
            marks.to_markdown())


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('action',
                        help='One of ' + ','.join([f"'{a}'" for a in ACTIONS]))
    parser.add_argument('--config', default='projects.yaml',
                        help='YaML configuration for course')
    parser.add_argument('--no-check', action='store_true',
                        help='Disable error on failed shell commands')
    parser.add_argument('--rebase', action='store_true',
                        help='Rebase, push on git pull')
    parser.add_argument('--student-type',
                        help='"UG" or "PGT" (both if not specified)')
    parser.add_argument('--allow-missing', action='store_true',
                        help='Whether to allow missing marks without error')
    parser.add_argument('--feedback-out-path', default='feedback',
                        help='Path to write feedback files')
    parser.add_argument('--org-url',
                        help='Version control root URL for student '
                        'repositories (for "add-submodules"')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    config = read_yaml(args.config)
    if args.action == 'check':
        check_config(config)
    elif args.action == 'report':
        report(config)
    elif args.action == 'split-projects':
        split_projects(config)
    elif args.action == 'make-repos':
        make_repos(config, not args.no_check)
    elif args.action == 'pull-repos':
        pull_repos(config, not args.no_check, args.rebase, args.rebase)
    elif args.action == 'add-submodules':
        if args.org_url is None:
            raise RuntimeError('Specify --org-url for this action')
        add_submodules(config, args.org_url, not args.no_check)
    elif args.action == 'write-gitignore':
        write_gitignore(config, not args.no_check)
    elif args.action == 'write-marks':
        write_marks(config, args.student_type, args.allow_missing)
    elif args.action == 'write-project-list':
        write_project_list(config, args.student_type)
    elif args.action == 'write-perscon':
        write_perscon(config, args.student_type)
    elif args.action == 'write-feedback':
        write_feedback(config, args.feedback_out_path, args.student_type)
    else:
        alist = "', '".join(ACTIONS)
        raise RuntimeError(f"action should be in '{alist}'")


if __name__ == '__main__':
    main()
