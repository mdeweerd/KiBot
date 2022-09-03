# -*- coding: utf-8 -*-
# Copyright (c) 2022 Salvador E. Tropea
# Copyright (c) 2022 Instituto Nacional de Tecnología Industrial
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
"""
Dependencies:
  - name: KiCad PCB/SCH Diff
    version: 2.4.1
    role: mandatory
    github: INTI-CMNB/KiDiff
    command: kicad-diff.py
    pypi: kidiff
    downloader: pytool
    id: KiDiff
  - from: Git
    role: Compare with files in the repo
  - from: KiAuto
    role: Compare schematics
    version: 2.0.0
"""
from hashlib import sha1
import os
import shlex
from shutil import rmtree, copy2
from subprocess import run, CalledProcessError, STDOUT, PIPE
from tempfile import mkdtemp, NamedTemporaryFile
from .error import KiPlotConfigurationError
from .gs import GS
from .kiplot import load_any_sch
from .layer import Layer
from .misc import FAILED_EXECUTE
from .optionable import BaseOptions
from .macros import macros, document, output_class  # noqa: F401
from . import log

logger = log.get_logger()
STASH_MSG = 'KiBot_Changes_Entry'


def debug_output(res):
    if res.stdout:
        logger.debug('- Output from command: '+res.stdout.decode())


def run_command(command, change_to=None):
    logger.debug('Executing: '+shlex.join(command))
    try:
        res = run(command, check=True, stdout=PIPE, stderr=STDOUT, cwd=change_to)
    except CalledProcessError as e:
        logger.error('Running {} returned {}'.format(e.cmd, e.returncode))
        debug_output(e)
        exit(FAILED_EXECUTE)
    debug_output(res)
    return res.stdout.decode().rstrip()


class DiffOptions(BaseOptions):
    def __init__(self):
        with document:
            self.output = GS.def_global_output
            """ *Filename for the output (%i=diff_pcb/diff_sch, %x=pdf) """
            self.pcb = True
            """ Compare the PCB, otherwise compare the schematic """
            self.old = 'HEAD'
            """ Reference file. When using git use `HEAD` to refer to the last commit.
                Use `HEAD~` to refer the previous to the last commit.
                As `HEAD` is for the whole repo you can use `KIBOT_LAST-n` to make
                reference to the changes in the PCB/SCH. The `n` value is how many
                changes in the history you want to go back. A 0 is the same as `HEAD`,
                a 1 means the last time the PCB/SCH was changed, etc """
            self.old_type = 'git'
            """ [git,file] How to interpret the `old` name. Use `git` for a git hash, branch, etc.
                Use `file` for a file name """
            self.new = ''
            """ The file you want to compare. Leave it blank for the current PCB/SCH """
            self.new_type = 'file'
            """ [git,file] How to interpret the `new` name. Use `git` for a git hash, branch, etc.
                Use `file` for a file name """
            self.cache_dir = ''
            """ Directory to cache the intermediate files. Leave it blank to disable the cache """
            self.diff_mode = 'red_green'
            """ [red_green,stats] In the `red_green` mode added stuff is green and red when removed.
                The `stats` mode is used to meassure the amount of difference. In this mode all
                changes are red, but you can abort if the difference is bigger than certain threshold """
            self.fuzz = 5
            """ [0,100] Color tolerance (fuzzyness) for the `stats` mode """
            self.threshold = 0
            """ [0,1000000] Error threshold for the `stats` mode, 0 is no error. When specified a
                difference bigger than the indicated value will make the diff fail """
            self.add_link_id = False
            """ When enabled we create a symlink to the output file with a name that contains the
                git hashes involved in the comparison. If you plan to compress the output don't
                forget to disable the `follow_links` option """
            self.copy_instead_of_link = False
            """ When `copy_instead_of_link` is enabled creates a copy of the file instead of a symlink.
                Useful for some Windows setups """
        super().__init__()
        self._expand_id = 'diff'
        self._expand_ext = 'pdf'

    def config(self, parent):
        super().config(parent)
        self._expand_id = 'diff'+('_pcb' if self.pcb else '_sch')

    def get_targets(self, out_dir):
        return [self._parent.expand_filename(out_dir, self.output)]

    def get_digest(self, file_path, restart=True):
        logger.debug('Hashing '+file_path)
        if restart:
            self.h = sha1()
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(self.h.block_size)
                if not chunk:
                    break
                self.h.update(chunk)
        return self.h.hexdigest()

    def add_to_cache(self, name, hash):
        cmd = [self.command, '--only_cache', '--old_file_hash', hash, '--cache_dir', self.cache_dir]
        if self.incl_file:
            cmd.extend(['--layers', self.incl_file])
        if GS.debug_enabled:
            cmd.insert(1, '-'+'v'*GS.debug_level)
        cmd.extend([name, name])
        run_command(cmd)

    def cache_pcb(self, name):
        if name:
            if not os.path.isfile(name):
                raise KiPlotConfigurationError('Missing file to compare: `{}`'.format(name))
        else:
            GS.check_pcb()
            name = GS.pcb_file
        hash = self.get_digest(name)
        self.add_to_cache(name, hash)
        return hash

    def cache_sch(self, name):
        if name:
            if not os.path.isfile(name):
                raise KiPlotConfigurationError('Missing file to compare: `{}`'.format(name))
        else:
            GS.check_sch()
            name = GS.sch_file
        # Schematics can have sub-sheets
        sch = load_any_sch(name, os.path.splitext(os.path.basename(name))[0])
        files = sch.get_files()
        hash = self.get_digest(files[0])
        if len(files) > 1:
            for f in files[1:]:
                hash = self.get_digest(f, restart=False)
        hash = 'sch'+hash
        self.add_to_cache(name, hash)
        return hash

    def cache_file(self, name=None):
        return self.cache_pcb(name) if self.pcb else self.cache_sch(name)

    def run_git(self, cmd):
        return run_command([self.git_command]+cmd, change_to=self.repo_dir)

    def undo_git(self):
        if self.checkedout:
            logger.debug('Restoring point '+self.branch)
            self.run_git(['checkout', '--recurse-submodules', self.branch])
        if self.stashed:
            logger.debug('Restoring changes')
            # We don't know if we stashed anything (push always returns 0)
            # So we check that the last stash contains our message
            res = self.run_git(['stash', 'list', 'stash@{0}'])
            if STASH_MSG in res:
                self.run_git(['stash', 'pop', '--index'])

    def solve_git_name(self, name):
        ori = name
        if not name.startswith('KIBOT_LAST'):
            return name
        logger.debug('Finding '+name)
        # The magic KIBOT_LAST
        malformed = 'Malformed `KIBOT_LAST` value, must be `KIBOT_LAST-n`, not: '+ori
        name = name[10:]
        # How many changes?
        num = 0
        if name[0] != '-':
            raise KiPlotConfigurationError(malformed)
        try:
            num = int(name[1:])
        except ValueError:
            raise KiPlotConfigurationError(malformed)
        num = str(num)
        # Return its hash
        res = self.run_git(['log', '--pretty=format:%H', '--skip='+num, '-n', '1', '--', self.file])
        if not res:
            raise KiPlotConfigurationError("The `{}` doesn't resolve to a valid hash".format(ori))
        logger.debug('- '+res)
        return res

    def cache_git(self, name):
        self.stashed = False
        self.checkedout = False
        # Which file
        if self.pcb:
            GS.check_pcb()
            self.file = GS.pcb_file
        else:
            GS.check_sch()
            self.file = GS.sch_file
        # Place where we know we have a repo
        self.repo_dir = os.path.dirname(os.path.abspath(self.file))
        try:
            # Save current changes
            logger.debug('Saving current changes')
            self.run_git(['stash', 'push', '-m', STASH_MSG])
            self.stashed = True
            # Find the current branch
            self.branch = self.run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
            if self.branch == 'HEAD':
                # Detached
                self.branch = self.run_git(['rev-parse', 'HEAD'])
            logger.debug('Current branch is '+self.branch)
            # Checkout the target
            name = self.solve_git_name(name)
            logger.debug('Changing to '+name)
            self.run_git(['checkout', '--recurse-submodules', name])
            self.checkedout = True
            # A short version of the current hash
            self.git_hash = self.run_git(['rev-parse', '--short', 'HEAD'])
            # Populate the cache
            hash = self.cache_file()
        finally:
            self.undo_git()
        return hash

    def cache_obj(self, name, type):
        self.git_hash = 'None'
        return self.cache_git(name) if type == 'git' else self.cache_file(name), self.git_hash

    def create_layers_incl(self, layers):
        incl_file = None
        if self.pcb and not isinstance(layers, type):
            layers = Layer.solve(layers)
            logger.debug('Including layers:')
            with NamedTemporaryFile(mode='w', suffix='.lst', delete=False) as f:
                incl_file = f.name
                for la in layers:
                    logger.debug('- {} ({})'.format(la.layer, la.id))
                    f.write(str(la.id)+'\n')
        return incl_file

    def run(self, name):
        self.command = self.ensure_tool('KiDiff')
        if self.old_type == 'git' or self.new_type == 'git':
            self.git_command = self.ensure_tool('Git')
        if not self.pcb:
            # We need eeschema_do for this
            self.ensure_tool('KiAuto')
        # Solve the cache dir
        remove_cache = False
        if not self.cache_dir:
            self.cache_dir = mkdtemp()
            remove_cache = True
        # A valid name, not really used
        if self.pcb:
            GS.check_pcb()
            file = GS.pcb_file
        else:
            GS.check_sch()
            file = GS.sch_file
        dir_name = os.path.dirname(name)
        file_name = os.path.basename(name)
        self.incl_file = None
        try:
            # List of layers
            self.incl_file = self.create_layers_incl(self.layers)
            # Populate the cache
            old_hash, gh1 = self.cache_obj(self.old, self.old_type)
            new_hash, gh2 = self.cache_obj(self.new, self.new_type)
            # Compute the diff using the cache
            cmd = [self.command, '--no_reader', '--new_file_hash', new_hash, '--old_file_hash', old_hash,
                   '--cache_dir', self.cache_dir, '--output_dir', dir_name, '--output_name', file_name,
                   '--diff_mode', self.diff_mode, '--fuzz', str(self.fuzz)]
            if self.incl_file:
                cmd.extend(['--layers', self.incl_file])
            if self.threshold:
                cmd.extend(['--threshold', str(self.threshold)])
            cmd.extend([file, file])
            if GS.debug_enabled:
                cmd.insert(1, '-'+'v'*GS.debug_level)
            run_command(cmd)
            if self.add_link_id:
                name_comps = os.path.splitext(name)
                target = name_comps[0]+'_'+gh1+'-'+gh2+name_comps[1]
                if self.copy_instead_of_link:
                    copy2(name, target)
                else:
                    if os.path.isfile(target):
                        os.remove(target)
                    os.symlink(os.path.basename(name), target)
        finally:
            # Clean-up
            if remove_cache:
                rmtree(self.cache_dir)
            if self.incl_file:
                os.remove(self.incl_file)


@output_class
class Diff(BaseOutput):  # noqa: F821
    """ Diff
        Generates a PDF with the differences between two PCBs or schematics """
    def __init__(self):
        super().__init__()
        self._category = ['PCB/docs', 'Schematic/docs']
        self._both_related = True
        with document:
            self.options = DiffOptions
            """ *[dict] Options for the `diff` output """
            self.layers = Layer
            """ *[list(dict)|list(string)|string] [all,selected,copper,technical,user]
                List of PCB layers to use. When empty all available layers are used.
                Note that if you want to support adding/removing layers you should specify a list here """

    def run(self, name):
        self.options.layers = self.layers
        super().run(name)
