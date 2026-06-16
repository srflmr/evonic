"""
FastContext skill install/uninstall script.
"""
import os


def install(context: dict) -> dict:
    return {'success': True, 'message': 'FastContext skill installed successfully.'}


def uninstall(context: dict) -> dict:
    return {'success': True, 'message': 'FastContext skill uninstalled successfully.'}
