# -*- coding: utf-8 -*-
# Copyright (c) 2021 Salvador E. Tropea
# Copyright (c) 2021 Instituto Nacional de Tecnología Industrial
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
import re
import os
import glob
import sys
from sys import exit
from subprocess import check_output, STDOUT, CalledProcessError
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED, ZIP_BZIP2, ZIP_LZMA
from tarfile import open as tar_open
from collections import OrderedDict
from .gs import GS
from .kiplot import config_output, get_output_dir, run_output
from .misc import MISSING_TOOL, WRONG_INSTALL, W_EMPTYZIP, WRONG_ARGUMENTS, INTERNAL_ERROR
from .optionable import Optionable, BaseOptions
from .macros import macros, document, output_class  # noqa: F401
from . import log

logger = log.get_logger(__name__)


class FilesList(Optionable):
    def __init__(self):
        super().__init__()
        with document:
            self.source = '*'
            """ File names to add, wildcards allowed. Use ** for recursive match.
                Note this pattern is applied to the output dir specified with -d comman line option """
            self.from_output = ''
            """ Collect files from the selected output.
                When used the `source` option is ignored """
            self.filter = '.*'
            """ A regular expression that source files must match """
            self.dest = ''
            """ Destination directory inside the archive, empty means the same of the file """


class CompressOptions(BaseOptions):
    ZIP_ALGORITHMS = {'auto': ZIP_DEFLATED,
                      'stored': ZIP_STORED,
                      'deflated': ZIP_DEFLATED,
                      'bzip2': ZIP_BZIP2,
                      'lzma': ZIP_LZMA}
    TAR_MODE = {'auto': 'bz2',
                'stored': '',
                'deflated': 'gz',
                'bzip2': 'bz2',
                'lzma': 'xz'}

    def __init__(self):
        with document:
            self.output = GS.def_global_output
            """ Name for the generated archive (%i=name of the output %x=according to format) """
            self.format = 'ZIP'
            """ [ZIP,TAR,RAR] Output file format """
            self.compression = 'auto'
            """ [auto,stored,deflated,bzip2,lzma] Compression algorithm. Use auto to let KiBot select a suitable one """
            self.files = FilesList
            """ [list(dict)] Which files will be included """
        super().__init__()

    def config(self, parent):
        super().config(parent)
        if isinstance(self.files, type):
            self.files = []
            logger.warning(W_EMPTYZIP+'No files provided, creating an empty archive')
        self._expand_id = parent.name
        self._expand_ext = self.solve_extension()

    def create_zip(self, output, files):
        extra = {}
        extra['compression'] = self.ZIP_ALGORITHMS[self.compression]
        if sys.version_info.major > 3 or (sys.version_info.major == 3 and sys.version_info.minor >= 7):
            extra['compresslevel'] = 9
        with ZipFile(output, 'w', **extra) as zip:
            for fname, dest in files.items():
                logger.debug('Adding '+fname+' as '+dest)
                zip.write(fname, dest)

    def create_tar(self, output, files):
        with tar_open(output, 'w:'+self.TAR_MODE[self.compression]) as tar:
            for fname, dest in files.items():
                logger.debug('Adding '+fname+' as '+dest)
                tar.add(fname, dest)

    def create_rar(self, output, files):
        if os.path.isfile(output):
            os.remove(output)
        for fname, dest in files.items():
            logger.debug('Adding '+fname+' as '+dest)
            cmd = ['rar', 'a', '-m5', '-ep', '-ap'+os.path.dirname(dest), output, fname]
            try:
                check_output(cmd, stderr=STDOUT)
            except FileNotFoundError:
                logger.error('Missing `rar` command, install it')
                exit(MISSING_TOOL)
            except CalledProcessError as e:
                logger.error('Failed to invoke rar command, error {}'.format(e.returncode))
                if e.output:
                    logger.debug('Output from command: '+e.output.decode())
                exit(WRONG_INSTALL)

    def solve_extension(self):
        if self.format == 'ZIP':
            return 'zip'
        if self.format == 'RAR':
            return 'rar'
        # TAR
        ext = 'tar'
        sub_ext = self.TAR_MODE[self.compression]
        if sub_ext:
            ext += '.'+sub_ext
        return ext

    def get_files(self, output, no_out_run=False):
        output_real = os.path.realpath(output)
        files = OrderedDict()
        for f in self.files:
            # Get the list of candidates
            files_list = None
            if f.from_output:
                for out in GS.outputs:
                    if out.name == f.from_output:
                        config_output(out)
                        files_list = out.get_targets(get_output_dir(out.expand_dirname(out.dir), dry=True))
                        break
                if files_list is None:
                    logger.error('Unknown output `{}` selected in {}'.format(f.from_output, self._parent))
                    exit(WRONG_ARGUMENTS)
                if not no_out_run:
                    for file in files_list:
                        if not os.path.isfile(file):
                            # The target doesn't exist
                            if not out._done:
                                # The output wasn't created in this run, try running it
                                run_output(out)
                            if not os.path.isfile(file):
                                # Still missing, something is wrong
                                logger.error('Unable to generate `{}` from {}'.format(file, out))
                                exit(INTERNAL_ERROR)
            else:
                files_list = glob.iglob(os.path.join(GS.out_dir, f.source), recursive=True)
            # Filter and adapt them
            for fname in filter(re.compile(f.filter).match, files_list):
                fname_real = os.path.realpath(fname)
                # Avoid including the output
                if fname_real == output_real:
                    continue
                # Compute the destination directory inside the archive
                dest = fname
                if f.dest:
                    dest = os.path.join(f.dest, os.path.basename(fname))
                else:
                    dest = os.path.relpath(dest, GS.out_dir)
                files[fname_real] = dest
        return files

    def get_targets(self, out_dir):
        return [self._parent.expand_filename(out_dir, self.output)]

    def get_dependencies(self):
        output = self.get_targets(GS.out_dir)[0]
        files = self.get_files(output, no_out_run=True)
        return files.keys()

    def run(self, output):
        # Output file name
        logger.debug('Collecting files')
        # Collect the files
        files = self.get_files(output)
        logger.debug('Generating `{}` archive'.format(output))
        if self.format == 'ZIP':
            self.create_zip(output, files)
        elif self.format == 'TAR':
            self.create_tar(output, files)
        elif self.format == 'RAR':
            self.create_rar(output, files)


@output_class
class Compress(BaseOutput):  # noqa: F821
    """ Archiver (files compressor)
        Generates a compressed file containing output files.
        This is used to generate groups of files in compressed file format. """
    def __init__(self):
        super().__init__()
        with document:
            self.options = CompressOptions
            """ [dict] Options for the `compress` output """

    def get_dependencies(self):
        return self.options.get_dependencies()
