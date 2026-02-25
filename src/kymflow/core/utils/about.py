def getVersionInfo() -> dict:
    retDict = {}

    import platform

    import kymflow.core as kymflow_core
    from kymflow.core.user_config import UserConfig

    # from kymflow.core.utils.logging import get_log_file_path

    retDict["KymFlow Core"] = kymflow_core.__version__  # noqa
    # retDict["KymFlow GUI version"] = kymflow_gui.__version__  # noqa
    retDict["KymFlow GUI"] = "N/A (GUI not imported in core)"  # GUI import commented out
    # retDict["NiceGUI version"] = nicegui.__version__
    retDict["NiceGUI"] = "N/A (GUI not imported in core)"  # GUI import commented out

    retDict["Python"] = platform.python_version()

    retDict["OS System"] = platform.system()
    retDict["OS Release"] = platform.release()
    retDict["OS Machine"] = platform.machine()
    retDict["OS Processor"] = platform.processor()

    
    _user_config_file = UserConfig.default_config_path()
    _user_config_path = _user_config_file.parent
    retDict["User Config"] = str(_user_config_path)
    
    # retDict["email"] = "robert.cudmore@gmail.com"

    # get build info (from nicegui-pack)
    from kymflow.build_info import get_build_info
    build_info = get_build_info()
    # version_info["Build info"] = build_info
    # for key, value in build_info.items():
    #     retDict[key] = value
    retDict["Build info"] = build_info

    return retDict
