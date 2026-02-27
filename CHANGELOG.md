# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-11-01
### Added
- Initial public release of KymFlow.
- macOS standalone app bundle for running the KymFlow GUI without Python.

### Fixed
- N/A

### Known Issues
- Lots we will address in next releases.

## [0.2.1] - 2026-02-27

Final KymFlow.app should run on first double-click by user, no need to use terminal xaatr or "Full Disk Access". This was achieved by proper (i) codesign, (ii) notary tool, and (iii) staple.

Otherwise, no changes

### Known Issues

 - If user open from a folder without KymFlow app acces, will still get misleading 'loaded' notify but now files will be loaded. see log for entries like this:

 ```
2026-02-26 10:46:44 [WARNING] kymflow.core.image_loaders.acq_image_list:_instantiate_image:305:   -->> e:[Errno 1] Operation not permitted: '/Users/dmanning/Downloads/declan-stall-v1/28d Saline/20251030/20251030_A106_0003.txt'

2026-02-26 10:46:44 [WARNING] kymflow.core.image_loaders.acq_image_list:_instantiate_image:304: AcqImageList: could not load file: /Users/dmanning/Downloads/declan-stall-v1/28d Saline + Recovery/20251114/20251114_A114_0002.tif
```


