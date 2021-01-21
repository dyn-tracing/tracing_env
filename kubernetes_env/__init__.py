from pathlib import Path
import sys

# avoid annoying import errors...
# this is necessary to support location independent imports
FILE_DIR = Path.resolve(Path(__file__)).parent
sys.path.append(str(FILE_DIR))
