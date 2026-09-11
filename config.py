from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

PORTS_FILE = DATA_DIR / "ports.json"
STATIONS_FILE = DATA_DIR / "stations.json"
VESSELS_FILE = DATA_DIR / "vessels.json"
ROUTES_FILE = DATA_DIR / "routes.json"


# ============================================================
# SIMULATION SETTINGS
# ============================================================

# Default safety buffer before a resource reaches
# its critical threshold.
DEFAULT_SAFETY_BUFFER_DAYS = 3.0

# Default simulation speed.
#
# 1.0  = real-time
# 10.0 = 10 simulation hours for every real hour
# etc.
DEFAULT_SIMULATION_SPEED = 1.0


# ============================================================
# NAVIGATION SETTINGS
# ============================================================

# Conversion constants.
KILOMETRES_PER_NAUTICAL_MILE = 1.852
NAUTICAL_MILES_PER_KILOMETRE = 1 / KILOMETRES_PER_NAUTICAL_MILE

# Earth radius used for haversine calculations.
EARTH_RADIUS_KM = 6371.0088


# ============================================================
# OPTIMIZER SETTINGS
# ============================================================

DEFAULT_MAX_ALTERNATIVES = 3

# Minimum acceptable cargo weight.
MIN_CARGO_WEIGHT_TONNES = 0.0


# ============================================================
# RESOURCE SETTINGS
# ============================================================

# Prevent invalid negative inventory values.
MIN_RESOURCE_QUANTITY = 0.0

# Prevent negative consumption rates.
MIN_DAILY_CONSUMPTION = 0.0


# ============================================================
# DEVELOPMENT / DEMO SETTINGS
# ============================================================

PROJECT_NAME = (
    "Antarctic Maritime Resupply Navigation Simulator"
)

PROJECT_VERSION = "0.1.0"

DATA_SOURCE_STATUS = "SIMULATED"


# ============================================================
# SAFETY
# ============================================================

# These are simulation-level safety defaults.
#
# They are NOT real Antarctic operational limits.
# Real operational constraints should come from
# authoritative MoES/NCPOR/ship/operator data later.

ENABLE_SAFETY_CHECKS = True

REQUIRE_FUEL_CAPACITY_CHECK = True

REQUIRE_CARGO_CAPACITY_CHECK = True

REQUIRE_VESSEL_AVAILABILITY_CHECK = True

REQUIRE_ROUTE_MATCH_CHECK = True