

def convert_baostock_to_phoenix_schema(param_name, param_val):
    if param_name == "frequency":
        mapping = {
            "d": "daily",
            "w": "weekly",
            "m": "monthly",
            "5": "5min",
            "15": "15min",
            "30": "30min",
            "60": "60min"
        }
        return mapping.get(param_val)
    elif param_name == "adjustflag":
        mapping = {
            "1": "hfq",
            "2": "qfq",
            "3": "nf"
        }
        return mapping.get(param_val)
    return None