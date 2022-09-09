# -*- coding: utf-8 -*-
# Copyright (c) 2020-2022 Salvador E. Tropea
# Copyright (c) 2020-2022 Instituto Nacional de Tecnología Industrial
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
import os
import requests
import tempfile
from .misc import W_MISS3D, W_FAILDL, DISABLE_3D_MODEL_TEXT
from .gs import GS
from .out_base import VariantOptions, BaseOutput
from .kicad.config import KiConf
from .macros import macros, document  # noqa: F401
from . import log

logger = log.get_logger()


class Base3DOptions(VariantOptions):
    def __init__(self):
        with document:
            self.no_virtual = False
            """ *Used to exclude 3D models for components with 'virtual' attribute """
            self.download = True
            """ *Downloads missing 3D models from KiCad git. Only applies to models in KISYS3DMOD """
            self.kicad_3d_url = 'https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/'
            """ Base URL for the KiCad 3D models """
        # Temporal dir used to store the downloaded files
        self._tmp_dir = None
        super().__init__()
        self._expand_id = '3D'

    def download_model(self, url, fname):
        """ Download the 3D model from the provided URL """
        logger.debug('Downloading `{}`'.format(url))
        r = requests.get(url, allow_redirects=True)
        if r.status_code != 200:
            logger.warning(W_FAILDL+'Failed to download `{}`'.format(url))
            return None
        if self._tmp_dir is None:
            self._tmp_dir = tempfile.mkdtemp()
            logger.debug('Using `{}` as temporal dir for downloaded files'.format(self._tmp_dir))
        dest = os.path.join(self._tmp_dir, fname)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(r.content)
        return dest

    def download_models(self):
        """ Check we have the 3D models.
            Inform missing models.
            Try to download the missing models
            Stores changes in self.undo_3d_models_rep """
        models_replaced = False
        # Load KiCad configuration so we can expand the 3D models path
        KiConf.init(GS.pcb_file)
        # List of models we already downloaded
        downloaded = set()
        extra_debug = GS.debug_level > 3
        # Look for all the footprints
        for m in GS.get_modules():
            ref = m.GetReference()
            # Extract the models (the iterator returns copies)
            models = m.Models()
            models_l = []
            while not models.empty():
                models_l.append(models.pop())
            # Look for all the 3D models for this footprint
            for m3d in models_l:
                if m3d.m_Filename.endswith(DISABLE_3D_MODEL_TEXT):
                    # Skip models we intentionally disabled using a bogus name
                    if extra_debug:
                        logger.debug("- Skipping {} (disabled)".format(m3d.m_Filename))
                    continue
                used_extra = [False]
                full_name = KiConf.expand_env(m3d.m_Filename, used_extra)
                if extra_debug:
                    logger.debug("- Expanded {} -> {}".format(m3d.m_Filename, full_name))
                if not os.path.isfile(full_name):
                    # Missing 3D model
                    if self.download and (m3d.m_Filename.startswith('${KISYS3DMOD}/') or
                                          m3d.m_Filename.startswith('${KICAD6_3DMODEL_DIR}/')):
                        # This is a model from KiCad, try to download it
                        fname = m3d.m_Filename[m3d.m_Filename.find('/')+1:]
                        replace = None
                        if full_name in downloaded:
                            # Already downloaded
                            replace = os.path.join(self._tmp_dir, fname)
                        else:
                            # Download the model
                            url = self.kicad_3d_url+fname
                            replace = self.download_model(url, fname)
                            if replace:
                                # Successfully downloaded
                                downloaded.add(full_name)
                                self.undo_3d_models[replace] = m3d.m_Filename
                                # If this is a .wrl also download the .step
                                if url.endswith('.wrl'):
                                    url = url[:-4]+'.step'
                                    fname = fname[:-4]+'.step'
                                    self.download_model(url, fname)
                        if replace:
                            m3d.m_Filename = replace
                            models_replaced = True
                    if full_name not in downloaded:
                        logger.warning(W_MISS3D+'Missing 3D model for {}: `{}`'.format(ref, full_name))
                else:  # File was found
                    if used_extra[0]:
                        # The file is there, but we got it expanding a user defined text
                        # This is completely valid for KiCad, but kicad2step doesn't support it
                        m3d.m_Filename = full_name
                        if not models_replaced and extra_debug:
                            logger.debug('- Modifying models with text vars')
                        models_replaced = True
            # Push the models back
            for model in models_l:
                models.push_front(model)
        return models_replaced

    def list_models(self):
        """ Get the list of 3D models """
        # Load KiCad configuration so we can expand the 3D models path
        KiConf.init(GS.pcb_file)
        models = set()
        # Look for all the footprints
        for m in GS.get_modules():
            # Look for all the 3D models for this footprint
            for m3d in m.Models():
                full_name = KiConf.expand_env(m3d.m_Filename)
                if os.path.isfile(full_name):
                    models.add(full_name)
        return list(models)

    def filter_components(self):
        if not self._comps:
            # No variant/filter to apply
            if self.download_models():
                # Some missing components found and we downloaded them
                # Save the fixed board
                ret = self.save_tmp_board()
                # Undo the changes done during download
                self.undo_3d_models_rename(GS.board)
                return ret
            return GS.pcb_file
        self.filter_pcb_components(GS.board, do_3D=True, do_2D=False)
        self.download_models()
        fname = self.save_tmp_board()
        self.unfilter_pcb_components(GS.board, do_3D=True, do_2D=False)
        return fname

    def get_targets(self, out_dir):
        return [self._parent.expand_filename(out_dir, self.output)]


class Base3D(BaseOutput):
    def __init__(self):
        super().__init__()

    def get_dependencies(self):
        files = super().get_dependencies()
        files.extend(self.options.list_models())
        return files
