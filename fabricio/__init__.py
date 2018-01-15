from fabricio.operations import local, log, move_file, remove_file, run
from fabricio.operations import Error, host_errors
from fabricio.decorators import skip_unknown_host, once_per_task
from fabricio.tasks import infrastructure

VERSION = (0, 5, 3)

__version__ = '.'.join(map(str, VERSION))
