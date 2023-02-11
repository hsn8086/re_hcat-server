import logging
import subprocess
import sys

debug = '--debug' in sys.argv
logging.basicConfig(level=logging.DEBUG if debug else logging.INFO,
                    format='[%(asctime)s][%(filename)s(%(lineno)d)][%(levelname)s] %(message)s',
                    datefmt='%b/%d/%Y-%H:%M:%S')
try:
    from _main import main
except:
    logging.critical('The function "main" could not be loaded, please check if the file is complete.')
    sys.exit()

try:
    main()
except ModuleNotFoundError as err:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requirements.txt'])
    main()
except BaseException as err:
    logging.exception(err)

