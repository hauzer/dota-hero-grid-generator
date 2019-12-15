import json
import math
import os
from pathlib import Path
import requests
import winreg


DOTA2_APP_ID = 570

STEAM_REGISTRY_ROOT_KEY = winreg.HKEY_CURRENT_USER
STEAM_REGISTRY_KEY = r'Software\Valve\Steam'
STEAM_REGISTRY_PATH_VALUE = 'SteamPath'
STEAM_REGISTRY_APPS_KEY = 'Apps'
STEAM_REGISTRY_APP_INSTALLED_VALUE = 'Installed'
STEAM_REGISTRY_USERS_KEY = 'Users'

STEAM_USERDATA_FOLDER = 'userdata'
STEAM_USERDATA_REMOTE_FOLDER = 'remote'
DOTA2_CFG_FOLDER = 'cfg'
GRID_CONFIG_FILE_NAME = 'hero_grid_config.json'

CATEGORY_WIDTH = 1200
CATEGORY_ROW_HEIGHT = 90
CATEGORY_HEROES_PER_ROW = 22
CATEGORY_BOTTOM_PADDING = 60

POSITIONS = ['One', 'Two', 'Three', 'Four', 'Five']
RANKS = {
    'Herald': 1,
    'Guardian': 2,
    'Crusader': 3,
    'Archon': 4,
    'Legend': 5,
    'Ancient': 6,
    'Divine': 7,
    'Immortal': 8
}


class Error(Exception):
    pass


def warning(msg):
    return print('Warning: {}'.format(msg))

def main():
    with open('config.json', 'r') as fp:
        config = json.load(fp)

    try:
        steam_registry_key = winreg.OpenKey(STEAM_REGISTRY_ROOT_KEY, STEAM_REGISTRY_KEY)
    except OSError:
        raise Error(r'Steam registry keys missing.')

    try:
        steam_registry_dota_key = winreg.OpenKey(steam_registry_key, r'{}\{}'.format(STEAM_REGISTRY_APPS_KEY, DOTA2_APP_ID))
        if winreg.QueryValueEx(steam_registry_dota_key, STEAM_REGISTRY_APP_INSTALLED_VALUE)[0] == '0':
            raise OSError
    except OSError:
        warning(r'Steam registry indicates Dota 2 is not installed.')

    trade_id = None
    if config['trade_id'] == 0:
        try:
            steam_registry_users_key = winreg.OpenKey(steam_registry_key, STEAM_REGISTRY_USERS_KEY)
        except OSError:
            raise Error(r'Steam registry user data missing.')
            
        try:
            for i in range(2):
                trade_id = winreg.EnumKey(steam_registry_users_key, i)
                if i == 1:
                    raise Error(r'Multiple Steam users detected. Please supply your trade ID in `config.json` under "trade_id".')
        except OSError:
            if not trade_id:
                raise Error(r'No Steam users detected. Try supplying your trade ID in `config.json` under "trade_id".')
    else:
        trade_id = config['trade_id']

    steam_path = Path(winreg.QueryValueEx(steam_registry_key, STEAM_REGISTRY_PATH_VALUE)[0])
    grid_config_path = steam_path / STEAM_USERDATA_FOLDER / trade_id / str(DOTA2_APP_ID) / STEAM_USERDATA_REMOTE_FOLDER / DOTA2_CFG_FOLDER / GRID_CONFIG_FILE_NAME

    try:
        with open(grid_config_path, 'r') as fp:
            grids = json.load(fp)
    except FileNotFoundError:
        warning(r'Hero grid configuration file not found, creating.')
        grids = {
            'version': 3,
            'configs': []
        }

    try:
        heroes = requests.get('https://api.opendota.com/api/heroStats').json()
    except requests.RequestException:
        raise Error(r'Failed to retreive data from OpenDota')

    core_rank = RANKS[config['core_rank']]
    core_rank_heroes = sorted(heroes, key=lambda h: h['{}_win'.format(core_rank)] / h['{}_pick'.format(core_rank)], reverse=True)

    support_rank = RANKS[config['support_rank']]
    support_rank_heroes = sorted(heroes, key=lambda h: h['{}_win'.format(support_rank)] / h['{}_pick'.format(support_rank)], reverse=True)

    def make_grid_category(i):
        return {
            'category_name': 'Position {}'.format(POSITIONS[i]),
            'x_position': 0,
            'y_position': 0,
            'width': CATEGORY_WIDTH,
            'height': CATEGORY_ROW_HEIGHT,
            'hero_ids': []
        }

    new_grid = {
        'config_name': config['grid_name'],
        'categories': [make_grid_category(i) for i in range(5)]
    }

    for hero in core_rank_heroes:
        for position in config['hero_positions'][hero['localized_name']]:
            if position in [1, 2, 3]:
                new_grid['categories'][position - 1]['hero_ids'].append(hero['id'])

    for hero in support_rank_heroes:
        for position in config['hero_positions'][hero['localized_name']]:
            if position in [4, 5]:
                new_grid['categories'][position - 1]['hero_ids'].append(hero['id'])

    previous_heights = 0
    for category in new_grid['categories']:
        category['y_position'] = previous_heights
        category['height'] *= max(1, math.ceil(len(category['hero_ids']) / CATEGORY_HEROES_PER_ROW))
        previous_heights += category['height'] + CATEGORY_BOTTOM_PADDING

    replaced_grid = False
    for i, grid in enumerate(grids['configs']):
        if grid['config_name'] == new_grid['config_name']:
            grids['configs'][i] = new_grid
            replaced_grid = True
            break

    if not replaced_grid:
        grids['configs'].append(new_grid)

    with open(grid_config_path, 'w') as fp:
        json.dump(grids, fp, indent=4)

    print('Hero grid configuration file successfully updated!')


if __name__ == '__main__':
    try:
        main()
    except Error as e:
        print('Error: {}'.format(e.args[0]))
        exit(1)
