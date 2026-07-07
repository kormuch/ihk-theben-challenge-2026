"""
Product family definitions with their expected attributes (attribute_schema).
The schema defines which fields are relevant for this family —
it does not enforce them, but the UI can use it for completeness checks.
"""

FAMILIES = [
    {
        "name": "Unsorted",
        "description": "Holding family for imported or AI-extracted products that need manual classification",
        "attribute_schema": {},
    },
    {
        "name": "Timer",
        "description": "Analog and digital timers for residential and industrial installation",
        "attribute_schema": {
            "voltage": {"type": "string", "label": "Rated Voltage", "unit": "V", "required": True},
            "switching_capacity": {"type": "string", "label": "Switching Capacity", "unit": "W", "required": True},
            "switching_cycles_per_day": {"type": "integer", "label": "Switching Cycles/Day", "required": False},
            "accuracy": {"type": "string", "label": "Accuracy", "unit": "s/day", "required": False},
            "protection_class": {"type": "string", "label": "Protection Class (IP)", "required": True},
            "module_width": {"type": "string", "label": "Module Width", "unit": "MW", "required": False},
            "certifications": {"type": "list", "label": "Certifications", "required": True},
            "rohs_compliant": {"type": "boolean", "label": "RoHS Compliant", "required": True},
            "operating_temperature": {"type": "string", "label": "Operating Temperature", "unit": "°C", "required": False},
            "launch_date": {"type": "date", "label": "Launch Date", "required": False},
        },
    },
    {
        "name": "Motion Sensor",
        "description": "Presence and motion detectors for indoor and outdoor use",
        "attribute_schema": {
            "voltage": {"type": "string", "label": "Operating Voltage", "unit": "V", "required": True},
            "detection_angle": {"type": "integer", "label": "Detection Angle", "unit": "°", "required": True},
            "range": {"type": "string", "label": "Range", "unit": "m", "required": True},
            "switching_capacity": {"type": "string", "label": "Max Switching Capacity", "unit": "W", "required": True},
            "follow_up_time": {"type": "string", "label": "Follow-up Time", "required": False},
            "light_threshold": {"type": "string", "label": "Light Threshold", "unit": "Lux", "required": False},
            "protection_class": {"type": "string", "label": "Protection Class (IP)", "required": True},
            "mounting": {"type": "string", "label": "Mounting Type", "required": True},
            "certifications": {"type": "list", "label": "Certifications", "required": True},
            "rohs_compliant": {"type": "boolean", "label": "RoHS Compliant", "required": True},
            "reach_compliant": {"type": "boolean", "label": "REACH Compliant", "required": False},
            "launch_date": {"type": "date", "label": "Launch Date", "required": False},
        },
    },
    {
        "name": "Room Thermostat",
        "description": "Electronic room thermostats for heating, cooling, and ventilation control",
        "attribute_schema": {
            "voltage": {"type": "string", "label": "Operating Voltage", "unit": "V", "required": True},
            "temperature_range": {"type": "string", "label": "Control Range", "unit": "°C", "required": True},
            "switching_differential": {"type": "string", "label": "Switching Differential", "unit": "K", "required": False},
            "output": {"type": "string", "label": "Output Type", "required": True},
            "display": {"type": "boolean", "label": "Display", "required": False},
            "knx_capable": {"type": "boolean", "label": "KNX Capable", "required": False},
            "protection_class": {"type": "string", "label": "Protection Class (IP)", "required": True},
            "mounting_type": {"type": "string", "label": "Mounting Type", "required": True},
            "certifications": {"type": "list", "label": "Certifications", "required": True},
            "rohs_compliant": {"type": "boolean", "label": "RoHS Compliant", "required": True},
            "energy_efficiency_class": {"type": "string", "label": "Energy Efficiency Class", "required": False},
            "launch_date": {"type": "date", "label": "Launch Date", "required": False},
        },
    },
]
