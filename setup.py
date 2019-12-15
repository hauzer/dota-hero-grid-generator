from cx_Freeze import setup, Executable

setup(
    executables=[Executable('make_dota_hero_grid_by_position.py')],
    options={
        'build_exe': {
            'include_files': ['config.json'],
            'packages': ['multiprocessing']
        }
    }
)
