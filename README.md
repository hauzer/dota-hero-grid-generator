![Demo](img/demo.gif)

## How To Install

If you're on Windows, you can download the latest [release](https://github.com/hauzer/dota-hero-grid-generator/releases). No guarantees it's the most up-to-date version, though.

If you want to run from source, follow these instructions:

* Ensure you have Python 3 installed.
*  `git clone git@github.com:hauzer/dota-hero-grid-generator.git`.
*  `cd dota-hero-grid-generator`.
*  `$PYTHON -m venv py`.
*  `py/Scripts/python -m pip install --upgrade git+https://github.com/anthony-tuininga/cx_Freeze.git@master`.
*  `py/Scripts/python -m pip install -r requirements.txt`.

## How To Use

* Point to the Steam installation directory in the `config.json` file.
* Set up your grids, also in the aforementioned file.
* Run with `py/Scripts/python ./dota_hero_grid_generator.py`.

<br/>

<sub>Data provided by [STRATZ](https://stratz.com).</sub>
