def getVersionInfo() -> dict:
    retDict = {}

    import platform

    # Commented out to prevent GUI imports in core module (causes multiprocessing issues)
    # import nicegui
    # import kymflow.core as kymflow_core
    # import kymflow.gui_v2 as kymflow_gui
    import kymflow.core as kymflow_core
    from kymflow.core.user_config import UserConfig

    from kymflow.core.utils.logging import get_log_file_path

    # retDict['SanPy version'] = __version__
    retDict["KymFlow Core version"] = kymflow_core.__version__  # noqa
    # retDict["KymFlow GUI version"] = kymflow_gui.__version__  # noqa
    retDict["KymFlow GUI version"] = "N/A (GUI not imported in core)"  # GUI import commented out
    retDict["Python version"] = platform.python_version()
    retDict["Python platform"] = platform.machine()  # platform.platform()
    # retDict["NiceGUI version"] = nicegui.__version__
    retDict["NiceGUI version"] = "N/A (GUI not imported in core)"  # GUI import commented out
    retDict["User Config"] = str(UserConfig.default_config_path())
    retDict["Log file"] = str(get_log_file_path())
    # retDict['PyQt version'] = QtCore.__version__  # when using import qtpy
    # retDict['Bundle folder'] = sanpy._util.getBundledDir()
    # retDict['Log file'] = sanpy.sanpyLogger.getLoggerFile()
    retDict["GitHub"] = "https://github.com/mapmanager/kymflow"
    # retDict['Documentation'] = 'https://cudmore.github.io/SanPy/'
    retDict["email"] = "robert.cudmore@gmail.com"

    return retDict
