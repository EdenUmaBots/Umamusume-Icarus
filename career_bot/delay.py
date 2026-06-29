import random
import time
import os

# Per-install timing seed so the dna_* jitter is consistent across runs on a
# given machine. (The old endpoint-pacing engine -- simulate_delay /
# simulate_turn_delay / GateKeeper -- was removed in v2.1; the live delay path
# lives in main.py's attach_turn_delay / wait_for_game_turn_delay.)
_dna_path = os.path.join(os.path.dirname(__file__), '.timing_dna')
if not os.path.exists(_dna_path):
    with open(_dna_path, 'w') as f:
        f.write(str(random.randint(1000000, 9999999)))

with open(_dna_path, 'r') as f:
    _dna_seed = int(f.read().strip())

_dna_rng = random.Random(_dna_seed)

# Set True to disable all dna_* pacing sleeps (honored by dna_sleep).
GLOBAL_DELAYS_DISABLED = False


def dna_randint(min_val, max_val):
    return _dna_rng.randint(min_val, max_val)


def dna_sleep(min_val, max_val, mean=None, stddev=None):
    if GLOBAL_DELAYS_DISABLED:
        return 0.0
    if mean is not None and stddev is not None:
        dt = max(min_val, min(max_val, _dna_rng.gauss(mean, stddev)))
    else:
        dt = _dna_rng.uniform(min_val, max_val)
    time.sleep(dt)
    return dt


def dna_uniform(min_val, max_val):
    return _dna_rng.uniform(min_val, max_val)


def dna_gauss(mean, stddev):
    return _dna_rng.gauss(mean, stddev)
