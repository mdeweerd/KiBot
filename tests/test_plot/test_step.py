"""
Tests of Printing Schematic files

We test:
- STEP for bom.kicad_pcb

For debug information use:
pytest-3 --log-cli-level debug

"""

import os
import sys
# Look for the 'utils' module from where the script is running
prev_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if prev_dir not in sys.path:
    sys.path.insert(0, prev_dir)
# Utils import
from utils import context

STEP_DIR = '3D'
# STEP_FILE = 'bom.step'


def test_step_1(test_dir):
    prj = 'bom'
    ctx = context.TestContext(test_dir, 'STEP_1', prj, 'step_simple', STEP_DIR)
    ctx.run()
    # Check all outputs are there
    name = os.path.join(STEP_DIR, prj+'-3D.step')
    ctx.expect_out_file(name)
    # Check the R and C 3D models are there
    ctx.search_in_file(name, ['R_0805_2012Metric', 'C_0805_2012Metric'])
    ctx.search_err(['Missing 3D model for R1: `(.*)R_0805_2012Metrico.wrl`',
                    'Failed to download `(.*)R_0805_2012Metrico.wrl`'])
    ctx.clean_up()


def test_step_2(test_dir):
    prj = 'bom_fake_models'
    ctx = context.TestContext(test_dir, 'STEP_2', prj, 'step_simple_2', STEP_DIR)
    ctx.run()
    # Check all outputs are there
    ctx.expect_out_file(os.path.join(STEP_DIR, prj+'-3D.step'))
    ctx.clean_up()


def test_step_3(test_dir):
    prj = 'bom'
    ctx = context.TestContext(test_dir, 'STEP_3', prj, 'step_simple_3', STEP_DIR)
    ctx.run()
    # Check all outputs are there
    ctx.expect_out_file(os.path.join(STEP_DIR, prj+'.step'))
    ctx.clean_up()


def test_step_variant_1(test_dir):
    prj = 'kibom-variant_3'
    ctx = context.TestContext(test_dir, 'test_step_variant_1', prj, 'step_variant_1', '')
    ctx.run(extra_debug=True)
    # Check all outputs are there
    ctx.expect_out_file(prj+'-3D.step')
    ctx.clean_up(keep_project=True)

def test_step_variant_2(test_dir):
    prj = 'kibom-variant_4'
    ctx = context.TestContext(test_dir, 'test_step_variant_2', prj, 'step_variant_2', '')
    ctx.run(extra_debug=True)
    # Check all outputs are there
    ctx.expect_out_file(prj+'-3D.step')
    ctx.clean_up(keep_project=True)
