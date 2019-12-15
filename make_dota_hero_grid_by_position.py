import json
import math
import requests


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


def main():
    heroes = requests.get('https://api.opendota.com/api/heroStats').json()

    with open('config.json', 'r') as fp:
        config = json.load(fp)

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

    with open('hero_grid_config.json', 'r') as fp:
        grids = json.load(fp)

    replaced_grid = False
    for i, grid in enumerate(grids['configs']):
        if grid['config_name'] == new_grid['config_name']:
            grids['configs'][i] = new_grid
            replaced_grid = True
            break

    if not replaced_grid:
        grids['configs'].append(new_grid)

    with open('hero_grid_config.json', 'w') as fp:
        json.dump(grids, fp, indent=4)

if __name__ == '__main__':
    main()
