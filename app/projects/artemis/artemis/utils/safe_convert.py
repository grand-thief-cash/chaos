

# Helper to safely convert types
def safe_float(val):
    if not val: return 0.0
    try: return float(val)
    except ValueError: return 0.0

def safe_int(val):
    if not val: return 0
    try: return int(float(val))
    except ValueError: return 0