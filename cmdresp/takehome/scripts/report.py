"""Current report entry point; Run 1 generator is archived with its evidence."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('report_run2.py')),run_name='__main__')
