from core4.config.pragma import connect


mongo_url = "mongodb://localhost:27017"  # default mongo connection
mongo_database = "core4dev"  # default mongo database

# system collections
sys = {
    "conf": None,
    "log": connect("mongodb://sys.log"),
    "role": connect("mongodb://sys.role"),
    "quota": connect("mongodb://sys.quota")
}

# system folders
folder = {
    'root': '/srv/core4',
    'transfer': 'transfer',
    'process': 'proc',
    'archive': 'arch',
    'location': 'api/location',
    'upstream': 'api/upstream',
    'vassal': 'api/vassal',
    'temp': 'temp'
}

# logging setup
logging = {
    "stderr": "DEBUG",
    "stdout": None,
    "mongodb": "INFO",
    "format": "%(asctime)s "
              "- %(levelname)-8s "
              "[%(qual_name)s/%(identifier)s] "
              "%(message)s",
    "exception": {
        "capacity": 1000
    },
    "extra": None
}