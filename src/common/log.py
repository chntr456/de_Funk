import logging, sys
def get_logger(name: str, level: str = "INFO"):
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        lg.addHandler(h)
    lg.setLevel(level.upper())
    return lg
