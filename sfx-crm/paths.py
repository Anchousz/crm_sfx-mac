# -*- coding: utf-8 -*-
"""Пути приложения: где хранить данные и искать ресурсы."""
import os
import subprocess
import sys

APP_NAME = "SFX CRM"
IS_MAC = sys.platform == "darwin"


def is_frozen():
    return getattr(sys, "frozen", False)


def app_dir():
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _user_data_base():
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support")
    return os.environ.get("APPDATA", app_dir())


def data_dir():
    base = app_dir()
    if is_frozen() and not os.path.exists(os.path.join(base, "crm.db")):
        base = os.path.join(_user_data_base(), APP_NAME)
        os.makedirs(base, exist_ok=True)
    return base


def open_path(path):
    if IS_MAC:
        subprocess.Popen(["open", path])
    else:
        os.startfile(path)


def resource(*parts):
    base = getattr(sys, "_MEIPASS", None) or app_dir()
    return os.path.join(base, *parts)


def logo_path():
    for base in (data_dir(), app_dir()):
        p = os.path.join(base, "logo.png")
        if os.path.exists(p):
            return p
    return None