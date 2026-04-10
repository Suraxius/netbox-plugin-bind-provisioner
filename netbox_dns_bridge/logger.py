import logging

PLUGIN_NAME = "dns-bridge"

def get_logger(name: str) -> logging.Logger:
    #name = name.replace("_","-").rsplit(".", 1)[-1]
    #
    #if name.startswith(PLUGIN_NAME):
    #    return logging.getLogger(name)
    #return logging.getLogger(f"{PLUGIN_NAME}.{name}")
    return logging.getLogger(f"{PLUGIN_NAME}")
