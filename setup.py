from cx_Freeze import setup

build_exe_options = {
    'include_files': ['config.json'],
    'packages': ['multiprocessing']
}

setup(
    name='dota-hero-grid-generator',
    options={"build_exe": build_exe_options},
    executables=[{'script': 'dota_hero_grid_generator.py'}]
)
