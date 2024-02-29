import yaml
import os

def load_config():
    config = {}
    with open('config/config.yaml', 'r') as f:
        config.update(yaml.safe_load(f))
    return config