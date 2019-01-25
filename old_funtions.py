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


def release(args):
    changelog = Changelog(file_path(CHANGELOG_FILE_NAME), args.version_number)
    repository = Repository()

    if args.version_number in changelog.existing_versions:
        exit_existing_version(changelog.next_version, changelog.latest_version())

    print('Target release version: {}'.format(changelog.next_version))
    #close release tag
    changelog.close_release_section(repository)
    
    print('\nDone!')