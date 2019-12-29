from cx_Freeze import setup, Executable

setup(
    executables=[Executable('dota_hero_grid_generator.py')],
    options={
        'build_exe': {
            'include_files': ['config.json'],
            'packages': ['multiprocessing']
        }
    }
)
