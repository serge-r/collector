# Base settings for collector app

# Directory, with TextFSM templates and index file
TEMPLATES_DIRECTORY = 'collector/cli_templates'

# MAX mtu for interfaces
MAX_MTU = 32767

# FILE to LOG
LOGFILE = "/var/log/netbox/netbox.log"

# LOGLEVEL
LOGLEVEL = 'DEBUG'

# Configuration for logging
# For change it - See Django documantation
# Now set as debug logginng
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(asctime)s %(levelname)s %(filename)s[Line:%(lineno)d] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
        'logfile': {
            'class': 'logging.FileHandler',
            'filename': LOGFILE,
            'formatter': 'console',
        },
    },
    'loggers': {
        'collector': {
            'level': LOGLEVEL,
            'handlers': ['console', 'logfile'],
        },
    },
}
