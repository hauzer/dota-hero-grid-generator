![Demo](img/demo.gif)

## How To Install

If you're on Windows, you can download the latest [release](https://github.com/hauzer/dota-hero-grid-generator/releases). No guarantees it's the most up-to-date version, though.

If you want to run from source, ensure that you have Python 3.9.1+ and the `venv` module installed; how to install this depends on your system. Then follow the instructions below.

Linux:
*  `$ git clone https://github.com/hauzer/dota-hero-grid-generator.git`
*  `$ cd dota-hero-grid-generator`
*  `$ python3 -m venv py`
*  `$ py/bin/python -m pip install -r requirements.txt`

Windows:
*  `$ git clone https://github.com/hauzer/dota-hero-grid-generator.git`
*  `$ cd dota-hero-grid-generator`
*  `$ py -3 -m venv py`
*  `$ py/Scripts/python -m pip install -r requirements.txt`

## How To Use

* Configure `config.json`:
   * Get your own Stratz API token [here](https://stratz.com/api). You just need to log in with your Steam account.
   * Point to the Steam installation directory. Note that this is *not* where Dota is, but where the actual Steam executable resides (e.g. `steam.exe` on Windows).
   * Set up your grids. Take a look [here](config-schema.jsonc) for detailed documentation.
* Run:
  * If from a release, just double click on `dota_hero_grid_generator.exe`.
  * If from source on Linux, use the following command:  
  `$ py/bin/python ./dota_hero_grid_generator.py`  
  * If from source on Windows, use the following command:  
  `$ py/Scripts/python ./dota_hero_grid_generator.py`  
* You'll be informed about which grid(s) were created/updated for which user(s).
* Enjoy!

<sub>Data provided by [STRATZ](https://stratz.com).</sub>

## Donations

If you enjoy my work, please consider a donation.

```
BTC: BC1QF2G847UQTDY6GAG5D64DSCFVEZ0HHY7AC3PNKX

ETH: 0x61a08C3f8dF5A0507923FcA2ec8597e68e51d6A0

XMR: 48aLGv9rg2Q1edA36PjKbj34SEAViUSGH47QfGDmWuqEDjUE1fA238BMn6z3R79DfKBTgu6TkT4VL5sMeTG6axMaKXytH6F
```
