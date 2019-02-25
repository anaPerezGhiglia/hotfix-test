#!/usr/bin/python3

from math import *
import sys
import argparse
import re
import fileinput
import datetime
import configparser
from itertools import tee
from functools import reduce
import os

VERSION_PATTERN = '##\s\[(\d+(?:\.\d+)*)'
CHANGELOG_FILE_NAME = 'CHANGELOG.md'
GITHUB_DOMAIN = 'https://github.com/'
RELEASE_FOOTNOTE_REGEX = '\[.+\]\:\s(.+)'
SUBSECTION_HEADER = '### '
UNRELEASED_IGNORECASE = re.compile(re.escape('[Unreleased]'), re.IGNORECASE)

CHANGELOG_HEADER = """# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]
"""
RED = '\033[0;31m'
GREEN = '\033[0;32m'
NC = '\033[0m'

def colored_text(msg, color):
    return color + msg + NC

def error(msg):
    return colored_text(msg, RED)

def success(msg):
    return colored_text(msg, GREEN)

class Repository:
    def __init__(self, project_dir):
        git_config = configparser.ConfigParser()
        git_config.read(file_path(project_dir, '.git/config'))
        remote_url = git_config['remote "origin"']['url']
        match = re.search('git\@github\.com:([\w._\/-]+)\.git', remote_url)
        self.name = match.group(1)
        
    def compare_url(self, from_tag, to_tag):
        return GITHUB_DOMAIN + '{}/compare/{}...{}'.format(self.name, from_tag, to_tag)        
        
class Section:
    def __init__(self, lines, name = None):
        #TODO: search version if not present search for unreleased
        if name:
            self.name = name
        else:
            self.name = re.match(VERSION_PATTERN, lines[0]).group(1)
        
        self.lines = lines
        
class UnreleasedSection(Section):
    
    def subsection_name(name):
            return SUBSECTION_HEADER+name
        
    ADDED_SUBSECTION = subsection_name('Added')
    CHANGED_SUBSECTION = subsection_name('Changed')
    DEPRECATED_SUBSECTION = subsection_name('Deprecated')
    REMOVED_SUBSECTION = subsection_name('Removed')
    FIXED_SUBSECTION = subsection_name('Fixed')
    SECURITY_SUBSECTION = subsection_name('Security')
    
    def __init__(self, lines):
        super().__init__(lines, 'Unreleased')
        
        subsection_lines = list(filter(lambda x: re.match(SUBSECTION_HEADER, x), self.lines))

        # subsection ranges
        subsection_indexes = lines_to_indexes(self.lines, subsection_lines)
        
        if subsection_indexes:
            subsection_indexes.append(len(self.lines))
        
        subsections_ranges = list(pairwise(subsection_indexes))
        
        if subsection_indexes:
            # if there are subsections, header is until the first one
            self.header = self.lines[0:subsection_indexes[0]]
        else:
            #otherwise is all the lines
            self.header = self.lines
            
        
        # combine subsection header with range        
        subsections = list(zip(subsection_lines, subsections_ranges))
        
        def find_subsection(name):
            subsection = next(filter(lambda x: re.match(name, x[0], re.IGNORECASE), subsections), None)
            if subsection:
                start, stop = subsection[1]
                sub_lines = self.lines[start:stop]
                #remove empty lines
                sub_lines = list(filter(lambda x: x, sub_lines))
                return sub_lines
            else:
                return []
              
        self.added_lines = find_subsection(UnreleasedSection.ADDED_SUBSECTION)
        self.changed_lines = find_subsection(UnreleasedSection.CHANGED_SUBSECTION)
        self.deprecated_lines = find_subsection(UnreleasedSection.DEPRECATED_SUBSECTION)
        self.removed_lines = find_subsection(UnreleasedSection.REMOVED_SUBSECTION)
        self.fixed_lines = find_subsection(UnreleasedSection.FIXED_SUBSECTION)
        self.security_lines = find_subsection(UnreleasedSection.SECURITY_SUBSECTION)
        
        
    def _add_line(self, list, section_name, message):
        if not list:
            list.append(section_name)
        list.append(' - {}'.format(message))
        
    def add(self, message):
        self._add_line(self.added_lines, UnreleasedSection.ADDED_SUBSECTION, message)
        
    def change(self, message):
        self._add_line(self.changed_lines, UnreleasedSection.CHANGED_SUBSECTION, message)
        
    def deprecate(self, message):
        self._add_line(self.deprecated_lines, UnreleasedSection.DEPRECATED_SUBSECTION, message)
        
    def remove(self, message):
        self._add_line(self.removed_lines, UnreleasedSection.REMOVED_SUBSECTION, message)
        
    def fix(self, message):
        self._add_line(self.fixed_lines, UnreleasedSection.FIXED_SUBSECTION, message)
        
    def security(self, message):
        self._add_line(self.security_lines, UnreleasedSection.SECURITY_SUBSECTION, message)
        
    def all_lines(self):
        all = [self.added_lines, self.changed_lines, self.deprecated_lines, self.removed_lines, self.fixed_lines, self.security_lines]
        
        def add_ending_line(group):
            group.append('')
            return group
        
        def combine(acc, elem):
            if elem:
                return acc + add_ending_line(elem)
            else:
                return acc
                
        return self.header + reduce(combine, all, [])
    
    def close(self, version_number):
        self.header = ['## [{}] - {}'.format(version_number, datetime.datetime.today().strftime('%Y-%m-%d'))]
        lines = self.all_lines()
        return Section(lines)
        
 
class EditableChangelog:
    def __init__(self, project_dir, changelog_filename):
        self.project_dir = project_dir
        self.changelog_filename = changelog_filename
        print('Project dir: {}'.format(self.project_dir))
        print('Changelog filename: {}'.format(self.changelog_filename))
        file_lines = []
        with open(file_path(self.project_dir, self.changelog_filename)) as fh:
            file_lines = [ line.rstrip() for line in fh.readlines() ]
            
            unreleased = next(filter(lambda x: re.match('## \[Unreleased\]', x, re.IGNORECASE) is not None, file_lines), None)
            unreleased_index = file_lines.index(unreleased)
            
            # Get header lines
            self.header = file_lines[:unreleased_index]
            
            # Get releases sections indexes
            def is_section(line):
                return re.match(VERSION_PATTERN, line) is not None
            section_lines = filter(is_section, file_lines)
            sections_indexes = lines_to_indexes(file_lines, section_lines)
            
            # Get footnotes
            self.releases_footnotes = list(filter(lambda x: re.match(RELEASE_FOOTNOTE_REGEX, x), file_lines))
            release_footnotes_indexes = lines_to_indexes(file_lines, self.releases_footnotes)
            if(release_footnotes_indexes):
                sections_indexes.append(release_footnotes_indexes[0]) # add first footnote to build last pair
            pairs = pairwise(sections_indexes)
            
            # Build sections objects with all sections (including unreleased)
            self.closed_sections = list(map(lambda tuple: Section(file_lines[tuple[0]:tuple[1]]), pairs))
            if(sections_indexes):
                self.unreleased_section = UnreleasedSection(file_lines[unreleased_index:sections_indexes[0]])
            else:
                self.unreleased_section = UnreleasedSection(file_lines[unreleased_index:])
    
    
    def close(self):
        all_lines = []
        all_lines.append(self.header)
        all_lines.append(self.unreleased_section.all_lines())
        for section in self.closed_sections:
            all_lines.append(section.lines)
        all_lines.append(self.releases_footnotes)
        
        file = open(file_path(self.project_dir, self.changelog_filename), 'w')
        for sublist in all_lines:
            for item in sublist:
                file.write(item + '\n')
        file.close()
        print(success('\n[OK] Changelog file edited'))

        
    def existing_versions(self):
        return list(map(lambda x: x.name, self.closed_sections))
    
    def close_unreleased_section(self, new_version_number, repository):
        # close compare url
        if self.releases_footnotes:
            compare = self.releases_footnotes[0].replace('...HEAD', '...{}'.format(new_version_number))
            # change tag name
            self.releases_footnotes[0] = UNRELEASED_IGNORECASE.sub('[{}]'.format(new_version_number), compare)
        
        # insert new unreleased compare url
        new_unreleased_compare_url = '[Unreleased]: {}'.format(repository.compare_url(new_version_number, 'HEAD'))
        self.releases_footnotes.insert(0, new_unreleased_compare_url)
        
        newest_closed_version = self.unreleased_section.close(new_version_number)
        self.closed_sections.insert(0, newest_closed_version)
        self.unreleased_section = UnreleasedSection(['## [Unreleased]', ''])
        
        self.close()
        
def file_path(project_root_dir, file_name):
    return project_root_dir + '/' + file_name

def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

def exit_existing_version(intended_version, latest_version):
    exit('\n* Version {} already exists in changelog file -> Latest version: {}'.format(intended_version, latest_version))
    
def lines_to_indexes(file_lines, lines):
    return list(map(lambda x: file_lines.index(x), lines))
 
def edit_changelog(args, func):
    changelog = EditableChangelog(args.dir, args.file)
    func(changelog.unreleased_section)(args.message)
    changelog.close()
    
def add(args):
    edit_changelog(args, lambda c: c.add)
def change(args):
    edit_changelog(args, lambda c: c.change)
def deprecate(args):
    edit_changelog(args, lambda c: c.deprecate)    
def remove(args):
    edit_changelog(args, lambda c: c.remove)
def fix(args):
    edit_changelog(args, lambda c: c.fix)
def security(args):
    edit_changelog(args, lambda c: c.security)
    
def new_release(args):

    changelog = EditableChangelog(args.dir, args.file)

    repository = Repository(args.dir)

    if args.version_number in changelog.existing_versions():
        exit_existing_version(args.version_number, changelog.existing_versions()[0])
    
    print('Target release version: {}'.format(args.version_number))
    changelog.close_unreleased_section(args.version_number, repository)

def init_changelog(args):
    filename = file_path(args.dir, args.file)
    
    if os.path.isfile(filename):
        exit(error('[ERROR] Changelog file {} already exists'.format(filename)))
    else:
        file = open(filename, 'w+')
        file.write(CHANGELOG_HEADER)
        file.close()
        print(success('[OK] Changelog file created as {}'.format(filename)))
        
def main():
    parser = argparse.ArgumentParser(description='Performs operations in CHANGELOG file')
    subparsers = parser.add_subparsers()
    
    parser.add_argument('--dir', default=os.getcwd(), metavar='<directory>', help='Project\'s directory. Default: current directory')
    parser.add_argument('--file', default=CHANGELOG_FILE_NAME, metavar='<filename>', help='Changelog file name. Default: {}'.format(CHANGELOG_FILE_NAME))
        
    #create the parser for the "release" command
    parser_release = subparsers.add_parser('release')
    parser_release.add_argument('version_number', metavar='version', type=str, help='release version number')
    parser_release.set_defaults(func=new_release)
    
    #create the parser for the "add" command
    parser_add = subparsers.add_parser('add')
    parser_add.add_argument('message', metavar='message', type=str, help='message of added section')
    parser_add.set_defaults(func=add)
    
    #create the parser for the "change" command
    parser_change = subparsers.add_parser('change')
    parser_change.add_argument('message', metavar='message', type=str, help='message of changed section')
    parser_change.set_defaults(func=change)
    
    #create the parser for the "deprecate" command
    parser_deprecate = subparsers.add_parser('deprecate')
    parser_deprecate.add_argument('message', metavar='message', type=str, help='message of deprecated section')
    parser_deprecate.set_defaults(func=deprecate)
    
    #create the parser for the "remove" command
    parser_remove = subparsers.add_parser('remove')
    parser_remove.add_argument('message', metavar='message', type=str, help='message of removed section')
    parser_remove.set_defaults(func=remove)
    
    #create the parser for the "fix" command
    parser_fix = subparsers.add_parser('fix')
    parser_fix.add_argument('message', metavar='message', type=str, help='message of fixed section')
    parser_fix.set_defaults(func=fix)
    
    #create the parser for the "security" command
    parser_security = subparsers.add_parser('security')
    parser_security.add_argument('message', metavar='message', type=str, help='message of security section')
    parser_security.set_defaults(func=security)
    
    #create the parser for "init" changelog command
    parser_init = subparsers.add_parser('init', description='creates a new changelog file')
    parser_init.set_defaults(func=init_changelog)
    
    args = parser.parse_args()
    args.func(args)
    
    
# Standard boilerplate to call the main() function to begin the program.
if __name__ == '__main__':
    main()


