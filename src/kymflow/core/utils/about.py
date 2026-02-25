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
    # retDict["NiceGUI version"] = nicegui.__version__
    retDict["NiceGUI version"] = "N/A (GUI not imported in core)"  # GUI import commented out

    retDict["Python version"] = platform.python_version()
    retDict["System"] = platform.system()
    retDict["Release"] = platform.release()
    retDict["Machine"] = platform.machine()
    retDict["Processor"] = platform.processor()

    
    # get build info
    from kymflow.build_info import get_build_info
    build_info = get_build_info()
    # version_info["Build info"] = build_info
    for key, value in build_info.items():
        retDict[key] = value

    _user_config_file = UserConfig.default_config_path()
    _user_config_path = _user_config_file.parent
    # _link = f'<a href="file://{_user_config_path}">{_user_config_path}</a>'
    # retDict["User Config"] = str(_link)
    # _link = f'file://{_user_config_path}'
    # retDict["User Config"] = _link
    retDict["User Config"] = str(_user_config_path)
    
    # retDict["Log file"] = str(get_log_file_path())

    # retDict['PyQt version'] = QtCore.__version__  # when using import qtpy
    # retDict['Bundle folder'] = sanpy._util.getBundledDir()
    # retDict['Log file'] = sanpy.sanpyLogger.getLoggerFile()
    # retDict["GitHub"] = "https://github.com/mapmanager/kymflow"
    # retDict['Documentation'] = 'https://cudmore.github.io/SanPy/'
    retDict["email"] = "robert.cudmore@gmail.com"

    return retDict
