import asyncio
import json
import math
import os
from pathlib import Path
import aiohttp
import sys
import vdf


DOTA2_APP_ID = 570


STEAM_CONFIG_FOLDER_NAME = 'config'
STEAM_USERS_FILE_NAME = 'loginusers.vdf'


class Error(Exception):
    pass


class SteamUser:
    def __init__(self, account_name, persona_name, id64):
        self.account_name = account_name
        self.persona_name = persona_name
        self.id64 = int(id64)
        self.id3 = self.id64 - 76561197960265728 # https://github.com/arhi3a/Steam-ID-Converter/blob/master/steam_id_converter.py#L7


GRID_WIDTH = 1200


ROLES = {
    'core': 0,
    'support': 1
}


LANES = {
    'roam': 0,
    'safe': 1,
    'mid': 2,
    'off': 3,
    'jungle': 4
}


class HeroGridCategory:
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

    HERO_WIDTH = 95
    HERO_REAL_WIDTH = 85
    HERO_HEIGHT = 135
    HERO_REAL_HEIGHT = 170

    def __init__(self, name, role, lane, ranks, pickrate_treshold):
        self.name = name
        self.role = role
        self.lane = lane
        self.ranks = ranks
        self.pickrate_treshold = pickrate_treshold
        self.data = [{
            'category_name': name,
            'x_position': 0,
            'y_position': 0,
            'width': 0,
            'height': 0,
            'hero_ids': []
        }]

    @classmethod
    async def create(cls, *args, **kwargs):
        inst = cls(*args, **kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.stratz.com/api/v1/Hero/directory/detail/?role={}&lane={}&rank={}'.format(
                    inst.role,
                    inst.lane,
                    ','.join(str(inst.RANK_IDS[rank]) for rank in inst.ranks)
                ),
                headers = {
                    'content-type': 'application/json'
                }
            ) as resp:
                try:
                    info = await resp.json()
                except Exception as e:
                    print('{}\n\n'.format(resp.text()))
                    raise Error('Failed to parse data from Stratz. The API may be down, your connection unstable,'
                                'or something else. Received data is printed above. Exact error:\n\t{}'.format(repr(e)))

        x_position = 0
        y_position = inst.HERO_REAL_HEIGHT - inst.HERO_HEIGHT
        info['heroes'] = [hero for hero in info['heroes'] if 'pickBan' in hero]
        for hero in sorted(info['heroes'], key=lambda hero: hero['pickBan']['pick']['wins'], reverse=True):
            picks = hero['pickBan']['pick']['matchCount']
            if picks / (info['matchPickCount'] / 10) >= inst.pickrate_treshold:
                inst.data.append({
                    'category_name': '  {:.2f}%'.format(round(hero['pickBan']['pick']['wins'] * 100, 2)),
                    'x_position': x_position,
                    'y_position': y_position,
                    'width': inst.HERO_WIDTH,
                    'height': inst.HERO_HEIGHT,
                    'hero_ids': [
                        hero['heroId']
                    ]
                })

                if x_position + inst.HERO_REAL_WIDTH * 2 > 1200:
                    x_position = 0
                    y_position += inst.HERO_REAL_HEIGHT
                else:
                    x_position += inst.HERO_REAL_WIDTH

        if x_position == 0:
            inst.real_height = y_position
        else:
            inst.real_height = y_position + inst.HERO_REAL_HEIGHT

        return inst


class HeroGrid:
    def __init__(self, name, users, ranks, pickrate_treshold):
        self.name = name
        self.users = users
        self.ranks = ranks
        self.pickrate_treshold = pickrate_treshold

        if self.name is None:
            self.name = 'Winrates by Position ({})'.format(' + '.join((ranks)))

        self.data = {
            'config_name': self.name,
            'categories': []
        }

    @classmethod
    async def create(cls, *args, **kwargs):
        inst = cls(*args, **kwargs)

        categories_params = [
            ('Carry', ROLES['core'], LANES['safe']),
            ('Mid', ROLES['core'], LANES['mid']),
            ('Offlane', ROLES['core'], LANES['off']),
            ('Support', ROLES['support'], LANES['off']),
            ('Hard Support', ROLES['support'], LANES['safe'])
        ]

        categories_coros = []
        for category_params in categories_params:
            categories_coros.append(HeroGridCategory.create(category_params[0], category_params[1], category_params[2], inst.ranks, inst.pickrate_treshold))

        categories = await asyncio.gather(*categories_coros)

        cumulated_height = 0
        for i, category in enumerate(categories):
            if i > 0:
                for subcategory in category.data:
                    subcategory['y_position'] += cumulated_height

            inst.data['categories'].extend(category.data)
            cumulated_height += category.real_height + 60

        return inst


class HeroGridsConfig:
    STEAM_USERDATA_FOLDER_NAME = 'userdata'
    STEAM_USERDATA_REMOTE_FOLDER_NAME = 'remote'

    DOTA2_CFG_FOLDER_NAME = 'cfg'
    GRID_CONFIG_FILE_NAME = 'hero_grid_config.json'

    def __init__(self, steam_path, user):
        self.steam_path = steam_path
        self.user = user
        self.path = \
            Path(self.steam_path) / \
            self.STEAM_USERDATA_FOLDER_NAME / \
            str(self.user.id3) / \
            str(DOTA2_APP_ID) / \
            self.STEAM_USERDATA_REMOTE_FOLDER_NAME / \
            self.DOTA2_CFG_FOLDER_NAME / \
            self.GRID_CONFIG_FILE_NAME

        try:
            with open(self.path, 'r', encoding='utf-8') as fp:
                self.data = json.load(fp)
        except:
            self.data = {
                'version': 3,
                'configs': []
            }

    def add(self, new_grid):
        replaced = False
        for i, grid in enumerate(self.data['configs']):
            if grid['config_name'] == new_grid.name:
                self.data['configs'][i] = new_grid.data
                replaced = True
                break

        if not replaced:
            self.data['configs'].append(new_grid.data)

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as fp:
            json.dump(self.data, fp, indent=4)


async def main():
    with open('config.json', 'r', encoding='utf-8') as fp:
        config = json.load(fp)

    hero_grid_coros = []
    for grid in config['grids']:
        hero_grid_coros.append(HeroGrid.create(grid.get('name'), grid['users'], grid['ranks'], grid['pickrate_treshold']))

    hero_grids = await asyncio.gather(*hero_grid_coros)

    grids = []
    grids_without_users = []
    grid_user_names = set()
    for hero_grid in hero_grids:
        if not hero_grid.users:
            grids_without_users.append(hero_grid.name)
        else:
            grids.append(hero_grid)
            grid_user_names = grid_user_names.union(hero_grid.users)

    if not grids:
        raise Error('No grids found in the config!')

    if not grid_user_names:
        raise Error('None of the grids are assigned to any users!')

    if grids_without_users:
        print('Warning: These grids have no users: {}.'.format(', '.join(grids_without_users)))

    steam_users = []
    steam_users_by_account_name = {}
    try:
        with open(Path(config['steam']['path']) / STEAM_CONFIG_FOLDER_NAME / STEAM_USERS_FILE_NAME, 'r', encoding='utf-8') as fp:
            for id64, user in vdf.load(fp)['users'].items():
                if user['AccountName'] in grid_user_names:
                    grid_user_names.remove(user['AccountName'])
                    steam_users.append(SteamUser(user['AccountName'], user['PersonaName'], id64))
                    steam_users_by_account_name[user['AccountName']] = steam_users[-1]
    except FileNotFoundError:
        raise Error('Steam path invalid, or Steam config files corrupt.')

    if not steam_users:
        raise Error('Usernames from the config don\'t match to any Steam users!')

    if grid_user_names:
        print('Warning: These usernames from the config weren\'t matched to any Steam users: {}.'.format(', '.join(grid_user_names)))

    hero_grids_configs = []
    hero_grids_configs_by_user_account_name = {}
    for user in steam_users:
        hero_grids_configs.append(HeroGridsConfig(config['steam']['path'], user))
        hero_grids_configs_by_user_account_name[user.account_name] = hero_grids_configs[-1]
    
    for grid in grids:
        for user in grid.users:
            try:
                hero_grids_configs_by_user_account_name[user].add(grid)
            except KeyError:
                pass

    for hero_grids_config in hero_grids_configs:
        hero_grids_config.save()

    for grid in grids:
        users = ['{} ({})'.format(user, steam_users_by_account_name[user].persona_name) for user in grid.users]
        print('{} updated for {}.'.format(grid.name, ', '.join(users)))

    print('\n{} grid{} updated for {} user{}!\n'.format(len(grids), 's' if len(grids) > 1 else '', len(steam_users), 's' if len(steam_users) > 1 else ''))


if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(main()) # https://github.com/aio-libs/aiohttp/issues/4324#issuecomment-676675779
    except aiohttp.ClientError:
        raise Error('Something happened with the network. Maybe Stratz is unavailable or your internet is down.')
    except Error as e:
        print('Error: {}\n'.format(e.args[0]))
    finally:
        if getattr(sys, "frozen", False):
            input()
