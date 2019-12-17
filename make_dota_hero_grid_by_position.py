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
CORE_LANE_POSITIONS = {
    1: 1,
    2: 2,
    3: 3
}
SUPPORT_LANE_POSITIONS = {
    1: 5,
    3: 4
}

RANK_IDS = {
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

    winrates = {i: {} for i in range(1, 6)}
    heroes_core_info = requests.get('https://api.stratz.com/api/v1/Hero/{{id}}?role=0&rank={}'.format(RANK_IDS[config['core_rank']])).json()
    heroes_support_info = requests.get('https://api.stratz.com/api/v1/Hero/{{id}}?role=1&rank={}'.format(RANK_IDS[config['support_rank']])).json()

    for hero in heroes_core_info['heroes']:
        for lane in hero['heroLaneDetail']:
            try:
                winrates[CORE_LANE_POSITIONS[lane['laneId']]][hero['heroId']] = lane['wins']
            except KeyError:
                continue

    for hero in heroes_support_info['heroes']:
        for lane in hero['heroLaneDetail']:
            try:
                winrates[SUPPORT_LANE_POSITIONS[lane['laneId']]][hero['heroId']] = lane['wins']
            except KeyError:
                continue

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

    hero_ids = {}
    hero_basic_info = requests.get('https://api.stratz.com/api/v1/Hero').json()
    for _, hero in hero_basic_info.items():
        hero_ids[hero['displayName']] = hero['id']

    for name, positions in config['hero_positions'].items():
        for position in positions:
            new_grid['categories'][position - 1]['hero_ids'].append(hero_ids[name])

    for i, _ in enumerate(new_grid['categories']):
        new_grid['categories'][i]['hero_ids'].sort(key=lambda id_: winrates[i + 1][id_], reverse=True)

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
    except requests.RequestException:
        raise Error(r'Failed to retreive data from Stratz')
    except Error as e:
        print('Error: {}'.format(e.args[0]))
        exit(1)
