#!/usr/bin/env python3

import argparse
import csv
import math
import os
import re
import subprocess

import pandas as pd

EDGES = {}
FOREIGN_USERS = {}


def generate_key(a, b):
    return '{}|{}'.format(*sorted([a, b]))


def separate_key(key):
    return key.split('|')


def increment_weight(data, key, weight):
    try:
        data[key] = data[key] + weight
    except KeyError:
        data[key] = weight


def download_tweets(screen_name):
    # TODO: Error handling, detect incomplete data
    # TODO: Option for "--since" and "--limit"
    # TODO: Option for path of Twint.py
    if os.path.isfile('{}_tweets.csv'.format(screen_name)):
        return True
    result = subprocess.run(
        args='python Twint.py -u {} --limit 1000 --since 2018-04-20 --csv -o {}_tweets.csv'.format(
            screen_name, screen_name), shell=True)
    result.check_returncode()


def parse_tweets(tweetfile):
    users = {}
    with open(tweetfile, 'r') as fh:
        tweetreader = csv.reader(fh)
        for row in tweetreader:
            for screen_name in re.findall(r"@([a-zA-Z0-9_]+)", row[6]):
                increment_weight(users, screen_name, 1)
    return users


def print_graph(filename):
    max_weight = max(EDGES.values())
    with open(filename, 'w') as graph:
        graph.write('graph G {\n')
        for k, v in EDGES.items():
            a, b = separate_key(k)
            if a in FOREIGN_USERS.keys() and FOREIGN_USERS[a] > 1 or b in FOREIGN_USERS.keys() and FOREIGN_USERS[b] > 1:
                graph.write('"{}" -- "{}" [weight={}, style=dashed];\n'.format(a, b, v))
            elif a not in FOREIGN_USERS.keys() and b not in FOREIGN_USERS.keys():
                graph.write('"{}" -- "{}" [weight={}, penwidth={}];\n'.format(*separate_key(k), v,
                                                                              math.log((18 * v) / max_weight + math.e)))
        graph.write('}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', help='starting point', required=True)
    parser.add_argument('-o', '--output', help='output filename', default='graph.gv')
    args = parser.parse_args()

    download_tweets(args.user)

    users_root = parse_tweets('{}_tweets.csv'.format(args.user))
    df_root = pd.DataFrame(list(users_root.items()), columns=['screen_name', 'mentions'])
    df_head = df_root.sort_values(by='mentions', ascending=False).head(10)

    for user in df_head['screen_name']:
        increment_weight(EDGES, generate_key(args.user, user),
                         df_head.loc[df_head['screen_name'] == user, 'mentions'].values[0])

        download_tweets(user)
        try:
            data = parse_tweets('{}_tweets.csv'.format(user))
        except FileNotFoundError:
            continue

        df_friends = pd.DataFrame(list(data.items()), columns=['screen_name', 'mentions'])
        df_friends_of_friends = df_friends.sort_values(by='mentions', ascending=False).head(10)
        df_friends = df_friends.loc[df_friends['screen_name'].isin(
            [args.user, *df_head['screen_name'].drop(df_head[df_head['screen_name'] == user].index)])]
        df_friends_of_friends = df_friends_of_friends[~df_friends_of_friends.isin(df_friends)].dropna()

        for other_user in df_friends['screen_name']:
            increment_weight(EDGES, generate_key(user, other_user),
                             df_friends.loc[df_friends['screen_name'] == other_user, 'mentions'].values[0])

        for other_user in df_friends_of_friends['screen_name']:
            increment_weight(EDGES, generate_key(user, other_user),
                             df_friends_of_friends.loc[
                                 df_friends_of_friends['screen_name'] == other_user, 'mentions'].values[0])
            increment_weight(FOREIGN_USERS, other_user, 1)

    print_graph(args.output)


if __name__ == '__main__':
    main()
