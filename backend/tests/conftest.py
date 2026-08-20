import os
import sys

# Tests run against the backend package layout (dominoes/, bots/) the same way
# uvicorn does, so put the backend root on the path rather than requiring an
# editable install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
