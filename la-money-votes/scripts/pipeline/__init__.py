"""Shared library for the la-money-votes data pipeline.

Kept dependency-light on purpose: everything here is Python standard library
only (json, re, datetime, urllib, dataclasses). No third-party packages are
required to build or validate data.
"""
