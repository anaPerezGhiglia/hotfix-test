#!/usr/bin/python

from math import *
import sys
import argparse
import re
import fileinput
import datetime
import configparser
from gi.importer import repository
from debian import changelog
from itertools import tee
from functools import reduce

VERSION_PATTERN = '##\s\[(\d+(?:\.\d+)*)'
CHANGELOG_FILE_NAME = 'CHANGELOG.md'
PROJECT_ROOT_DIR = ''
GITHUB_DOMAIN = 'https://github.com/'
RELEASE_FOOTNOTE_REGEX = '\[.+\]\:\s(.+)'
SUBSECTION_HEADER = '### '

class Repository:
    def __init__(self):
        git_config = configparser.ConfigParser()
        git_config.read(file_path('.git/config'))
        remote_url = git_config['remote "origin"']['url']
        match = re.search('git\@github\.com:([\w._\/-]+)\.git', remote_url)
        self.name = match.group(1)
        print('Repository: {}'.format('{}/{}'.format(GITHUB_DOMAIN, self.name)))
        
    def compare_url(self, from_tag, to_tag):
        return GITHUB_DOMAIN + '{}/compare/{}...{}'.format(self.name, from_tag, to_tag)        
        
class Changelog:
    def __init__(self, file_name, next_version):
        self.file_name = file_name
        
        versions = []
        unreleased_tag = None
        unreleased_compare_url = None
        
        with open(file_path(file_name), 'r') as file_handler:
            for n, line in enumerate(file_handler, start =1):
                match = re.search(VERSION_PATTERN, line)
                if match:
                    versions.append(match.group(1))
                    
                tag_match = re.search('\[Unreleased\]\s*$', line, re.IGNORECASE)
                if tag_match is not None:
                    unreleased_tag = n
        
        self.existing_versions = versions #version sorted from most recent to oldest
        self.unreleased_tag_line = unreleased_tag
#         self.unreleased_compare_url_line = unreleased_compare_url #TODO: calculate in the moment, because modifications to the file makes this get obsolete
        self.next_version = next_version
    
    def unreleased_compare_url_line(self):
        with open(file_path(self.file_name), 'r') as file_handler:
            for n, line in enumerate(file_handler, start =1):
                compare_match = re.search('\[Unreleased\]:\s', line, re.IGNORECASE)
                if compare_match is not None:
                    unreleased_compare_url = n
        return unreleased_compare_url
            
    def latest_version(self):
        return self.existing_versions[0]
    
    def _close_tag(self):
        self._replace_line(self.unreleased_tag_line, after_line='\n## [{}] - {}'.format(self.next_version, datetime.datetime.today().strftime('%Y-%m-%d')))
    
    def _replace_line(self, line_number, before_line = None, line_replace = None, after_line= None):
        fh = fileinput.input(self.file_name, inplace=True)
        line_replacement = None
        for n, line in enumerate(fh, start=1):
            if n == line_number:
                
                if before_line:
                    print(before_line)
                
                if line_replace:
                    line_replacement = line_replace(line)
                    print(line_replacement, end='')
                else:
                    print(line, end='')
                
                if after_line:
                    print(after_line)
                    
            else:
                print(line, end='')
                
        fileinput.close()
        return line_replacement
            
    def _close_compare_url(self, repository, version):
        # close open compare to new version
        insensitive_unreleased = re.compile(re.escape('[Unreleased]'), re.IGNORECASE)
        close_version = lambda url: insensitive_unreleased.sub('[{}]'.format(version), url.replace('...HEAD', '...{}'.format(version)))
        #insert new compare to HEAD
        before_line = '[Unreleased]: {}'.format(repository.compare_url(version, 'HEAD'))
        new_version_compare = self._replace_line(self.unreleased_compare_url_line(), before_line, close_version)
        match = re.search(RELEASE_FOOTNOTE_REGEX, new_version_compare)
        print('New version compare url: {}'.format(match.group(1)))

    def close_release_section(self, repository):
        self._close_tag()
        self._close_compare_url(repository, self.next_version)

class Section:
    def __init__(self, file_lines, start_line, stop_line, name = None):
        if name:
            self.name = name
        else:
            self.name = re.match(VERSION_PATTERN, file_lines[start_line]).group(1)
        
        self.lines = file_lines[start_line:stop_line]
        
class UnreleasedSection(Section):
    
    def subsection_name(name):
            return SUBSECTION_HEADER+name
        
    ADDED_SUBSECTION = subsection_name('Added')
    CHANGED_SUBSECTION = subsection_name('Changed')
    DEPRECATED_SUBSECTION = subsection_name('Deprecated')
    REMOVED_SUBSECTION = subsection_name('Removed')
    FIXED_SUBSECTION = subsection_name('Fixed')
    SECURITY_SUBSECTION = subsection_name('Security')
    
    def __init__(self, file_lines, start_line, stop_line):
        super().__init__(file_lines, start_line, stop_line, 'Unreleased')
        
        subsection_lines = list(filter(lambda x: re.match(SUBSECTION_HEADER, x), self.lines))

        # subsection ranges
        subsection_indexes = lines_to_indexes(file_lines, subsection_lines)
        subsection_indexes.append(stop_line)
        subsections_ranges = list(pairwise(subsection_indexes))

        self.header = file_lines[start_line:subsection_indexes[0]]
        
        # combine subsection header with range        
        subsections = list(zip(subsection_lines, subsections_ranges))
        
        def find_subsection(name):
            subsection = next(filter(lambda x: re.match(name, x[0], re.IGNORECASE), subsections), None)
            if subsection:
                start, stop = subsection[1]
                lines = file_lines[start:stop]
                #remove empty lines
                lines = list(filter(lambda x: x, lines))
                return lines
            else:
                return []
              
        self.added_lines = find_subsection(UnreleasedSection.ADDED_SUBSECTION)
        self.changed_lines = find_subsection(UnreleasedSection.CHANGED_SUBSECTION)
        self.deprecated_lines = find_subsection(UnreleasedSection.DEPRECATED_SUBSECTION)
        self.removed_lines = find_subsection(UnreleasedSection.REMOVED_SUBSECTION)
        self.fixed_lines = find_subsection(UnreleasedSection.FIXED_SUBSECTION)
        self.security_lines = find_subsection(UnreleasedSection.SECURITY_SUBSECTION)
        
        
    def add_line(self, list, section_name, message):
        if not list:
            list.append(section_name)
        list.append(' - {}'.format(message))
        
    def add(self, message):
        self.add_line(self.added_lines, UnreleasedSection.ADDED_SUBSECTION, message)
        
    def change(self, message):
        self.add_line(self.changed_lines, UnreleasedSection.CHANGED_SUBSECTION, message)
        
    def deprecate(self, message):
        self.add_line(self.deprecated_lines, UnreleasedSection.DEPRECATED_SUBSECTION, message)
        
    def remove(self, message):
        self.add_line(self.removed_lines, UnreleasedSection.REMOVED_SUBSECTION, message)
        
    def fix(self, message):
        self.add_line(self.fixed_lines, UnreleasedSection.FIXED_SUBSECTION, message)
        
    def security(self, message):
        self.add_line(self.security_lines, UnreleasedSection.SECURITY_SUBSECTION, message)
        

    def subsection(self, lines):
        lines.append('')
        return lines
        
    def all_lines(self):
        all = [self.added_lines, self.changed_lines, self.deprecated_lines, self.removed_lines, self.fixed_lines, self.security_lines]
        
        def combine(acc, elem):
            if elem:
                return acc + self.subsection(elem)
            else:
                return acc
                
        return self.header + reduce(combine, all, [])
        
 
class EditableChangelog:
    def __init__(self):
        file_lines = []
        with open(file_path(CHANGELOG_FILE_NAME)) as fh:
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
            self.relases_footnotes = list(filter(lambda x: re.match(RELEASE_FOOTNOTE_REGEX, x), file_lines))
            release_footnotes_indexes = lines_to_indexes(file_lines, self.relases_footnotes)
            sections_indexes.append(release_footnotes_indexes[0]) # add first footnote to build last pair
            pairs = pairwise(sections_indexes)
            
            # Build sections objects with all sections (including unreleased)
            self.closed_sections = list(map(lambda tuple: Section(file_lines, tuple[0], tuple[1]), pairs))
            self.all_sections = self.closed_sections.copy()
            self.unreleased_section = UnreleasedSection(file_lines, unreleased_index, sections_indexes[0])
            self.all_sections.insert(0, self.unreleased_section)
            
    
    def close(self):
        all_lines = []
        all_lines.append(self.header)
        all_lines.append(self.unreleased_section.all_lines())
        for section in self.closed_sections:
            all_lines.append(section.lines)
        all_lines.append(self.relases_footnotes)
        
        # TODO: write to file
        print()
        for sublist in all_lines:
            for item in sublist:
                print(item)
    

def file_path(file_name):
    return PROJECT_ROOT_DIR + file_name

def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

def exit_existing_version(intended_version, latest_version):
    exit('\n* Version {} already exists in changelog file -> Latest version: {}'.format(intended_version, latest_version))
    
def lines_to_indexes(file_lines, lines):
    return list(map(lambda x: file_lines.index(x), lines))
 
def edit_changelog(func):
    changelog = EditableChangelog()
    func(changelog.unreleased_section)
    changelog.close()
    
def add(args):
    edit_changelog(lambda c: c.add(args.message))
def change(args):
    edit_changelog(lambda c: c.change(args.message))
def deprecate(args):
    edit_changelog(lambda c: c.deprecate(args.message))    
def remove(args):
    edit_changelog(lambda c: c.remove(args.message))
def fix(args):
    edit_changelog(lambda c: c.fix(args.message))
def security(args):
    edit_changelog(lambda c: c.security(args.message))

def release(args):
    changelog = Changelog(file_path(CHANGELOG_FILE_NAME), args.version_number)
    repository = Repository()

    if args.version_number in changelog.existing_versions:
        exit_existing_version(changelog.next_version, changelog.latest_version())

    print('Target release version: {}'.format(changelog.next_version))
    #close release tag
    changelog.close_release_section(repository)
    
    print('\nDone!')
    
def main():
    parser = argparse.ArgumentParser(description='Performs operations on CHANGELOG file')#Close release in CHANGELOG')
    subparsers = parser.add_subparsers()
    
    #create the parser for the "release" command
    parser_release = subparsers.add_parser('release')
    parser_release.add_argument('version_number', metavar='version', type=str, help='release version number')
    parser_release.set_defaults(func=release)
    
    #create the parser for the "add" command
    parser_release = subparsers.add_parser('add')
    parser_release.add_argument('message', metavar='message', type=str, help='message of added section')
    parser_release.set_defaults(func=add)
    
    #create the parser for the "change" command
    parser_release = subparsers.add_parser('change')
    parser_release.add_argument('message', metavar='message', type=str, help='message of changed section')
    parser_release.set_defaults(func=change)
    
    #create the parser for the "deprecate" command
    parser_release = subparsers.add_parser('deprecate')
    parser_release.add_argument('message', metavar='message', type=str, help='message of deprecated section')
    parser_release.set_defaults(func=deprecate)
    
    #create the parser for the "remove" command
    parser_release = subparsers.add_parser('remove')
    parser_release.add_argument('message', metavar='message', type=str, help='message of removed section')
    parser_release.set_defaults(func=remove)
    
    #create the parser for the "fix" command
    parser_release = subparsers.add_parser('fix')
    parser_release.add_argument('message', metavar='message', type=str, help='message of fixed section')
    parser_release.set_defaults(func=fix)
    
    #create the parser for the "security" command
    parser_release = subparsers.add_parser('security')
    parser_release.add_argument('message', metavar='message', type=str, help='message of security section')
    parser_release.set_defaults(func=security)
    
    args = parser.parse_args()
    args.func(args)
    
    
# Standard boilerplate to call the main() function to begin the program.
if __name__ == '__main__':
    main()


