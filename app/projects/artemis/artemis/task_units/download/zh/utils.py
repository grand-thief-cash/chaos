

def convert_baostock_to_phoenix_schema(param_name, param_val):
    if param_name == "frequency":
        mapping = {
            "daily": "d",
            "weekly": "w",
            "monthly": "m",
            "5min": "5",
            "15min": "15",
            "30min": "30",
            "60min": "60",
        }
        return mapping.get(param_val)
    elif param_name == "adjustflag":
        mapping = {
            "hfq":"1",
            "qfq":"2",
            "nf":"3"
        }
        return mapping.get(param_val)
    return None