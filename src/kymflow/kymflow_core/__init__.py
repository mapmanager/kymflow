from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("kymflow")
except PackageNotFoundError:  # running from source without install
    __version__ = "0.0.0+local"
