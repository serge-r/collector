''' This is a settings file
	!
'''
# Directory, with TextFSM templates and index file
TEMPLATES_DIRECTORY = 'collector/cli_templates'

# Configuration for logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            # exact format is not important, this is the minimum information
            'format': '%(asctime)s %(levelname)s %(filename)s[Line:%(lineno)d] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
    },
    'loggers': {
        'collector': {
            'level': 'INFO',
            'handlers': ['console'],
        },
    },
}