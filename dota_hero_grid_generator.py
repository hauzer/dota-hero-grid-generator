import warnings
warnings.filterwarnings('ignore')

import aiohttp
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import traceback
import time
import uuid
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


class HeroGridCategory:
    HERO_WIDTH = 95
    HERO_REAL_WIDTH = 85
    HERO_HEIGHT = 135
    HERO_REAL_HEIGHT = 170

    def __init__(
        self,
        name,
        positions,
        ranks,
        modes,
        winrate_treshold,
        pickrate_treshold,
        show_pickrates,
        include_outliers,
        show_outliers_separately,
        winrate_outlier_treshold,
        pickrate_outlier_treshold,
        take_weeks,
        stratz_token,
        http_session
    ):
        self.name = name
        self.positions = positions
        self.ranks = ranks
        self.modes = modes
        self.winrate_treshold = winrate_treshold
        self.pickrate_treshold = pickrate_treshold
        self.show_pickrates = show_pickrates
        self.include_outliers = include_outliers
        self.show_outliers_separately = show_outliers_separately
        self.winrate_outlier_treshold = winrate_outlier_treshold
        self.pickrate_outlier_treshold = pickrate_outlier_treshold
        self.take_weeks = take_weeks
        self.data = [{
            'category_name': name,
            'x_position': 0,
            'y_position': 0,
            'width': 0,
            'height': 0,
            'hero_ids': []
        }]
        self.stratz_token = stratz_token
        self.http_session = http_session
        self.real_height = 0

    @classmethod
    async def create(cls, *args, **kwargs):
        inst = cls(*args, **kwargs)

        query = f'''
            {{
                heroStats {{
                    winWeek(
                        take: {inst.take_weeks},
                        bracketIds: [{','.join([rank.upper() for rank in inst.ranks])}],
                        positionIds: [{','.join([f'POSITION_{position}' for position in inst.positions])}],
                        gameModeIds: [{','.join([mode.upper() for mode in inst.modes])}]
                    ) {{
                        heroId,
                        matchCount,
                        winCount
                    }}
                }}
            }}
        '''

        async def make_request(api):
            while True:
                inst.http_session.rate_limiting['requests'] = [request for request in inst.http_session.rate_limiting['requests'] if request['timestamp'] >= time.time() - 1]
                if len(inst.http_session.rate_limiting['requests']) < inst.http_session.rate_limiting['requests_per_second']:
                    break

                await asyncio.sleep(0.5)

            id = uuid.uuid4()
            inst.http_session.rate_limiting['requests'].append({
                'id': id,
                'timestamp': time.time()
            })
            resp = await inst.http_session.post(
                f'{api}',
                data=json.dumps({'query': query}),
                headers = {
                    'User-Agent': 'STRATZ_API',
                    'Authorization': f'Bearer {inst.stratz_token}',
                    'Content-Type': 'application/json'
                }
            )

            inst.http_session.rate_limiting['requests'] = [request for request in inst.http_session.rate_limiting['requests'] if request['id'].int != id.int]

            text = await resp.text()

            try:
                json_data = json.loads(text)

                try:
                    if json_data['message'] == 'API rate limit exceeded':
                        print('You\'re being rate-limited by Stratz. Lower requests_per_second in the configuration file.\n\n')
                        os._exit()
                    elif json_data['message'] == 'A bearer token is required for a request. View more at https://stratz.com/api':
                        print('Your Stratz API token has expired. Refresh it at https://stratz.com/api.\n\n')
                        os._exit()
                except:
                    pass

                return json.loads(text)['data']
            except Exception as e:
                raise Error(f'Failed to parse data from Stratz. The API may be down, your connection unstable, '
                            f'or something else. Exact error:\n\n{traceback.format_exc()}\n\nData:{text}')

        data = (await make_request('https://api.stratz.com/graphql'))

        heroes_raw = data['heroStats']['winWeek']
        heroes = []
        for hero in heroes_raw:
            if any([hero['heroId'] == h['heroId'] for h in heroes]):
                continue

            for h in [h for h in heroes_raw if hero['heroId'] == h['heroId']][1:]:
                hero['winCount'] += h['winCount']
                hero['matchCount'] += h['matchCount']

            heroes.append(hero)

        all_match_count = sum([hero['matchCount'] for hero in heroes])

        for hero in heroes:
            hero['pickRate'] = round(hero['matchCount'] / (all_match_count / 10) * 100, 2)
            hero['winRate'] = round(hero['winCount'] / hero['matchCount'] * 100, 2)

        x_position = 0
        y_position = inst.HERO_REAL_HEIGHT - inst.HERO_HEIGHT
        def generate_hero(hero, start_x_position=None, end_x_position=None):
            nonlocal inst
            nonlocal x_position
            nonlocal y_position

            if start_x_position is None:
                start_x_position = 0

            if end_x_position is None:
                end_x_position = 1200

            if inst.show_pickrates:
                inst.data.append({
                    'category_name': '  {:.2f}%'.format(hero['winRate']),
                    'x_position': x_position,
                    'y_position': y_position,
                    'width': 0,
                    'height': 0,
                    'hero_ids': []
                })

                inst.data.append({
                    'category_name': '  {:.2f}%'.format(hero['pickRate']),
                    'x_position': x_position,
                    'y_position': y_position + 20,
                    'width': inst.HERO_WIDTH,
                    'height': inst.HERO_HEIGHT,
                    'hero_ids': [
                        hero['heroId']
                    ]
                })

                if x_position + inst.HERO_REAL_WIDTH * 2 > end_x_position:
                    x_position = start_x_position
                    y_position += inst.HERO_REAL_HEIGHT + 20
                else:
                    x_position += inst.HERO_REAL_WIDTH
            else:
                inst.data.append({
                    'category_name': '  {:.2f}%'.format(hero['winRate']),
                    'x_position': x_position,
                    'y_position': y_position,
                    'width': inst.HERO_WIDTH,
                    'height': inst.HERO_HEIGHT,
                    'hero_ids': [
                        hero['heroId']
                    ]
                })

                if x_position + inst.HERO_REAL_WIDTH * 2 > end_x_position:
                    x_position = start_x_position
                    y_position += inst.HERO_REAL_HEIGHT
                else:
                    x_position += inst.HERO_REAL_WIDTH

        winrate_outlier_treshold = inst.winrate_outlier_treshold if inst.winrate_outlier_treshold is not None else 1000
        pickrate_outlier_treshold = inst.pickrate_outlier_treshold if inst.pickrate_outlier_treshold is not None else 1000

        category_heroes = []
        for hero in sorted(heroes, key=lambda hero: hero['winRate'], reverse=True):
            if (hero['winRate'] >= inst.winrate_treshold and hero['pickRate'] >= inst.pickrate_treshold) or (inst.include_outliers and not inst.show_outliers_separately and (hero['winRate'] >= winrate_outlier_treshold or hero['pickRate'] >= pickrate_outlier_treshold)):
                generate_hero(hero)
                category_heroes.append(hero)

        if inst.include_outliers and inst.show_outliers_separately:
            outliers = [h for h in heroes if not any(ch['heroId'] == h['heroId'] for ch in category_heroes) and (h['winRate'] >= winrate_outlier_treshold or h['pickRate'] >= pickrate_outlier_treshold)]

            if len(outliers) > 0:
                if x_position != 0:
                    y_position += inst.HERO_REAL_HEIGHT

                    if inst.show_pickrates:
                        y_position += 20

                x_position = inst.HERO_REAL_WIDTH

                inst.data.append({
                    'category_name': f'Outliers: {inst.name}',
                    'x_position': x_position,
                    'y_position': y_position,
                    'width': 0,
                    'height': 0,
                    'hero_ids': []
                })

                y_position += inst.HERO_REAL_HEIGHT - inst.HERO_HEIGHT

                for hero in sorted(outliers, key=lambda hero: hero['winRate'], reverse=True):
                    generate_hero(hero, inst.HERO_REAL_WIDTH, 1200 - inst.HERO_REAL_WIDTH)

                if x_position == inst.HERO_REAL_WIDTH:
                    x_position = 0

        if x_position == 0:
            inst.real_height += y_position
        else:
            inst.real_height += y_position + inst.HERO_REAL_HEIGHT

            if inst.show_pickrates:
                inst.real_height += 20

        return inst


class HeroGrid:
    def __init__(
        self,
        name,
        users,
        categories,
        ranks,
        modes,
        winrate_treshold,
        pickrate_treshold,
        show_pickrates,
        include_outliers,
        show_outliers_separately,
        winrate_outlier_treshold,
        pickrate_outlier_treshold,
        take_weeks,
        stratz_token,
        http_session
    ):
        self.name = name
        self.users = users

        if categories is None:
            self.categories = [
                {
                    'name': 'Carry',
                    'positions': [1]
                },
                {
                    'name': 'Mid',
                    'positions': [2]
                },
                {
                    'name': 'Offlane',
                    'positions': [3]
                },
                {
                    'name': 'Support',
                    'positions': [4]
                },
                {
                    'name': 'Hard Support',
                    'positions': [5]
                }
            ]
        else:
            self.categories = categories

        self.ranks = ranks
        self.modes = modes
        self.winrate_treshold = winrate_treshold
        self.pickrate_treshold = pickrate_treshold
        self.show_pickrates = show_pickrates
        self.include_outliers = include_outliers
        self.show_outliers_separately = show_outliers_separately
        self.winrate_outlier_treshold = winrate_outlier_treshold
        self.pickrate_outlier_treshold = pickrate_outlier_treshold
        self.take_weeks = take_weeks

        for category in self.categories:
            if category.get('name') is None:
                category['name'] = ' + '.join(
                    {
                        1: 'Carry',
                        2: 'Mid',
                        3: 'Offlane',
                        4: 'Support',
                        5: 'Hard Support'
                    }[position] for position in category['positions']
                )

            if category.get('ranks') is None:
                category['ranks'] = self.ranks

            if category.get('modes') is None:
                category['modes'] = self.modes

            if category.get('winrate_treshold') is None:
                category['winrate_treshold'] = self.winrate_treshold

            if category.get('pickrate_treshold') is None:
                category['pickrate_treshold'] = self.pickrate_treshold

            if category.get('show_pickrates') is None:
                category['show_pickrates'] = self.show_pickrates

            if category.get('include_outliers') is None:
                category['include_outliers'] = self.include_outliers

            if category.get('show_outliers_separately') is None:
                category['show_outliers_separately'] = self.show_outliers_separately

            if category.get('winrate_outlier_treshold') is None:
                category['winrate_outlier_treshold'] = self.winrate_outlier_treshold

            if category.get('pickrate_outlier_treshold') is None:
                category['pickrate_outlier_treshold'] = self.pickrate_outlier_treshold

            if category.get('weeks') is None:
                category['weeks'] = self.take_weeks

        self.data = {
            'config_name': self.name,
            'categories': []
        }

        self.stratz_token = stratz_token
        
        self.http_session = http_session

    @classmethod
    async def create(cls, *args, **kwargs):
        inst = cls(*args, **kwargs)

        categories_coros = []
        for category in inst.categories:
            categories_coros.append(HeroGridCategory.create(
                category['name'],
                category['positions'],
                category['ranks'],
                category['modes'],
                category['winrate_treshold'],
                category['pickrate_treshold'],
                category['show_pickrates'],
                category['include_outliers'],
                category['show_outliers_separately'],
                category['winrate_outlier_treshold'],
                category['pickrate_outlier_treshold'],
                category['weeks'],
                inst.stratz_token,
                inst.http_session
            ))

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

    connector = aiohttp.TCPConnector(
        family=socket.AF_INET,
        ssl=False,
        limit=config['stratz']['requests_per_second']
    )

    cookie_jar = aiohttp.CookieJar(unsafe=True)

    async with aiohttp.ClientSession(connector=connector, cookie_jar=cookie_jar) as http_session:
        http_session.rate_limiting = {
            'requests_per_second': config['stratz']['requests_per_second'],
            'requests': []
        }

        hero_grid_coros = []
        for grid in config['grids']:
            hero_grid_coros.append(HeroGrid.create(
                grid['name'],
                grid['users'],
                grid.get('categories'),
                grid.get('ranks'),
                grid.get('modes'),
                grid.get('winrate_treshold'),
                grid.get('pickrate_treshold'),
                grid.get('show_pickrates'),
                grid.get('include_outliers'),
                grid.get('show_outliers_separately'),
                grid.get('winrate_outlier_treshold'),
                grid.get('pickrate_outlier_treshold'),
                grid.get('weeks'),
                config['stratz']['token'],
                http_session
            ))

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
        asyncio.run(main())
    except aiohttp.ClientError:
        raise Error('Something happened with the network. Maybe Stratz is unavailable or your internet is down.')
    except Error as e:
        print('Error: {}\n'.format(e.args[0]))
    finally:
        if getattr(sys, "frozen", False):
            input()
