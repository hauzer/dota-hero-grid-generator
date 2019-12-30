import json
import math
import os
from pathlib import Path
import requests
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


class HeroGrid:
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

    CATEGORY_WIDTH = 1200
    CATEGORY_ROW_HEIGHT = 90
    CATEGORY_HEROES_PER_ROW = 22
    CATEGORY_BOTTOM_PADDING = 60

    def __init__(self, name, users, core_rank, support_rank, total_pickrate_treshold, lane_pickrate_treshold):
        self.name = name
        self.users = users
        self.core_rank = core_rank
        self.support_rank = support_rank
        self.total_pickrate_treshold = total_pickrate_treshold
        self.lane_pickrate_treshold = lane_pickrate_treshold

        def make_grid_category(i):
            return {
                'category_name': 'Position {}'.format(self.POSITIONS[i]),
                'x_position': 0,
                'y_position': 0,
                'width': self.CATEGORY_WIDTH,
                'height': self.CATEGORY_ROW_HEIGHT,
                'hero_ids': []
            }

        self.data = {
            'config_name': self.name,
            'categories': [make_grid_category(i) for i in range(5)]
        }

        heroes_info_all = {i: {} for i in range(1, 6)}
        heroes_core_info = requests.get('https://api.stratz.com/api/v1/Hero/{{id}}?role=0&rank={}'.format(self.RANK_IDS[self.core_rank])).json()
        heroes_support_info = requests.get('https://api.stratz.com/api/v1/Hero/{{id}}?role=1&rank={}'.format(self.RANK_IDS[self.support_rank])).json()

        for heroes_role_info, role_lane_positions in [(heroes_core_info, self.CORE_LANE_POSITIONS), (heroes_support_info, self.SUPPORT_LANE_POSITIONS)]:
            for hero in heroes_role_info['heroes']:
                picks = hero['pickBan']['pick']['matchCount']
                if picks / heroes_role_info['matchPickCount'] >= self.total_pickrate_treshold:
                    for lane in hero['heroLaneDetail']:
                        try:
                            heroes_info_all[role_lane_positions[lane['laneId']]][hero['heroId']] = (lane['wins'], lane['matchCount'] / picks)
                        except KeyError:
                            continue

        for position, heroes_info in heroes_info_all.items():
            for hero_id, hero_info in heroes_info.items():
                if hero_info[1] >= self.lane_pickrate_treshold:
                    self.data['categories'][position - 1]['hero_ids'].append(hero_id)

        for i, _ in enumerate(self.data['categories']):
            self.data['categories'][i]['hero_ids'].sort(key=lambda id_: heroes_info_all[i + 1][id_][0], reverse=True)

        previous_heights = 0
        for category in self.data['categories']:
            category['y_position'] = previous_heights
            category['height'] *= max(1, math.ceil(len(category['hero_ids']) / self.CATEGORY_HEROES_PER_ROW))
            previous_heights += category['height'] + self.CATEGORY_BOTTOM_PADDING


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
            with open(self.path, 'r') as fp:
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
        with open(self.path, 'w') as fp:
            json.dump(self.data, fp, indent=4)


def join_list_of_strings_with_commas(lst):
    return ', '.join(lst).rstrip(', ')


def main():
    with open('config.json', 'r') as fp:
        config = json.load(fp)

    grids = []
    grids_without_users = []
    grid_user_names = set()
    for grid in config['grids']:
        hero_grid = HeroGrid(grid['name'], grid['users'], grid['core_rank'], grid['support_rank'], grid['total_pickrate_treshold'], grid['lane_pickrate_treshold'])
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
        print('Warning: These grids have no users: {}.'.format(join_list_of_strings_with_commas(grids_without_users)))

    steam_users = []
    steam_users_by_account_name = {}
    with open(Path(config['steam']['path']) / STEAM_CONFIG_FOLDER_NAME / STEAM_USERS_FILE_NAME, 'r') as fp:
        for id64, user in vdf.load(fp)['users'].items():
            if user['AccountName'] in grid_user_names:
                grid_user_names.remove(user['AccountName'])
                steam_users.append(SteamUser(user['AccountName'], user['PersonaName'], id64))
                steam_users_by_account_name[user['AccountName']] = steam_users[-1]

    if not steam_users:
        raise Error('Usernames from the config don\'t match to any Steam users!')

    if grid_user_names:
        print('Warning: These usernames from the config weren\'t matched to any Steam users: {}.'.format(join_list_of_strings_with_commas(grid_user_names)))

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
        print('{} updated for {}.'.format(grid.name, join_list_of_strings_with_commas(users)))

    print('\n{} grid{} updated for {} user{}!\n'.format(len(grids), 's' if len(grids) > 1 else '', len(steam_users), 's' if len(steam_users) > 1 else ''))


if __name__ == '__main__':
    try:
        main()
    except requests.RequestException:
        raise Error(r'Failed to retreive data from Stratz')
    except Error as e:
        print('Error: {}'.format(e.args[0]))
        exit(1)
