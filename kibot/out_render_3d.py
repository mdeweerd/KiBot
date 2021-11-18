# -*- coding: utf-8 -*-
# Copyright (c) 2021 Salvador E. Tropea
# Copyright (c) 2021 Instituto Nacional de Tecnología Industrial
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
import os
from glob import glob
from shutil import rmtree
from .misc import CMD_PCBNEW_3D, URL_PCBNEW_3D, RENDER_3D_ERR
from .gs import (GS)
from .kiplot import check_script, exec_with_retry, add_extra_options
from .out_base_3d import Base3DOptions, Base3D
from .macros import macros, document, output_class  # noqa: F401
from . import log

logger = log.get_logger(__name__)


class Render3DOptions(Base3DOptions):
    _colors = {'background1': 'bg_color_1',
               'background2': 'bg_color_2',
               'copper': 'copper_color',
               'board': 'board_color',
               'silk': 'silk_color',
               'solder_mask': 'sm_color',
               'solder_paste': 'sp_color'}
    _views = {'top': 'z', 'bottom': 'Z', 'front': 'y', 'rear': 'Y', 'right': 'x', 'left': 'X'}
    _rviews = {v: k for k, v in _views.items()}

    def __init__(self):
        with document:
            self.output = GS.def_global_output
            """ Name for the generated image file (%i='3D_$VIEW' %x='png') """
            self.no_tht = False
            """ Used to exclude 3D models for through hole components """
            self.no_smd = False
            """ Used to exclude 3D models for surface mount components """
            self.background1 = "#66667F"
            """ First color for the background gradient """
            self.background2 = "#CCCCE5"
            """ Second color for the background gradient """
            self.board = "#332B16"
            """ Color for the board without copper or solder mask """
            self.copper = "#B29C00"
            """ Color for the copper """
            self.silk = "#E5E5E5"
            """ Color for the silk screen """
            self.solder_mask = "#143324"
            """ Color for the solder mask """
            self.solder_paste = "#808080"
            """ Color for the solder paste """
            self.move_x = 0
            """ Steps to move in the X axis, positive is to the right.
                Just like pressing the right arrow in the 3D viewer """
            self.move_y = 0
            """ Steps to move in the Y axis, positive is up.
                Just like pressing the up arrow in the 3D viewer """
            self.ray_tracing = False
            """ Enable the ray tracing. Much better result, but slow, and you'll need to adjust `wait_rt` """
            self.wait_ray_tracing = 5
            """ How many seconds we must wait before capturing the ray tracing render.
                Lamentably KiCad can save an unfinished image. Enlarge it if your image looks partially rendered """
            self.view = 'top'
            """ [top,bottom,front,rear,right,left,z,Z,y,Y,x,X] Point of view """
            self.zoom = 0
            """ Zoom steps. Use positive to enlarge, get closer, and negative to reduce.
                Same result as using the mouse wheel in the 3D viewer """
            self.width = 1280
            """ Image width (aprox.) """
            self.height = 720
            """ Image height (aprox.) """
            self.orthographic = False
            """ Enable the orthographic projection mode (top view looks flat) """
            self.id_add = ''
            """ Text to add to the %i expansion content. To differentiate variations of this output """
        super().__init__()
        self._expand_ext = 'png'

    def config(self, parent):
        super().config(parent)
        self.validate_colors(self._colors.keys())
        view = self._views.get(self.view, None)
        if view is not None:
            self.view = view
        self._expand_id += '_'+self._rviews.get(self.view)+self.id_add

    def run(self, output):
        super().run(output)
        check_script(CMD_PCBNEW_3D, URL_PCBNEW_3D, '1.5.11')
        # Base command with overwrite
        cmd = [CMD_PCBNEW_3D, '--rec_w', str(self.width+2), '--rec_h', str(self.height+85),
               '3d_view', '--output_name', output]
        # Add user options
        if not self.no_virtual:
            cmd.append('--virtual')
        if self.no_tht:
            cmd.append('--no_tht')
        if self.no_smd:
            cmd.append('--no_smd')
        for color, option in self._colors.items():
            cmd.extend(['--'+option, getattr(self, color)])
        if self.move_x:
            cmd.extend(['--move_x', str(self.move_x)])
        if self.move_y:
            cmd.extend(['--move_y', str(self.move_y)])
        if self.zoom:
            cmd.extend(['--zoom', str(self.zoom)])
        if self.wait_ray_tracing != 5:
            cmd.extend(['--wait_rt', str(self.wait_ray_tracing)])
        if self.ray_tracing:
            cmd.append('--ray_tracing')
        if self.orthographic:
            cmd.append('--orthographic')
        if self.view != 'z':
            cmd.extend(['--view', self.view])
        # The board
        board_name = self.filter_components(GS.pcb_dir)
        cmd.extend([board_name, os.path.dirname(output)])
        cmd, video_remove = add_extra_options(cmd)
        # Execute it
        ret = exec_with_retry(cmd)
        # Remove the temporal PCB
        if board_name != GS.pcb_file:
            # KiCad likes to create project files ...
            for f in glob(board_name.replace('.kicad_pcb', '.*')):
                os.remove(f)
        # Remove the downloaded 3D models
        if self._tmp_dir:
            rmtree(self._tmp_dir)
        if ret:
            logger.error(CMD_PCBNEW_3D+' returned %d', ret)
            exit(RENDER_3D_ERR)
        if video_remove:
            video_name = os.path.join(GS.out_dir, 'pcbnew_3d_view_screencast.ogv')
            if os.path.isfile(video_name):
                os.remove(video_name)


@output_class
class Render_3D(Base3D):  # noqa: F821
    """ 3D render of the PCB
        Exports the image generated by KiCad's 3D viewer. """
    def __init__(self):
        super().__init__()
        with document:
            self.options = Render3DOptions
            """ [dict] Options for the `render_3d` output """
