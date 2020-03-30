import re

import yaml


def wallpost_check(wall_text):
    """Метод для определения тегов в тексте на стене"""
    p = re.findall('(?:\s|^)#[A-Za-z0-9\-\.\_]+(?:\s|$)', wall_text)
    return [e.replace(" ", "") for e in p]


def get_settings():
    """Чтение настроек с yaml"""
    with open("./yaml/settings.yml", 'r') as stream:
        return yaml.safe_load(stream)
